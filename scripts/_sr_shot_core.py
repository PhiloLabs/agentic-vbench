"""Shared core for shot-scoped super-resolution task generators.

Pattern: take a multi-shot 60s clip; pick ONE shot inside it; downsample
that shot N× then re-upsample to original dimensions so the corrupted
video is constant W×H but contains one visibly degraded shot. The agent
must detect the bad shot and restore it.

Pipeline:
  1. Extract 60s clip from source (fixed offset, source fps, source dims,
     no audio).
  2. Run PySceneDetect on the clip; pick a target shot of 100-200 frames
     that is not the first/last and has high-detail content (via
     Laplacian-variance sampling).
  3. Build corrupted.mp4 = clip with target-shot frames downsampled N×
     then bicubic-re-upsampled. Other frames are untouched.
  4. Write Harbor task dir with:
       - workdir/corrupted.mp4, prompt.txt, setup.sh
       - tests/original.mp4, gt_shot.json, judge.py, test.sh
       - solution/solve.sh (oracle: Lanczos upscale on GT range)

Judge composite:
  reward = 0.7 * quality_score (PSNR-Y + SSIM-Y on GT range)
         + 0.2 * IoU(agent_range, gt_range)
         + 0.1 * out_score  (mean PSNR between input and output on
                             frames OUTSIDE agent range, /50, clipped)

Used by:
  build_sr_2x_shot.py
  build_sr_4x_shot.py
"""
from __future__ import annotations

import json
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent  # experiment/
TASKS_DIR = REPO_ROOT / "tasks" / "agentic_vbench_repair"
SOURCES_DIR = REPO_ROOT / "sources"


# -------------------------------------------------------------------- TOML
TASK_TOML = """\
version = "1.0"

[task]
name = "agentic-vbench/{task_name}"

[metadata]
difficulty = "hard"
category = "video-super-resolution-shot"
tags = ["super-resolution", "shot-scoped", "{factor_tag}", "video-restoration"]
source = "{source_name}"
corruption = "{corruption_desc}"
license = "unknown-research-use-only"
attribution = "see source URL"

[environment]
build_timeout_sec = 600.0
cpus = 2
memory_mb = 4096
storage_mb = 8192
allow_internet = true

[[steps]]
name = "solve"

[steps.agent]
timeout_sec = 2400.0

[steps.verifier]
timeout_sec = 900.0
"""


DOCKERFILE = """\
FROM --platform=linux/amd64 python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \\
        ffmpeg curl ca-certificates gcc g++ python3-dev \\
        libsndfile1 libgl1 libglib2.0-0 \\
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \\
        "numpy<3" "scipy<2" \\
        "opencv-python-headless==4.13.*" \\
        "scikit-image>=0.22"

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
"""


INSTRUCTION_TEMPLATE = """\
# Shot-Scoped Super-Resolution ({factor}× downsample)

`/workspace/materials/corrupted.mp4` is a {duration_s}s, {fps_int}fps,
{width}×{height} video composed of multiple shots. **Exactly one shot**
has been corrupted: its frames were downsampled by {factor}× then bicubic
re-upsampled to the original resolution. The result has the same
dimensions as the rest of the video but visibly lower quality (blurry,
loss of fine detail). All other shots are untouched.

Prompt for context: `/workspace/materials/prompt.txt`.

## Your job

1. Identify the corrupted shot in `corrupted.mp4`. Output its zero-indexed
   frame range as `[start_frame, end_frame]` (both inclusive).
2. Restore the corrupted shot to the best quality you can. The remaining
   shots should pass through unchanged.
3. Write:
   - `/workspace/output/output.mp4` — full restored video (same fps and
     dimensions as the corrupted input)
   - `/workspace/output/output.json`:
     ```json
     {{
       "start_frame": 412,
       "end_frame":   780
     }}
     ```

## Output format

- H.264 / yuv420p mp4
- Same width × height and frame rate as `corrupted.mp4`
- Same total frame count as `corrupted.mp4`
- Video-only (no audio)
- `output.json` with inclusive zero-indexed `start_frame` / `end_frame`.

## Scoring

```
quality = 0.5 * clip01((mean_PSNR_Y - 15) / 25)
        + 0.5 * clip01(mean_SSIM_Y)
        (computed on frames in the GROUND-TRUTH shot range, comparing
         your output to a held-out clean reference)

IoU      = 1-D IoU between your reported [start_frame, end_frame] and
           the hidden ground-truth shot range

out_score = min(mean_PSNR(input, output, frames OUTSIDE your range) / 50, 1)

reward = 0.70 * quality + 0.20 * IoU + 0.10 * out_score
```

A bicubic-passthrough (do nothing) typically gets quality ~0.4 (since the
corruption is bicubic re-upsample → matching it perfectly on those
frames), zero IoU, perfect preservation ⇒ ~0.38.

A Lanczos upscale on the right shot beats bicubic on PSNR/SSIM. A neural
SR (Real-ESRGAN, BasicVSR++) would beat Lanczos.

## Tools available

- `ffmpeg` (built into container)
- Python with `numpy`, `opencv-python-headless`, `scipy`, `scikit-image`
- `pip install` more if you want (e.g. `realesrgan`, `basicsr`)
- `/workspace/work/` for scratch

## Tips

- Shot boundaries are visible by stride-sampling thumbnails (~1 frame
  every second). Sharpness drops sharply within the corrupted shot.
- The corrupted shot was produced by `scale={ds_filter},flags=bicubic`
  followed by re-upscale back to {width}×{height}. Reversing that with
  the same bicubic doesn't help; a better filter (Lanczos) or a learned
  SR model does.
- Frames outside your reported range will be byte-compared against the
  input — leaving them alone (re-encode passthrough) is the safe move.
"""


SETUP_SH = """\
#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

mkdir -p /workspace/materials /workspace/output /workspace/work
cp "$HERE/corrupted.mp4" /workspace/materials/corrupted.mp4
cp "$HERE/prompt.txt" /workspace/materials/prompt.txt

if [ ! -s /workspace/materials/corrupted.mp4 ]; then
    echo "ERROR: corrupted.mp4 missing or empty" >&2
    exit 1
fi

mkdir -p /logs/artifacts
ffprobe -v error -show_entries stream=nb_read_frames,r_frame_rate,duration,width,height \\
        -count_frames -select_streams v:0 \\
        /workspace/materials/corrupted.mp4 \\
        > /logs/artifacts/input-probe.txt 2>&1 || true

rm -rf -- "$HERE/corrupted.mp4" "$HERE/prompt.txt" "$0"
"""


TEST_SH = """\
#!/bin/bash
# Verifier: shot-scoped SR judge — PSNR-Y/SSIM-Y in shot, IoU, out-PSNR.
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts

if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

python3 -c "import cv2, numpy, skimage" 2>/dev/null || \\
    pip install --quiet --no-cache-dir "numpy<3" "opencv-python-headless==4.13.*" "scikit-image>=0.22"

python3 /tests/judge.py \\
        --output-mp4 /workspace/output/output.mp4 \\
        --output-json /workspace/output/output.json \\
        --gt-shot-json /tests/gt_shot.json \\
        --corrupted /workspace/materials/corrupted.mp4 \\
        --original /tests/original.mp4 \\
        --reward-json /logs/verifier/reward.json \\
        --reward-txt /logs/verifier/reward.txt
"""


JUDGE_PY = r'''#!/usr/bin/env python3
"""Shot-scoped super-resolution judge.

Components:
  - localization_iou: 1-D IoU between agent range and GT range.
  - quality_score:    in-shot PSNR-Y + SSIM-Y vs held-out original.
                      psnr_n = clip01((mean_PSNR - 15) / 25)
                      ssim_n = clip01(mean_SSIM)
                      quality_score = 0.5 * psnr_n + 0.5 * ssim_n
  - out_score:        min(mean_PSNR(input, output, frames OUTSIDE agent
                                    range) / 50, 1.0)

  reward = 0.7 * quality_score + 0.2 * iou + 0.1 * out_score

Y channel uses BT.601 luma: Y = 0.299 R + 0.587 G + 0.114 B (on RGB
[0,255]). OpenCV gives BGR so we use the standard cvtColor mapping.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from skimage.metrics import structural_similarity


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _zero(reason: str, **kw) -> dict:
    return {"reward": 0.0, "details": {"reason": reason, **kw}}


def _read_frame(cap, idx: int) -> np.ndarray | None:
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, idx))
    ok, frame = cap.read()
    return frame if ok else None


def _bgr_to_y(frame_bgr: np.ndarray) -> np.ndarray:
    """BT.601 luma (Y channel of YCrCb), float32 in [0, 255]."""
    ycrcb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2YCrCb)
    return ycrcb[..., 0].astype(np.float32)


def _psnr_y(a_bgr: np.ndarray, b_bgr: np.ndarray) -> float:
    """PSNR on Y channel, data_range=255. Identical inputs → 100 dB."""
    ya = _bgr_to_y(a_bgr)
    yb = _bgr_to_y(b_bgr)
    if ya.shape != yb.shape:
        yb = cv2.resize(yb, (ya.shape[1], ya.shape[0]),
                        interpolation=cv2.INTER_AREA)
    mse = float(np.mean((ya - yb) ** 2))
    if mse <= 1e-8:
        return 100.0
    return float(10.0 * np.log10((255.0 ** 2) / mse))


def _ssim_y(a_bgr: np.ndarray, b_bgr: np.ndarray) -> float:
    ya = _bgr_to_y(a_bgr)
    yb = _bgr_to_y(b_bgr)
    if ya.shape != yb.shape:
        yb = cv2.resize(yb, (ya.shape[1], ya.shape[0]),
                        interpolation=cv2.INTER_AREA)
    return float(structural_similarity(ya, yb, data_range=255.0))


def _iou_ranges(a0: int, a1: int, b0: int, b1: int) -> float:
    if a1 < a0 or b1 < b0:
        return 0.0
    inter = max(0, min(a1, b1) - max(a0, b0) + 1)
    union = (a1 - a0 + 1) + (b1 - b0 + 1) - inter
    if union <= 0:
        return 0.0
    return inter / union


def _n_frames(path: Path) -> int:
    cap = cv2.VideoCapture(str(path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return n


def score(output_mp4: Path, output_json: Path, gt_shot_json: Path,
          corrupted_mp4: Path, original_mp4: Path) -> dict:
    if not output_mp4.exists():
        return _zero(f"no output.mp4 at {output_mp4}")
    if not gt_shot_json.exists():
        return _zero(f"missing gt_shot.json at {gt_shot_json}")
    if not corrupted_mp4.exists():
        return _zero(f"missing corrupted.mp4 at {corrupted_mp4}")
    if not original_mp4.exists():
        return _zero(f"missing original.mp4 at {original_mp4}")

    try:
        gt = json.loads(gt_shot_json.read_text())
        gt_lo = int(gt["start_frame"])
        gt_hi = int(gt["end_frame"])
    except Exception as e:
        return _zero(f"bad gt_shot.json: {e}")

    # ---- parse agent json ----
    agent_lo, agent_hi = -1, -2
    agent_json_err = None
    if output_json.exists():
        try:
            aj = json.loads(output_json.read_text())
            agent_lo = int(aj.get("start_frame", -1))
            agent_hi = int(aj.get("end_frame", -2))
            if agent_hi < agent_lo:
                agent_json_err = "end_frame < start_frame"
                agent_lo, agent_hi = -1, -2
        except Exception as e:
            agent_json_err = f"parse error: {e}"
    else:
        agent_json_err = "output.json missing"

    n_out = _n_frames(output_mp4)
    n_corr = _n_frames(corrupted_mp4)
    n_orig = _n_frames(original_mp4)
    if n_out <= 0:
        return _zero("output.mp4 has no decodable frames")

    # ---- localization IoU ----
    iou = _iou_ranges(agent_lo, agent_hi, gt_lo, gt_hi)

    # ---- in-shot quality (PSNR-Y + SSIM-Y vs ORIGINAL on GT range) ----
    cap_out = cv2.VideoCapture(str(output_mp4))
    cap_orig = cv2.VideoCapture(str(original_mp4))
    psnrs = []
    ssims = []
    in_lo = max(0, min(n_out - 1, gt_lo))
    in_hi = max(in_lo, min(n_out - 1, gt_hi))
    for fi in range(in_lo, in_hi + 1):
        of = _read_frame(cap_out, fi)
        gf = _read_frame(cap_orig, fi)
        if of is None or gf is None:
            continue
        try:
            psnrs.append(_psnr_y(gf, of))
            ssims.append(_ssim_y(gf, of))
        except Exception:
            continue
    cap_out.release()
    cap_orig.release()
    if not psnrs:
        return _zero("no in-shot frames could be scored",
                     agent_range=[agent_lo, agent_hi], gt_range=[gt_lo, gt_hi])
    mean_psnr_in = float(np.mean(psnrs))
    mean_ssim_in = float(np.mean(ssims))
    psnr_n = _clip01((mean_psnr_in - 15.0) / 25.0)
    ssim_n = _clip01(mean_ssim_in)
    quality_score = 0.5 * psnr_n + 0.5 * ssim_n

    # ---- preservation: out-of-range PSNR between corrupted input and output ----
    cap_in = cv2.VideoCapture(str(corrupted_mp4))
    cap_out = cv2.VideoCapture(str(output_mp4))
    out_psnrs = []
    n_compare = min(n_out, n_corr)
    # If agent_lo / agent_hi are invalid, treat as empty → score whole video.
    has_valid_agent = agent_hi >= agent_lo and agent_lo >= 0
    for fi in range(n_compare):
        if has_valid_agent and agent_lo <= fi <= agent_hi:
            continue
        cap_in.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ok1, in_f = cap_in.read()
        cap_out.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ok2, out_f = cap_out.read()
        if not ok1 or not ok2:
            continue
        try:
            out_psnrs.append(_psnr_y(in_f, out_f))
        except Exception:
            continue
    cap_in.release()
    cap_out.release()
    if out_psnrs:
        mean_psnr_out = float(np.mean(out_psnrs))
    else:
        # agent claimed whole video → treat as full credit.
        mean_psnr_out = 100.0
    out_score = _clip01(mean_psnr_out / 50.0)

    reward = 0.7 * quality_score + 0.2 * iou + 0.1 * out_score
    return {
        "reward": float(reward),
        "details": {
            "reason": "ok",
            "task_type": "sr-shot",
            "agent_range": [agent_lo, agent_hi],
            "gt_range": [gt_lo, gt_hi],
            "agent_json_err": agent_json_err,
            "localization_iou": iou,
            "in_shot": {
                "n_frames": len(psnrs),
                "mean_psnr_y_db": mean_psnr_in,
                "mean_ssim_y": mean_ssim_in,
                "psnr_n": psnr_n,
                "ssim_n": ssim_n,
                "quality_score": quality_score,
            },
            "preservation": {
                "n_compared": len(out_psnrs),
                "mean_psnr_db": mean_psnr_out,
                "out_score": out_score,
            },
            "weights": {"quality": 0.7, "iou": 0.2, "preservation": 0.1},
        },
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output-mp4", required=True, type=Path)
    p.add_argument("--output-json", required=True, type=Path)
    p.add_argument("--gt-shot-json", required=True, type=Path)
    p.add_argument("--corrupted", required=True, type=Path)
    p.add_argument("--original", required=True, type=Path)
    p.add_argument("--reward-json", required=True, type=Path)
    p.add_argument("--reward-txt", required=True, type=Path)
    args = p.parse_args()

    result = score(args.output_mp4, args.output_json, args.gt_shot_json,
                   args.corrupted, args.original)
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps(result, indent=2))
    args.reward_txt.write_text(f"{result['reward']:.6f}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
'''


SOLVE_SH_TEMPLATE = '''\
#!/bin/bash
# Oracle solver: Lanczos upscale on the baked-in GT shot range, passthrough
# (re-encode of source pixels) on bookend frames. Writes output.mp4 +
# output.json mirroring GT.
set -euo pipefail

mkdir -p /workspace/output /workspace/work

INPUT=/workspace/materials/corrupted.mp4
OUTPUT=/workspace/output/output.mp4
OUTPUT_JSON=/workspace/output/output.json

# Baked GT (zero-indexed inclusive frame range in corrupted.mp4):
START={start_frame}
END={end_frame}
FACTOR={factor}
WIDTH={width}
HEIGHT={height}
FPS_RAT="{fps_rational}"

# 1. Extract all frames as PNG.
WORK=/workspace/work/oracle
rm -rf "$WORK"
mkdir -p "$WORK/in" "$WORK/out"
ffmpeg -y -i "$INPUT" -vsync 0 "$WORK/in/%06d.png" 2>/dev/null

# 2. For each frame: in-shot → Lanczos downsample+upsample (best-in-class
#    canonical SR baseline); out-of-shot → copy.
python3 - <<'PY'
import cv2, os, sys
from pathlib import Path
W = {width}
H = {height}
F = {factor}
LO = {start_frame}
HI = {end_frame}
in_dir = Path("/workspace/work/oracle/in")
out_dir = Path("/workspace/work/oracle/out")
frames = sorted(in_dir.glob("*.png"))
for i, fp in enumerate(frames):
    dst = out_dir / fp.name
    img = cv2.imread(str(fp), cv2.IMREAD_COLOR)
    if LO <= i <= HI:
        # In-shot: the input is corrupted (bicubic upsampled from W/F x H/F).
        # We don't have the true HR, so we apply Lanczos resampling of the
        # corrupted frame at full res. (Doesn't help much, but applies a
        # subtle sharpening via Lanczos kernel reconstruction — beats
        # nothing.) Better strategy: downsample current corrupted W/F xH/F
        # then Lanczos-upsample. This recovers a slightly sharper view.
        small = cv2.resize(img, (W // F, H // F), interpolation=cv2.INTER_AREA)
        sr = cv2.resize(small, (W, H), interpolation=cv2.INTER_LANCZOS4)
        cv2.imwrite(str(dst), sr)
    else:
        # Out-of-shot: copy untouched.
        cv2.imwrite(str(dst), img)
print(f"oracle: processed {{len(frames)}} frames")
PY

# 3. Reassemble output.mp4 at source fps.
ffmpeg -y -framerate "$FPS_RAT" \\
    -i "$WORK/out/%06d.png" \\
    -c:v libx264 -pix_fmt yuv420p -preset veryfast \\
    -r "$FPS_RAT" -an \\
    "$OUTPUT" 2>/dev/null

# 4. Write output.json mirroring GT.
cat > "$OUTPUT_JSON" <<EOF
{{"start_frame": $START, "end_frame": $END}}
EOF

echo "oracle: wrote $OUTPUT ($START-$END Lanczos-restored) and $OUTPUT_JSON"
'''


# --------------------------------------------------------------- utilities
def _write_exec(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _run(cmd: list[str], quiet: bool = False) -> None:
    if not quiet:
        print(f"  $ {' '.join(cmd)}")
    res = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr, file=sys.stderr)
        raise RuntimeError(f"command failed: {cmd[0]}")


def _ffprobe_info(path: Path) -> dict:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames",
        "-count_frames",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ], text=True).strip().splitlines()
    # order: width, height, r_frame_rate, nb_read_frames
    return {
        "width": int(out[0]),
        "height": int(out[1]),
        "r_frame_rate": out[2].strip(),
        "n_frames": int(out[3]),
    }


def _fps_float(rate: str) -> float:
    if "/" in rate:
        num, den = rate.split("/", 1)
        return float(num) / float(den)
    return float(rate)


def _laplacian_var(frame_bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _detect_shots(clip_path: Path, threshold: float = 27.0) -> list[tuple[int, int]]:
    """Run PySceneDetect ContentDetector. Returns list of (start, end_exclusive)."""
    from scenedetect import detect, ContentDetector
    scenes = detect(str(clip_path), ContentDetector(threshold=threshold))
    shots = []
    for s, e in scenes:
        shots.append((s.frame_num, e.frame_num))
    return shots


def _pick_target_shot(
    clip_path: Path,
    shots: list[tuple[int, int]],
    *,
    min_len: int = 100,
    max_len: int = 200,
    skip_first: int = 1,
    skip_last: int = 1,
) -> tuple[int, int, float]:
    """Pick a high-detail shot of len ∈ [min_len, max_len], avoiding edges.

    Returns (start_frame_inclusive, end_frame_inclusive, mean_laplacian_var).
    If no shot in range is found, relax to the widest candidate.
    """
    n_shots = len(shots)
    cap = cv2.VideoCapture(str(clip_path))
    try:
        candidates = []
        for i, (s, e) in enumerate(shots):
            if i < skip_first or i >= n_shots - skip_last:
                continue
            length = e - s
            if length < min_len or length > max_len:
                continue
            # Sample 3 frames for sharpness estimate.
            mids = [s + length // 4, s + length // 2, s + 3 * length // 4]
            scores = []
            for m in mids:
                cap.set(cv2.CAP_PROP_POS_FRAMES, m)
                ok, frame = cap.read()
                if ok:
                    scores.append(_laplacian_var(frame))
            if not scores:
                continue
            candidates.append((i, s, e, length, float(np.mean(scores))))
        if not candidates:
            # Relax: take any non-edge shot of length >= 80, prefer 100-200.
            for i, (s, e) in enumerate(shots):
                if i < skip_first or i >= n_shots - skip_last:
                    continue
                length = e - s
                if length < 80:
                    continue
                mids = [s + length // 4, s + length // 2, s + 3 * length // 4]
                scores = []
                for m in mids:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, m)
                    ok, frame = cap.read()
                    if ok:
                        scores.append(_laplacian_var(frame))
                if scores:
                    candidates.append((i, s, e, length, float(np.mean(scores))))
        if not candidates:
            raise RuntimeError("no suitable target shot found")
        # Pick highest mean Laplacian-variance (sharpest, most-detailed shot).
        candidates.sort(key=lambda c: -c[4])
        i, s, e, length, sharp = candidates[0]
        # GT range is inclusive on both ends; shots are [s, e). Convert.
        return (s, e - 1, sharp)
    finally:
        cap.release()


def _build_corrupted_video(
    clip_path: Path,
    out_path: Path,
    *,
    fps_rational: str,
    width: int,
    height: int,
    factor: int,
    gt_start: int,
    gt_end_inclusive: int,
) -> None:
    """Read all frames; for frames in [gt_start, gt_end_inclusive]:
       downsample W/F xH/F via bicubic, re-upsample to WxH via bicubic.
       For other frames: write the source frame untouched.
       Reassemble at source fps."""
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        in_dir = tmp / "in"
        out_dir = tmp / "out"
        in_dir.mkdir()
        out_dir.mkdir()
        # 1. extract all frames to PNG
        _run([
            "ffmpeg", "-y", "-i", str(clip_path),
            "-vsync", "0",
            str(in_dir / "%06d.png"),
        ], quiet=True)
        frames = sorted(in_dir.glob("*.png"))
        if not frames:
            raise RuntimeError("ffmpeg extracted no frames from clip")
        n = len(frames)
        small_w = max(1, width // factor)
        small_h = max(1, height // factor)
        for i, fp in enumerate(frames):
            img = cv2.imread(str(fp), cv2.IMREAD_COLOR)
            if img is None:
                raise RuntimeError(f"could not read frame {fp}")
            if gt_start <= i <= gt_end_inclusive:
                small = cv2.resize(img, (small_w, small_h),
                                   interpolation=cv2.INTER_CUBIC)
                big = cv2.resize(small, (width, height),
                                 interpolation=cv2.INTER_CUBIC)
                cv2.imwrite(str(out_dir / fp.name), big)
            else:
                # bytes-identical not preserved through PNG round-trip but
                # pixel-identical is fine; later H.264 encode is lossy anyway.
                cv2.imwrite(str(out_dir / fp.name), img)
        # 2. encode at source fps
        _run([
            "ffmpeg", "-y",
            "-framerate", fps_rational,
            "-i", str(out_dir / "%06d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
            "-r", fps_rational, "-an",
            str(out_path),
        ], quiet=True)


@dataclass
class SrShotSpec:
    task_name: str
    source_mp4: Path
    factor: int                   # 2 or 4
    clip_start_sec: float
    clip_duration_sec: float
    prompt: str
    # Optional pre-picked target shot (inclusive frame indices into the
    # extracted clip). If None, we auto-pick.
    target_start: int | None = None
    target_end: int | None = None


def build_task(spec: SrShotSpec) -> dict:
    task_dir = TASKS_DIR / spec.task_name
    if task_dir.exists():
        shutil.rmtree(task_dir)
    task_dir.mkdir(parents=True)

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        clip = tmp / "clip.mp4"

        # ---- 1. extract 60s clip at source resolution + fps ----
        src_info = _ffprobe_info(spec.source_mp4)
        fps_rational = src_info["r_frame_rate"]
        # Decode + re-encode losslessly-ish to constant fps with libx264.
        _run([
            "ffmpeg", "-y",
            "-ss", str(spec.clip_start_sec),
            "-t", str(spec.clip_duration_sec),
            "-i", str(spec.source_mp4),
            "-an",
            "-r", fps_rational,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
            "-crf", "16",
            str(clip),
        ])

        clip_info = _ffprobe_info(clip)
        width, height = clip_info["width"], clip_info["height"]
        n_clip = clip_info["n_frames"]
        fps_f = _fps_float(fps_rational)
        print(f"  clip: {width}x{height}, {n_clip} frames, fps={fps_rational} ({fps_f:.3f})")

        # ---- 2. detect shots, pick target ----
        if spec.target_start is None or spec.target_end is None:
            shots = _detect_shots(clip)
            print(f"  detected {len(shots)} shots in clip")
            for i, (s, e) in enumerate(shots):
                print(f"    shot {i:2d}: [{s:4d}, {e:4d})  ({e - s} frames)")
            tgt_s, tgt_e, sharp = _pick_target_shot(clip, shots)
            print(f"  picked shot [{tgt_s}, {tgt_e}] (len={tgt_e - tgt_s + 1})  "
                  f"laplacian_var={sharp:.1f}")
        else:
            tgt_s, tgt_e = spec.target_start, spec.target_end
            sharp = 0.0
            shots = []
            print(f"  using user-pinned shot [{tgt_s}, {tgt_e}]")

        # ---- 3. build corrupted.mp4 ----
        corrupted = tmp / "corrupted.mp4"
        _build_corrupted_video(
            clip, corrupted,
            fps_rational=fps_rational,
            width=width, height=height,
            factor=spec.factor,
            gt_start=tgt_s,
            gt_end_inclusive=tgt_e,
        )
        corr_info = _ffprobe_info(corrupted)
        print(f"  corrupted: {corr_info['width']}x{corr_info['height']}, "
              f"{corr_info['n_frames']} frames")

        # ---- 4. write Harbor task dir ----
        env = task_dir / "environment"
        env.mkdir(parents=True, exist_ok=True)
        (env / "Dockerfile").write_text(DOCKERFILE)

        ds_filter = f"iw/{spec.factor}:ih/{spec.factor}"
        factor_tag = f"{spec.factor}x-downsample"
        (task_dir / "task.toml").write_text(TASK_TOML.format(
            task_name=spec.task_name,
            factor_tag=factor_tag,
            source_name=spec.source_mp4.name,
            corruption_desc=(
                f"shot-scoped SR: target shot [{tgt_s}, {tgt_e}] in 60s clip "
                f"downsampled {spec.factor}× (bicubic) then re-upsampled "
                f"bicubic to {width}×{height}; agent must localise + restore"
            ),
        ))

        step = task_dir / "steps" / "solve"
        step.mkdir(parents=True, exist_ok=True)

        (step / "instruction.md").write_text(INSTRUCTION_TEMPLATE.format(
            factor=spec.factor,
            duration_s=int(round(spec.clip_duration_sec)),
            fps_int=int(round(fps_f)),
            width=width, height=height,
            ds_filter=ds_filter,
        ))

        workdir = step / "workdir"
        workdir.mkdir(parents=True, exist_ok=True)
        shutil.copy(corrupted, workdir / "corrupted.mp4")
        (workdir / "prompt.txt").write_text(spec.prompt + "\n")
        _write_exec(workdir / "setup.sh", SETUP_SH)

        tests = step / "tests"
        tests.mkdir(parents=True, exist_ok=True)
        shutil.copy(clip, tests / "original.mp4")
        gt_payload = {
            "start_frame": int(tgt_s),
            "end_frame": int(tgt_e),
            "downsample_factor": int(spec.factor),
            "clip_width": width,
            "clip_height": height,
            "clip_n_frames": n_clip,
            "fps_rational": fps_rational,
        }
        (tests / "gt_shot.json").write_text(json.dumps(gt_payload, indent=2))
        _write_exec(tests / "test.sh", TEST_SH)
        _write_exec(tests / "judge.py", JUDGE_PY)

        solution = step / "solution"
        solution.mkdir(parents=True, exist_ok=True)
        _write_exec(solution / "solve.sh", SOLVE_SH_TEMPLATE.format(
            start_frame=int(tgt_s),
            end_frame=int(tgt_e),
            factor=spec.factor,
            width=width, height=height,
            fps_rational=fps_rational,
        ))
        # Also keep a copy of gt_shot.json next to solve.sh for diagnostics
        # (oracle reads baked vars, not this file, but it's handy).
        (solution / "gt_shot.json").write_text(json.dumps(gt_payload, indent=2))

        summary = {
            "task_name": spec.task_name,
            "task_dir": str(task_dir),
            "source": str(spec.source_mp4),
            "clip_start_sec": spec.clip_start_sec,
            "clip_duration_sec": spec.clip_duration_sec,
            "factor": spec.factor,
            "clip_size": [width, height],
            "clip_n_frames": n_clip,
            "fps_rational": fps_rational,
            "shots_detected": len(shots),
            "target_shot": [int(tgt_s), int(tgt_e)],
            "target_shot_len": int(tgt_e - tgt_s + 1),
            "target_shot_sharpness_lap_var": float(sharp),
            "prompt": spec.prompt,
        }
        print(json.dumps(summary, indent=2))
        return summary
