"""Shared core for shot-swap restoration task generators.

Pattern: clip a multi-shot segment from a source video, detect shots
with PySceneDetect, pick 2 non-adjacent visually distinct shots of
similar length and swap them. The corrupted video has these shots in
swapped temporal order; the agent must restore the original order.

Pipeline:
  1. Clip source at given offset/duration, scale to 480p, normalise fps.
  2. Run PySceneDetect (content-aware) on the clip -> shot list.
  3. Pick 2 swap shots with constraints: both >= 60 frames, non-adjacent,
     not first/last, similar length (within +/-20%), visually distinct
     (color-histogram chi-sq distance above a floor).
  4. Build per-shot segment mp4s via ffmpeg -ss/-t re-encode.
  5. Concat in two orders: original (-> tests/original.mp4) and
     swapped (-> workdir/corrupted.mp4) using the concat demuxer +
     re-encode (concat copy fails when timestamps differ).
  6. Emit gt_swap.json with frame ranges in BOTH the original and the
     corrupted/swapped timelines.
  7. Vendor the full Harbor task dir: task.toml, Dockerfile, instruction,
     setup, tests (judge.py + test.sh + original.mp4 + gt_swap.json),
     solution (oracle solve.sh + gt_swap.json).

Used by:
  build_swap_car.py
  build_swap_product.py
"""
from __future__ import annotations

import csv
import json
import math
import random
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent  # experiment/
TASKS_DIR = REPO_ROOT / "tasks" / "agentic_vbench_repair"
SOURCES_DIR = REPO_ROOT / "sources"

SEED = 42
TARGET_HEIGHT = 480
MIN_SHOT_FRAMES = 60
LENGTH_TOL = 0.20  # +/-20% length match between the two swapped shots
MIN_HIST_DIST = 0.30  # min chi-sq normalised color hist distance


TASK_TOML = """\
version = "1.0"

[task]
name = "agentic-vbench/{task_name}"

[metadata]
difficulty = "medium"
category = "video-shot-restoration"
tags = ["shot-swap", "shot-reorder", "video-restoration", "shot-boundary"]
source = "{source_name}"
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
timeout_sec = 1800.0

[steps.verifier]
timeout_sec = 600.0
"""


DOCKERFILE = """\
FROM --platform=linux/amd64 python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \\
        ffmpeg curl ca-certificates gcc g++ python3-dev \\
        libgl1 libglib2.0-0 \\
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \\
        "numpy<3" \\
        "opencv-python-headless==4.13.*"

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
"""


INSTRUCTION_MD = """\
# Shot-Swap Restoration

`/workspace/materials/corrupted.mp4` is a ~{duration_s}s {fps_int} fps
multi-shot video. **Two non-adjacent shots have been swapped out of
temporal order.** Every other shot is in its original position; only
those two shots have been exchanged.

## Your job

1. Detect the two swapped shots (e.g. via shot-boundary detection +
   visual continuity analysis).
2. Produce a video at `/workspace/output/output.mp4` that **restores the
   original temporal order of all shots**.
3. Emit a JSON report at `/workspace/output/output.json`:

```json
{{
  "swap": [
    {{"corrupted_start": Sa, "corrupted_end": Ea}},
    {{"corrupted_start": Sb, "corrupted_end": Eb}}
  ]
}}
```

`corrupted_start` / `corrupted_end` are **0-indexed frame numbers in the
corrupted input** (inclusive start, exclusive end) describing where each
swapped shot currently sits in the corrupted timeline. Order within the
list does not matter.

## Output format

- `/workspace/output/output.mp4`: H.264 / yuv420p video + AAC 48 kHz
  stereo audio, same fps + resolution + duration as input. The audio
  track must be reordered in lock-step with the video (swap-A's audio
  travels with swap-A's video).
- `/workspace/output/output.json`: as above.

## Scoring

Primary: **whole-video PSNR** against the original-order reference. If
you correctly restore the shot order, your output matches the reference
closely (high PSNR); if not, content mismatch in the two swapped regions
drives PSNR down. The score is normalised: mean PSNR in [10 dB, 40 dB]
mapped to [0, 1]. (Audio is not part of the score, but is included in
both the corrupted input and the reference so you can use audio cues to
identify the swap.)

Secondary (diagnostic, not in composite): IoU between your reported swap
ranges and the ground-truth swap ranges.

## Notes

- Container has internet. CPU only; ~30 minute timeout.
- Available libs: `ffmpeg`, `opencv-python-headless`, `numpy`. Install
  more if needed via `pip install` (e.g. `scenedetect`).
- The two swapped shots are non-adjacent (at least one other shot sits
  between them in the original order) and are visually distinct from
  each other.
- Audio cues (engine notes, voice-over phrasing, music continuity) are a
  reliable secondary signal for locating the swap.
- Use `/workspace/work/` for scratch.
"""


SETUP_SH = """\
#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

mkdir -p /workspace/materials /workspace/output /workspace/work
cp "$HERE/corrupted.mp4" /workspace/materials/corrupted.mp4

if [ ! -s /workspace/materials/corrupted.mp4 ]; then
    echo "ERROR: corrupted.mp4 missing or empty" >&2
    exit 1
fi

if [ -f "$HERE/prompt.txt" ]; then
    cp "$HERE/prompt.txt" /workspace/materials/prompt.txt
fi

mkdir -p /logs/artifacts
ffprobe -v error -show_entries stream=nb_read_frames,r_frame_rate,duration \\
        -count_frames -select_streams v:0 \\
        /workspace/materials/corrupted.mp4 \\
        > /logs/artifacts/input-probe.txt 2>&1 || true

rm -rf -- "$HERE/corrupted.mp4" "$HERE/prompt.txt" "$0"
"""


TEST_SH = """\
#!/bin/bash
# Verifier: whole-video PSNR vs original-order reference + diagnostic
# detection IoU.
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts

if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

python3 -c "import cv2, numpy" 2>/dev/null || \\
    pip install --quiet --no-cache-dir "numpy<3" "opencv-python-headless==4.13.*"

python3 /tests/judge.py \\
        --output-mp4 /workspace/output/output.mp4 \\
        --output-json /workspace/output/output.json \\
        --original /tests/original.mp4 \\
        --gt-swap-json /tests/gt_swap.json \\
        --reward-json /logs/verifier/reward.json \\
        --reward-txt /logs/verifier/reward.txt
"""


JUDGE_PY = '''\
#!/usr/bin/env python3
"""Shot-swap restoration judge.

Composite reward = whole-video mean PSNR (output.mp4 vs original.mp4),
normalised to [0, 1] via linear map of [10, 40] dB.

Diagnostics (NOT in composite, reported in details):
- detection_score: IoU between agent-reported swap ranges and GT swap
  ranges in the corrupted timeline (Hungarian-style best match, 2 pairs).
- length penalty applied if output length differs from reference by
  more than 10%.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

PSNR_LO = 10.0
PSNR_HI = 40.0
LEN_TOL = 0.10  # 10% length deviation = heavy penalty


def zero(reason: str) -> dict:
    return {"reward": 0.0, "details": {"reason": reason}}


def open_video(path: Path) -> tuple[cv2.VideoCapture, int, int, int]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return cap, 0, 0, 0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    return cap, n, w, h


def frame_mse(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]))
    diff = a.astype(np.float64) - b.astype(np.float64)
    return float(np.mean(diff * diff))


def psnr_from_mse(mse: float) -> float:
    if mse <= 1e-10:
        return 99.0
    return 20.0 * np.log10(255.0) - 10.0 * np.log10(mse)


def interval_iou(a: tuple[int, int], b: tuple[int, int]) -> float:
    s1, e1 = a; s2, e2 = b
    if e1 <= s1 or e2 <= s2:
        return 0.0
    inter = max(0, min(e1, e2) - max(s1, s2))
    union = max(e1, e2) - min(s1, s2)
    return inter / union if union > 0 else 0.0


def best_pair_iou(pred: list[tuple[int, int]],
                  gt: list[tuple[int, int]]) -> tuple[float, list]:
    # Match 2 pred ranges to 2 GT ranges, max sum-IoU.
    if not pred:
        return 0.0, []
    # Truncate pred to first 4 to keep brute force small.
    pred = pred[:4]
    best = 0.0
    best_match = []
    n_gt = len(gt)
    # Enumerate all assignments of pred[i] to gt[j] (at most n_gt picks).
    from itertools import permutations
    for perm in permutations(range(len(pred)), n_gt):
        ious = [interval_iou(pred[perm[k]], gt[k]) for k in range(n_gt)]
        s = sum(ious)
        if s > best:
            best = s
            best_match = [
                {"pred_idx": int(perm[k]), "gt_idx": k,
                 "pred": list(pred[perm[k]]), "gt": list(gt[k]),
                 "iou": float(ious[k])}
                for k in range(n_gt)
            ]
    return best / max(1, n_gt), best_match


def read_all_frames(path: Path, max_w: int = 640) -> tuple[list, tuple[int, int]]:
    cap = cv2.VideoCapture(str(path))
    frames = []
    if not cap.isOpened():
        return frames, (0, 0)
    w0 = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h0 = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if w0 > max_w:
        scale = max_w / w0
        w = max_w
        h = int(round(h0 * scale))
    else:
        w, h = w0, h0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if (w, h) != (frame.shape[1], frame.shape[0]):
                frame = cv2.resize(frame, (w, h))
            frames.append(frame)
    finally:
        cap.release()
    return frames, (w, h)


def score(output_mp4: Path, output_json: Path, original: Path,
          gt_swap_json: Path) -> dict:
    if not original.exists():
        return zero(f"missing reference {original}")
    if not gt_swap_json.exists():
        return zero(f"missing gt_swap.json {gt_swap_json}")
    if not output_mp4.exists():
        return zero("no output.mp4")

    gt_blob = json.loads(gt_swap_json.read_text())
    gt_ranges_corrupted = [
        (int(s["corrupted_start"]), int(s["corrupted_end"]))
        for s in gt_blob.get("swap", [])
    ]

    ref_frames, _ = read_all_frames(original)
    out_frames, _ = read_all_frames(output_mp4)
    if not ref_frames:
        return zero("could not read reference frames")
    if not out_frames:
        return zero("could not read output frames")

    n_ref = len(ref_frames)
    n_out = len(out_frames)
    len_dev = abs(n_out - n_ref) / max(1, n_ref)
    n_common = min(n_ref, n_out)

    # Aggregate MSE across frames (linear domain), then convert to PSNR.
    # Aggregating in dB underweights bad frames; e.g. if 10% of frames
    # are at 6 dB and 90% at 50 dB the *log* mean is 45 dB but the true
    # signal-noise ratio is closer to 16 dB. The latter is what we want.
    mses = []
    for i in range(n_common):
        mses.append(frame_mse(ref_frames[i], out_frames[i]))
    mean_mse = float(np.mean(mses)) if mses else float("inf")
    mean_psnr = psnr_from_mse(mean_mse)
    # Per-frame log-PSNR is reported as a diagnostic only.
    per_frame_psnr = [psnr_from_mse(m) for m in mses]
    log_mean_psnr = float(np.mean(per_frame_psnr)) if per_frame_psnr else 0.0
    psnr_n = float(np.clip((mean_psnr - PSNR_LO) / (PSNR_HI - PSNR_LO), 0.0, 1.0))

    # Heavy length-deviation penalty: if >10% off, halve psnr_n contribution.
    if len_dev > LEN_TOL:
        length_penalty = max(0.0, 1.0 - (len_dev - LEN_TOL) * 2.0)
    else:
        length_penalty = 1.0

    reward = psnr_n * length_penalty

    # Diagnostic detection: parse agent output.json swap ranges.
    detection_score = 0.0
    detection_matches: list = []
    pred_ranges: list[tuple[int, int]] = []
    if output_json.exists():
        try:
            pred_blob = json.loads(output_json.read_text())
            for s in pred_blob.get("swap", []):
                try:
                    pred_ranges.append((int(s["corrupted_start"]),
                                        int(s["corrupted_end"])))
                except Exception:
                    continue
        except Exception:
            pass
    if pred_ranges and gt_ranges_corrupted:
        detection_score, detection_matches = best_pair_iou(
            pred_ranges, gt_ranges_corrupted)

    return {
        "reward": float(reward),
        "details": {
            "reason": "ok",
            "overall_psnr_db": mean_psnr,
            "log_mean_psnr_db_diag": log_mean_psnr,
            "mean_mse": mean_mse,
            "psnr_normalised": psnr_n,
            "length_penalty": length_penalty,
            "n_ref_frames": n_ref,
            "n_out_frames": n_out,
            "length_deviation": len_dev,
            "detection_score_diag": detection_score,
            "detection_matches_diag": detection_matches,
            "gt_swap_ranges_corrupted": [list(r) for r in gt_ranges_corrupted],
            "pred_swap_ranges_corrupted": [list(r) for r in pred_ranges],
            "psnr_lo": PSNR_LO,
            "psnr_hi": PSNR_HI,
        },
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output-mp4", required=True, type=Path)
    p.add_argument("--output-json", required=True, type=Path)
    p.add_argument("--original", required=True, type=Path)
    p.add_argument("--gt-swap-json", required=True, type=Path)
    p.add_argument("--reward-json", required=True, type=Path)
    p.add_argument("--reward-txt", required=True, type=Path)
    args = p.parse_args()

    result = score(args.output_mp4, args.output_json, args.original,
                   args.gt_swap_json)
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps(result, indent=2))
    args.reward_txt.write_text(f"{result['reward']:.6f}\\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


# Oracle solve: reads gt_swap.json, uses ffmpeg concat to restore the
# original shot order from the corrupted input. The corrupted timeline
# is segmented at the boundaries listed in gt_swap.json: we identify the
# two swap ranges plus all the unchanged regions, then concat in the
# correct original order.
SOLVE_SH = '''\
#!/bin/bash
# Oracle: read baked-in gt_swap.json, restore the original shot order
# by chopping the corrupted video into segments at the recorded
# boundaries and concatenating in the right order.
set -euo pipefail

mkdir -p /workspace/output /workspace/work

INPUT=/workspace/materials/corrupted.mp4
OUTPUT=/workspace/output/output.mp4
OUTPUT_JSON=/workspace/output/output.json

# gt_swap.json is shipped alongside solve.sh in /workspace/solution/.
HERE="$(cd "$(dirname "$0")" && pwd)"
GT="$HERE/gt_swap.json"

python3 - "$INPUT" "$GT" /workspace/work "$OUTPUT" "$OUTPUT_JSON" <<'PY'
import json, subprocess, sys
from pathlib import Path

inp, gt_path, workdir, out_mp4, out_json = sys.argv[1:6]
workdir = Path(workdir); workdir.mkdir(parents=True, exist_ok=True)

gt = json.loads(Path(gt_path).read_text())
fps_num, fps_den = gt["fps_num"], gt["fps_den"]
total_corrupted = gt["total_corrupted_frames"]

# Build the segment plan in the *corrupted* timeline: a sorted list of
# (start, end) covering all of [0, total_corrupted), with the two swap
# ranges marked.
swap = sorted([(int(s["corrupted_start"]), int(s["corrupted_end"]))
               for s in gt["swap"]])
sA, eA = swap[0]
sB, eB = swap[1]
assert eA <= sB, "swap ranges overlap"

segments = []
cursor = 0
for sx, ex in [(sA, eA), (sB, eB)]:
    if cursor < sx:
        segments.append({"cs": cursor, "ce": sx, "kind": "fixed"})
    segments.append({"cs": sx, "ce": ex, "kind": "swap"})
    cursor = ex
if cursor < total_corrupted:
    segments.append({"cs": cursor, "ce": total_corrupted, "kind": "fixed"})

# To restore original order: swap-A and swap-B are currently in the
# wrong slots. Swap them back: take the segment in slot of swap-A but
# play the content of swap-B, and vice versa. With concat demuxer we
# just need to extract each frame range to its own mp4 and concat.
fps = float(fps_num) / float(fps_den)
def to_t(n): return n / fps

# Write per-segment mp4s.
seg_paths = []
for i, s in enumerate(segments):
    cs, ce = s["cs"], s["ce"]
    seg_path = workdir / f"seg_{i:03d}.mp4"
    n_frames = ce - cs
    # -ss must come AFTER -i on the concat-demuxed corrupted.mp4: input-side
    # fast-seek misses the requested frame on a concat-merged stream even
    # though every frame is a keyframe. Output-side seek is exact.
    cmd = [
        "ffmpeg", "-y",
        "-i", inp,
        "-ss", f"{to_t(cs):.6f}",
        "-frames:v", str(n_frames),
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        str(seg_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    seg_paths.append((i, seg_path, s["kind"]))

# Build the *restoration* order. Walk segments in corrupted order; for
# the first swap slot (sA..eA) play swap-B; for the second swap slot
# (sB..eB) play swap-A. Fixed segments stay put.
swap_indices = [i for i, _, k in seg_paths if k == "swap"]
assert len(swap_indices) == 2
idx_A, idx_B = swap_indices

restored = []
for i, p, k in seg_paths:
    if i == idx_A:
        restored.append(seg_paths[idx_B][1])
    elif i == idx_B:
        restored.append(seg_paths[idx_A][1])
    else:
        restored.append(p)

# Concat re-encode (concat copy can break with different streams).
list_file = workdir / "concat.txt"
list_file.write_text("\\n".join(f"file '{p.as_posix()}'" for p in restored) + "\\n")
subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
    "-c", "copy",
    out_mp4,
], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Write output.json: mirror GT swap ranges (corrupted timeline).
Path(out_json).write_text(json.dumps({
    "swap": [
        {"corrupted_start": sA, "corrupted_end": eA},
        {"corrupted_start": sB, "corrupted_end": eB},
    ]
}, indent=2))
print(f"oracle: wrote {out_mp4} and {out_json}")
PY
'''


# ---------------------------------------------------------------- helpers

def _write_exec(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _run(cmd: list[str]) -> None:
    print(f"  $ {' '.join(cmd)}")
    res = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr, file=sys.stderr)
        raise RuntimeError(f"command failed: {cmd[0]}")


def _ffprobe_fps(path: Path) -> tuple[int, int, float]:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ], text=True).strip()
    if "/" in out:
        num, den = out.split("/", 1)
        return int(num), int(den), int(num) / int(den)
    return int(out), 1, float(out)


def _count_frames(path: Path) -> int:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-count_frames", "-show_entries", "stream=nb_read_frames",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ], text=True).strip()
    return int(out)


def _duration(path: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ], text=True).strip()
    return float(out)


@dataclass
class Shot:
    idx: int       # 1-indexed scene number (PySceneDetect convention)
    start: int     # inclusive (0-indexed)
    end: int       # exclusive (0-indexed)

    @property
    def length(self) -> int:
        return self.end - self.start


def _detect_shots(clip: Path, scenedetect_workdir: Path) -> list[Shot]:
    scenedetect_workdir.mkdir(parents=True, exist_ok=True)
    csv_name = "scenes.csv"
    _run([
        "scenedetect", "-i", str(clip),
        "detect-content",
        "list-scenes", "-f", csv_name,
        "-o", str(scenedetect_workdir),
    ])
    csv_path = scenedetect_workdir / csv_name
    # PySceneDetect writes a header line "Timecode List:..." then a normal
    # CSV. Skip until "Scene Number" header.
    rows = []
    with csv_path.open() as f:
        reader = csv.reader(f)
        in_data = False
        for row in reader:
            if not row:
                continue
            if row[0] == "Scene Number":
                in_data = True
                continue
            if in_data:
                rows.append(row)
    shots: list[Shot] = []
    for r in rows:
        # PySceneDetect: Scene Number, Start Frame (1-indexed), Start TC,
        # Start Time (s), End Frame, End TC, End Time (s), Length frames,
        # Length tc, Length seconds.
        idx = int(r[0])
        start_1 = int(r[1])
        end_1 = int(r[4])
        # Convert to 0-indexed half-open: [start_1 - 1, end_1).
        shots.append(Shot(idx=idx, start=start_1 - 1, end=end_1))
    return shots


def _shot_hist(clip: Path, shot: Shot, fps: float) -> "np.ndarray":
    import cv2  # noqa
    import numpy as np  # noqa
    cap = cv2.VideoCapture(str(clip))
    if not cap.isOpened():
        raise RuntimeError(f"cv2 cannot open {clip}")
    try:
        # Sample middle frame of shot.
        mid = (shot.start + shot.end) // 2
        cap.set(cv2.CAP_PROP_POS_FRAMES, mid)
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError(f"cannot read frame {mid} from {clip}")
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
        hist = cv2.normalize(hist, hist).flatten()
        return hist
    finally:
        cap.release()


def _pick_swap_shots(shots: list[Shot], clip: Path, fps: float,
                     seed: int) -> tuple[Shot, Shot, dict]:
    """Pick 2 non-adjacent, similar-length, visually distinct shots."""
    import numpy as np  # noqa
    import cv2  # noqa
    # Eligible: not first/last, length >= MIN_SHOT_FRAMES.
    pool = [s for s in shots[1:-1] if s.length >= MIN_SHOT_FRAMES]
    if len(pool) < 4:
        raise RuntimeError(f"not enough eligible shots (need >=4, got {len(pool)})")

    rng = random.Random(seed)
    # Precompute hists for the pool.
    hists = {s.idx: _shot_hist(clip, s, fps) for s in pool}

    # Score all valid (a, b) candidate pairs: non-adjacent in `shots`
    # ordering, length within +/-20%, hist distance >= MIN_HIST_DIST.
    candidates: list[tuple[Shot, Shot, float, float]] = []
    pool_by_idx = {s.idx: s for s in pool}
    for i, a in enumerate(pool):
        for b in pool[i + 1:]:
            if abs(b.idx - a.idx) < 2:
                continue  # adjacent
            la, lb = a.length, b.length
            ratio = min(la, lb) / max(la, lb)
            if ratio < (1 - LENGTH_TOL):
                continue
            ha = hists[a.idx]; hb = hists[b.idx]
            # cv2.HISTCMP_BHATTACHARYYA: 0 = identical, 1 = max distinct.
            dist = float(cv2.compareHist(ha, hb, cv2.HISTCMP_BHATTACHARYYA))
            if dist < MIN_HIST_DIST:
                continue
            # Score: prefer high dist (visual distinctiveness) and
            # balanced length. Multiply dist by ratio for tie-break.
            score = dist + 0.3 * ratio
            candidates.append((a, b, dist, score))

    if not candidates:
        raise RuntimeError("no candidate shot pairs satisfy constraints")

    candidates.sort(key=lambda c: c[3], reverse=True)
    # Take top-K and pick one with seeded RNG for reproducible jitter.
    topk = candidates[: min(8, len(candidates))]
    a, b, dist, score = rng.choice(topk)
    if a.start > b.start:
        a, b = b, a
    meta = {
        "n_candidates": len(candidates),
        "picked_score": score,
        "picked_hist_dist": dist,
        "topk_summary": [
            {"a_idx": c[0].idx, "b_idx": c[1].idx, "dist": c[2], "score": c[3]}
            for c in topk
        ],
    }
    return a, b, meta


def build_task(
    *,
    task_name: str,
    source_mp4: Path,
    clip_offset_sec: float,
    clip_duration_sec: float,
    target_fps_rational: str,
    instruction_hint: str = "",
) -> dict:
    """Build one shot-swap restoration Harbor task dir.

    Returns a build summary dict.
    """
    task_dir = TASKS_DIR / task_name
    if task_dir.exists():
        shutil.rmtree(task_dir)
    task_dir.mkdir(parents=True)

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)

        # ---- 1. Make the clip (this BECOMES the original-order reference).
        # All-keyframe (GOP=1) video + AAC audio so subsequent per-segment
        # extraction and concat can both stream-copy. The build pipeline is
        # then bit-perfect: clip → segs → concat(original|corrupted) all via
        # -c copy. Oracle extracting from corrupted is also stream-copy, so
        # oracle output should match the reference end-to-end.
        clip = tmp / "clip.mp4"
        fps_num, fps_den = map(int, target_fps_rational.split("/"))
        _run([
            "ffmpeg", "-y",
            "-ss", str(clip_offset_sec),
            "-t", str(clip_duration_sec),
            "-i", str(source_mp4),
            "-vf", f"scale=-2:{TARGET_HEIGHT}",
            "-r", target_fps_rational,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
            "-g", "1", "-keyint_min", "1", "-x264-params", "scenecut=0",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "128k",
            str(clip),
        ])

        # ---- 2. Detect shots on the clip.
        shots = _detect_shots(clip, tmp / "scenes")
        n_total_frames = _count_frames(clip)
        fps = fps_num / fps_den
        print(f"  detected {len(shots)} shots in {n_total_frames}-frame clip")

        # ---- 3. Pick swap shots.
        shot_a, shot_b, pick_meta = _pick_swap_shots(shots, clip, fps, SEED)
        print(f"  swap shot A: idx={shot_a.idx} frames [{shot_a.start}, {shot_a.end})"
              f" len={shot_a.length}")
        print(f"  swap shot B: idx={shot_b.idx} frames [{shot_b.start}, {shot_b.end})"
              f" len={shot_b.length}")

        # ---- 4. Build per-segment mp4s in the *original* timeline. The
        # segment plan is the entire timeline split at shot_a/shot_b
        # boundaries (and the fixed regions in between/around).
        seg_plan: list[dict] = []  # entries: {"start","end","kind": "fixed"|"a"|"b"}
        cursor = 0
        for s, kind in [(shot_a, "a"), (shot_b, "b")]:
            if cursor < s.start:
                seg_plan.append({"start": cursor, "end": s.start, "kind": "fixed"})
            seg_plan.append({"start": s.start, "end": s.end, "kind": kind})
            cursor = s.end
        if cursor < n_total_frames:
            seg_plan.append({"start": cursor, "end": n_total_frames, "kind": "fixed"})

        seg_dir = tmp / "segs"
        seg_dir.mkdir()

        def _extract(start: int, end: int, dst: Path) -> None:
            # Stream-copy extraction: clip.mp4 is all-keyframe so we can
            # slice without re-encoding. Bit-perfect → concat-copy in the
            # next step preserves frames byte-for-byte.
            t_start = start / fps
            n_frames = end - start
            _run([
                "ffmpeg", "-y",
                "-ss", f"{t_start:.6f}",
                "-i", str(clip),
                "-frames:v", str(n_frames),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                str(dst),
            ])

        for i, seg in enumerate(seg_plan):
            dst = seg_dir / f"seg_{i:03d}_{seg['kind']}.mp4"
            _extract(seg["start"], seg["end"], dst)
            seg["path"] = dst

        # ---- 5. Compose original.mp4 (in-order concat). The reference is
        # the *re-encoded concat* of segments — not the raw clip — so that
        # the corrupted/original both go through identical re-encode and
        # PSNR is not floored by codec mismatch.
        def _concat(segments: list[dict], out: Path) -> None:
            list_file = tmp / f"concat_{out.stem}.txt"
            list_file.write_text(
                "\n".join(f"file '{Path(s['path']).as_posix()}'"
                         for s in segments) + "\n"
            )
            # Stream-copy concat: all segments come from an all-IDR clip
            # with identical x264/AAC parameters, so no re-encode needed.
            _run([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_file),
                "-c", "copy",
                str(out),
            ])

        original_mp4 = tmp / "original.mp4"
        _concat(seg_plan, original_mp4)

        # ---- 6. Build corrupted: same plan but swap the 'a' and 'b'
        # segment contents (keep slot order).
        a_seg = next(s for s in seg_plan if s["kind"] == "a")
        b_seg = next(s for s in seg_plan if s["kind"] == "b")
        a_path, b_path = a_seg["path"], b_seg["path"]

        swapped_plan = []
        for s in seg_plan:
            if s["kind"] == "a":
                swapped_plan.append({**s, "path": b_path})  # play B in A's slot
            elif s["kind"] == "b":
                swapped_plan.append({**s, "path": a_path})  # play A in B's slot
            else:
                swapped_plan.append(s)
        corrupted_mp4 = tmp / "corrupted.mp4"
        _concat(swapped_plan, corrupted_mp4)

        # ---- 7. Compute corrupted-timeline ranges of the two swap shots.
        # In the corrupted output, the slot at A's start..A's start + len_B
        # holds shot B; the slot at A.end + (b.start - a.end) + len_A holds
        # shot A. But we re-encoded each segment so the corrupted timeline
        # frame count = sum of segment frame counts in swapped plan. Build
        # per-segment cumulative frame counts (from actual encoded files,
        # to be exact in case of any rounding).
        def _seg_frames(p: Path) -> int:
            return _count_frames(p)

        corrupted_total = 0
        corrupted_offsets: list[int] = []  # start frame in corrupted timeline
        for s in swapped_plan:
            corrupted_offsets.append(corrupted_total)
            corrupted_total += _seg_frames(s["path"])
        n_corrupted_frames = corrupted_total

        # Find each swap slot's corrupted-timeline range.
        swap_ranges_corrupted = []
        for i, s in enumerate(swapped_plan):
            if s["kind"] in ("a", "b"):
                seg_len = _seg_frames(s["path"])
                swap_ranges_corrupted.append({
                    "kind_in_original_slot": s["kind"],
                    "corrupted_start": corrupted_offsets[i],
                    "corrupted_end": corrupted_offsets[i] + seg_len,
                })

        # Also record the original-timeline ranges of each shot (in the
        # *reference* original.mp4 timeline, derived the same way).
        original_total = 0
        original_offsets: list[int] = []
        for s in seg_plan:
            original_offsets.append(original_total)
            original_total += _seg_frames(s["path"])
        n_reference_frames = original_total
        swap_ranges_original = []
        for i, s in enumerate(seg_plan):
            if s["kind"] in ("a", "b"):
                seg_len = _seg_frames(s["path"])
                swap_ranges_original.append({
                    "kind": s["kind"],
                    "original_start": original_offsets[i],
                    "original_end": original_offsets[i] + seg_len,
                })

        gt_blob = {
            "fps_num": fps_num,
            "fps_den": fps_den,
            "total_corrupted_frames": n_corrupted_frames,
            "total_original_frames": n_reference_frames,
            "swap": swap_ranges_corrupted,
            "swap_original_timeline": swap_ranges_original,
            "pick_meta": pick_meta,
            "shot_count": len(shots),
            "shot_a_clip_range": [shot_a.start, shot_a.end],
            "shot_b_clip_range": [shot_b.start, shot_b.end],
        }

        # ---- 8. Vendor the Harbor task dir.
        (task_dir / "environment").mkdir(parents=True, exist_ok=True)
        (task_dir / "environment" / "Dockerfile").write_text(DOCKERFILE)
        (task_dir / "task.toml").write_text(TASK_TOML.format(
            task_name=task_name,
            source_name=source_mp4.name,
        ))

        step = task_dir / "steps" / "solve"
        step.mkdir(parents=True, exist_ok=True)
        (step / "instruction.md").write_text(INSTRUCTION_MD.format(
            duration_s=int(round(n_corrupted_frames / fps)),
            fps_int=int(round(fps)),
        ) + (f"\n\n## Source notes\n\n{instruction_hint}\n" if instruction_hint else ""))

        workdir = step / "workdir"
        workdir.mkdir(parents=True, exist_ok=True)
        shutil.copy(corrupted_mp4, workdir / "corrupted.mp4")
        prompt_path = workdir / "prompt.txt"
        prompt_path.write_text(
            "Two shots in this video have been swapped out of temporal "
            "order. Identify the swap and restore the original order."
        )
        _write_exec(workdir / "setup.sh", SETUP_SH)

        tests = step / "tests"
        tests.mkdir(parents=True, exist_ok=True)
        shutil.copy(original_mp4, tests / "original.mp4")
        (tests / "gt_swap.json").write_text(json.dumps(gt_blob, indent=2))
        _write_exec(tests / "test.sh", TEST_SH)
        _write_exec(tests / "judge.py", JUDGE_PY)

        solve_dir = step / "solution"
        solve_dir.mkdir(parents=True, exist_ok=True)
        # Oracle ships its own copy of gt_swap.json next to solve.sh.
        (solve_dir / "gt_swap.json").write_text(json.dumps(gt_blob, indent=2))
        _write_exec(solve_dir / "solve.sh", SOLVE_SH)

        # ---- 9. Build summary.
        summary = {
            "task_name": task_name,
            "task_dir": str(task_dir),
            "source": str(source_mp4),
            "fps": fps,
            "fps_rational": target_fps_rational,
            "n_shots_detected": len(shots),
            "shot_a": {"clip_idx": shot_a.idx, "clip_start": shot_a.start,
                       "clip_end": shot_a.end, "length": shot_a.length},
            "shot_b": {"clip_idx": shot_b.idx, "clip_start": shot_b.start,
                       "clip_end": shot_b.end, "length": shot_b.length},
            "pick_meta": pick_meta,
            "n_corrupted_frames": n_corrupted_frames,
            "n_reference_frames": n_reference_frames,
            "duration_s": n_corrupted_frames / fps,
            "swap_ranges_corrupted": swap_ranges_corrupted,
            "swap_ranges_original": swap_ranges_original,
        }
        print(json.dumps(summary, indent=2))
        return summary
