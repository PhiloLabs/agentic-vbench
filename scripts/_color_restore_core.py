"""Shared core for color-restoration repair task generators.

Flipped from the original color_shot tasks: the agent now receives the
graded video and must produce the clean original. The verifier compares
agent_output to the un-graded original with the same 85/15 in_window /
out_window split used by the windowed deblur tasks.

Task structure on disk (per task):
    workdir/source.mp4    — the BROKEN input (clean clip + LUT/CDL grade
                            applied over [window_start_s, window_end_s)).
    workdir/prompt.txt    — vague description of the grade applied.
    tests/original.mp4    — the clean reference the verifier compares to.
    tests/gt_window.json  — {"window_start_s","window_end_s","fps",
                             "weights":{"in_window":0.85,"out_window":0.15}}.
    tests/judge.py        — deterministic LAB-ΔE judge with in/out window.
    solution/solve.sh     — passthrough oracle (copy source -> output).

Two grade types are supported via ShotTaskSpec:
    grade_lut_path  — apply a published .cube LUT.
    grade_cdl       — apply ASC-CDL params (sat, contrast, R/G/B gains).
"""
from __future__ import annotations

import json
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent  # experiment/
TASKS_DIR = REPO_ROOT / "tasks" / "agentic_vbench_repair"
SOURCES_DIR = REPO_ROOT / "sources"


# --------------------------------------------------------------------- TOML
TASK_TOML = """\
version = "1.0"

[task]
name = "agentic-vbench/{task_name}"

[metadata]
difficulty = "hard"
category = "video-color-restore-shot"
tags = [{tags_csv}]
source = "{source_name}"
corruption = "{corruption_desc}"
license = "unknown-research-use-only"
attribution = "see source URL"

[environment]
build_timeout_sec = 1800.0
cpus = 4
memory_mb = 8192
storage_mb = 16384
allow_internet = true

[[steps]]
name = "solve"

[steps.agent]
timeout_sec = 2700.0

[steps.verifier]
timeout_sec = 1800.0
"""


DOCKERFILE = """\
FROM --platform=linux/amd64 python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \\
        ffmpeg curl ca-certificates libgl1 libglib2.0-0 \\
    && rm -rf /var/lib/apt/lists/*

# Deterministic color-grade judge: numpy + opencv only.
RUN pip install --no-cache-dir \\
        "numpy<3" "opencv-python-headless==4.13.*"

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
"""


SETUP_SH = """\
#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

mkdir -p /workspace/materials /workspace/output /workspace/work
cp "$HERE/source.mp4" /workspace/materials/source.mp4
cp "$HERE/prompt.txt" /workspace/materials/prompt.txt

if [ ! -s /workspace/materials/source.mp4 ]; then
    echo "ERROR: source.mp4 missing or empty" >&2
    exit 1
fi

mkdir -p /logs/artifacts
ffprobe -v error -show_entries stream=nb_read_frames,r_frame_rate,duration \\
        -count_frames -select_streams v:0 \\
        /workspace/materials/source.mp4 \\
        > /logs/artifacts/input-probe.txt 2>&1 || true

rm -rf -- "$HERE/source.mp4" "$HERE/prompt.txt" "$0"
"""


TEST_SH = """\
#!/bin/bash
# Verifier: deterministic windowed color-restoration judge (LAB ΔE).
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts

if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

python3 /tests/judge.py \\
        --output-mp4 /workspace/output/output.mp4 \\
        --source-mp4 /workspace/materials/source.mp4 \\
        --original-mp4 /tests/original.mp4 \\
        --gt-window-json /tests/gt_window.json \\
        --reward-json /logs/verifier/reward.json \\
        --reward-txt /logs/verifier/reward.txt
"""


JUDGE_PY = r'''#!/usr/bin/env python3
"""Color-restoration judge with in/out window scoring.

For each frame i:
    if window_start_frame <= i < window_end_frame  (in-window):
        dE_in[i]  = mean ΔE(output[i], original[i])    -- restoration
    else                                                (out-window):
        dE_out[i] = mean ΔE(output[i], source[i])      -- preservation

    in_window_score  = 1 - clip(mean(dE_in)  / 10.0, 0, 1)
    out_window_score = 1 - clip(mean(dE_out) / 5.0,  0, 1)
    reward = 0.85 * in_window_score + 0.15 * out_window_score

Deterministic single-threaded OpenCV decode (matches the deblur judge fix).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("OPENCV_FFMPEG_THREADS", "1")
os.environ.setdefault("OPENCV_VIDEOIO_PRIORITY_FFMPEG", "100")

import cv2
import numpy as np

cv2.setNumThreads(1)


DELTAE_IN_NORM = 10.0   # in-window ΔE / 10 -> 0 (restoration mapping)
DELTAE_OUT_NORM = 5.0   # out-window ΔE / 5  -> 0 (preservation, tighter)


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _zero(reason: str) -> dict:
    return {"reward": 0.0, "details": {"reason": reason}}


def _delta_e_lab(a_bgr: np.ndarray, b_bgr: np.ndarray) -> float:
    """Mean per-pixel Euclidean ΔE in OpenCV 8-bit LAB space.

    cv2 LAB is scaled (L: 0-255, a/b: 0-255 with 128 = neutral). Euclidean
    distance in that 8-bit space approximates CIE76 ΔE up to a scale; for
    a benchmark-internal threshold this is fine and fully deterministic.
    """
    if a_bgr.shape != b_bgr.shape:
        b_bgr = cv2.resize(b_bgr, (a_bgr.shape[1], a_bgr.shape[0]),
                           interpolation=cv2.INTER_AREA)
    la = cv2.cvtColor(a_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    lb = cv2.cvtColor(b_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    return float(np.sqrt(np.mean(np.sum((la - lb) ** 2, axis=-1))))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output-mp4", required=True, type=Path)
    p.add_argument("--source-mp4", required=True, type=Path)
    p.add_argument("--original-mp4", required=True, type=Path)
    p.add_argument("--gt-window-json", required=True, type=Path)
    p.add_argument("--reward-json", required=True, type=Path)
    p.add_argument("--reward-txt", required=True, type=Path)
    args = p.parse_args()

    args.reward_json.parent.mkdir(parents=True, exist_ok=True)

    if not args.output_mp4.exists():
        result = _zero(f"no output.mp4 at {args.output_mp4}")
    elif not args.source_mp4.exists():
        result = _zero(f"missing source.mp4 at {args.source_mp4}")
    elif not args.original_mp4.exists():
        result = _zero(f"missing original.mp4 at {args.original_mp4}")
    elif not args.gt_window_json.exists():
        result = _zero(f"missing gt_window.json at {args.gt_window_json}")
    else:
        win = json.loads(args.gt_window_json.read_text())
        fps = float(win["fps"])
        w_start_s = float(win["window_start_s"])
        w_end_s = float(win["window_end_s"])
        w = win.get("weights") or {}
        w_in = float(w.get("in_window", 0.85))
        w_out = float(w.get("out_window", 0.15))

        # Stream-decode all 3 videos frame-by-frame to keep memory bounded
        # (an earlier all-in-memory version OOM'd the 4 GiB container on
        # the 216 s v3-s1 clip — 5400 frames × 960×720×3 × 3 = ~33 GiB).
        out_cap = cv2.VideoCapture(str(args.output_mp4))
        src_cap = cv2.VideoCapture(str(args.source_mp4))
        orig_cap = cv2.VideoCapture(str(args.original_mp4))
        try:
            # Probe a hint for window-frame conversion (use any cap's count).
            n_hint = int(out_cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
            start_f = max(0, int(round(w_start_s * fps)))
            end_f = max(start_f, int(round(w_end_s * fps)))
            dE_in_sum = 0.0; dE_in_n = 0
            dE_out_sum = 0.0; dE_out_n = 0
            i = 0
            while True:
                ok_o, of = out_cap.read()
                ok_s, sf = src_cap.read()
                ok_or, orf = orig_cap.read()
                if not (ok_o and ok_s and ok_or):
                    break
                if start_f <= i < end_f:
                    dE_in_sum += _delta_e_lab(of, orf)
                    dE_in_n += 1
                else:
                    dE_out_sum += _delta_e_lab(of, sf)
                    dE_out_n += 1
                i += 1
            n = i
        finally:
            out_cap.release(); src_cap.release(); orig_cap.release()

        if n == 0:
            result = _zero("could not decode any frames from inputs")
        elif end_f <= start_f:
            result = _zero(
                f"degenerate window frames=[{start_f},{end_f}) "
                f"after clipping to n={n}")
        else:
            # Coverage: how many of the EXPECTED in/out-window frames did
            # we actually score? If the agent submitted a shorter output
            # than source/original, we end the per-frame loop early and
            # leave parts of the expected window unmeasured. Penalize
            # missing coverage so a truncated submission can't game the
            # judge by simply not addressing the corrupted window at all.
            expected_in = max(0, end_f - start_f)
            # Source frame count probed from the source video so we know
            # what the agent SHOULD have produced.
            src_total = int(src_cap.get(cv2.CAP_PROP_FRAME_COUNT)) or n
            expected_out = max(0, src_total - expected_in)
            in_coverage = (dE_in_n / expected_in) if expected_in > 0 else 1.0
            out_coverage = (dE_out_n / expected_out) if expected_out > 0 else 1.0
            in_coverage = _clip01(in_coverage)
            out_coverage = _clip01(out_coverage)

            end_f_eff = min(end_f, n)
            mean_in = (dE_in_sum / dE_in_n) if dE_in_n else 0.0
            mean_out = (dE_out_sum / dE_out_n) if dE_out_n else 0.0
            raw_in = _clip01(1.0 - mean_in / DELTAE_IN_NORM) if dE_in_n else 0.0
            raw_out = _clip01(1.0 - mean_out / DELTAE_OUT_NORM) if dE_out_n else 0.0
            in_score = raw_in * in_coverage
            out_score = raw_out * out_coverage
            reward = w_in * in_score + w_out * out_score
            result = {
                "reward": float(reward),
                "details": {
                    "reason": "ok",
                    "task_type": "color-restore",
                    "n_frames_scored": n,
                    "n_frames_expected": src_total,
                    "window_start_frame": start_f,
                    "window_end_frame": end_f_eff,
                    "n_in_window_frames": dE_in_n,
                    "n_out_window_frames": dE_out_n,
                    "expected_in_window_frames": expected_in,
                    "expected_out_window_frames": expected_out,
                    "in_window_coverage": in_coverage,
                    "out_window_coverage": out_coverage,
                    "mean_deltaE_in_window_vs_original": mean_in,
                    "mean_deltaE_out_window_vs_source": mean_out,
                    "raw_in_window_score": raw_in,
                    "raw_out_window_score": raw_out,
                    "in_window_score": in_score,
                    "out_window_score": out_score,
                    "weights": {"in_window": w_in, "out_window": w_out},
                },
            }

    args.reward_json.write_text(json.dumps(result, indent=2))
    args.reward_txt.write_text(f"{result['reward']:.6f}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
'''


SOLVE_SH = """\
#!/bin/bash
# Oracle: passthrough — copy source (broken) to output. Establishes the
# "do nothing" baseline. Out-of-window scores perfect (untouched matches
# input). In-window scores poorly (still graded). Composite around 0.15.
set -euo pipefail
mkdir -p /workspace/output
cp /workspace/materials/source.mp4 /workspace/output/output.mp4
echo "oracle: passthrough copied source.mp4 -> output.mp4"
"""


INSTRUCTION_TEMPLATE = """\
# Color-Grade Restoration (Windowed)

`/workspace/materials/source.mp4` is a video where a **bad color grade
has been applied to a contiguous window of frames**. Outside that window
the original look is intact. Your job is to find the affected stretch
and revert it so the entire video plays back at the original look.

A short prompt at `/workspace/materials/prompt.txt` hints at what kind
of grade has been applied (e.g. "a warm cinematic tint" or "a noir
black-and-white look"); it does NOT tell you the exact frames.

## Your job

1. Identify the time window where the bad grade has been applied.
2. Restore that range to the original look — match the colour and tone
   of the surrounding (clean) frames.
3. Leave every frame **outside** the bad-grade window unchanged.
4. Write the result to **`/workspace/output/output.mp4`**.

You do not need to emit a separate metadata JSON; the verifier compares
your output pixel-wise against the hidden clean reference.

## Output format

- H.264 / yuv420p mp4
- Same resolution and frame rate as the input
- Same number of frames as the input
- Audio: keep the input's audio if present (the verifier ignores audio
  but a player-friendly output is preferred)

## Scoring

The judge weighs **in-window restoration** vs **out-of-window
preservation** at 85% / 15%:

```
mean_dE_in  = mean LAB ΔE between your output and the clean reference,
              averaged over the bad-grade window
mean_dE_out = mean LAB ΔE between your output and the original input,
              averaged over frames OUTSIDE the bad-grade window
in_window_score  = clip01(1 - mean_dE_in  / 10.0)
out_window_score = clip01(1 - mean_dE_out /  5.0)
reward = 0.85 * in_window_score + 0.15 * out_window_score
```

Passthrough (do nothing) baseline: composite around 0.15 (out-window
preservation is perfect, but in-window stays graded → near-zero).

## Notes

- Container has internet. CPU only.
- Available libs: ffmpeg (with `lut3d` / `eq` filters), numpy,
  opencv-python-headless.
- Detect the affected window first (e.g. shot-boundary detection plus
  per-frame colour-stat anomaly), then apply an inverse grade only to
  that range.
"""


@dataclass
class ColorRestoreTaskSpec:
    task_name: str
    source_mp4: Path
    clip_start_sec: float
    clip_duration_sec: float
    fps: int                       # rate to re-encode the clip to
    # The contiguous window where the grade is applied, in clip-relative
    # seconds (i.e., 0 = clip start, clip_duration_sec = clip end).
    grade_window_sec: tuple[float, float]
    # Short hint in the prompt — kept deliberately vague but mentions the
    # *kind* of grade (e.g. "a warm cinematic tint", "a noir B&W look",
    # "a cold-desaturated blueish wash"). The agent does not get the
    # exact window.
    grade_hint: str
    # Grade specification — mutually exclusive.
    grade_lut_path: Path | None = None     # path to a .cube LUT
    grade_cdl: dict | None = None          # {"saturation", "contrast",
                                            #  "rr", "gg", "bb"}
    tags: list = field(default_factory=lambda: [
        "color-restore", "video-color", "video-restoration", "windowed",
    ])


# --------------------------------------------------------------- utilities
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


def _has_audio(path: Path) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    ).stdout.strip()
    return bool(out)


def _extract_clip(source: Path, start_sec: float, duration_sec: float,
                  fps: int, dst: Path, with_audio: bool) -> None:
    """Extract a clip (re-encoded H.264, yuv420p, fixed fps). Keeps audio
    if `with_audio` is True (assumes source has an audio stream)."""
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", str(start_sec),
        "-t", str(duration_sec),
        "-i", str(source),
        "-vf", f"fps={fps}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
        "-crf", "18",
    ]
    if with_audio:
        cmd += ["-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "128k"]
    else:
        cmd += ["-an"]
    cmd += [str(dst)]
    _run(cmd)


def _apply_grade_window(
    *,
    source: Path,
    dst: Path,
    fps: int,
    window_start_s: float,
    window_end_s: float,
    lut_path: Path | None,
    cdl: dict | None,
    with_audio: bool,
) -> None:
    """Apply LUT or CDL grade ONLY to frames whose timestamp is in the
    given window. Frames outside the window stream-copy through.

    Uses ffmpeg's split + trim + concat filter graph. Picks the right
    grading expression based on which of lut_path / cdl is set.
    """
    # Use frame-number trim so the segment boundary is exact across
    # different fps rationals.
    w_start_f = int(round(window_start_s * fps))
    w_end_f = int(round(window_end_s * fps))

    if lut_path is not None:
        grade_filter = f"lut3d='{lut_path.as_posix()}'"
    elif cdl is not None:
        # CDL via ffmpeg `eq` filter — saturation + contrast — and a
        # `colorchannelmixer` for per-channel gains. Order matters: apply
        # per-channel gains first (acts on linear-ish 8-bit data), then
        # saturation/contrast (eq's documented behaviour). Approximate but
        # deterministic and matches what review.html's "v3_cold_desat"
        # produces.
        sat = float(cdl.get("saturation", 1.0))
        contrast = float(cdl.get("contrast", 1.0))
        rr = float(cdl.get("rr", 1.0))
        gg = float(cdl.get("gg", 1.0))
        bb = float(cdl.get("bb", 1.0))
        grade_filter = (
            f"colorchannelmixer=rr={rr}:gg={gg}:bb={bb},"
            f"eq=saturation={sat}:contrast={contrast}"
        )
    else:
        raise ValueError("must specify either lut_path or cdl")

    # Three-way split + grade middle segment + concat.
    audio_n = 0 if not with_audio else 1
    # Always go through concat with v=1; only include a=1 path when audio.
    if with_audio:
        fc = (
            f"[0:v]split=3[v0][v1][v2];"
            f"[v0]trim=end_frame={w_start_f},setpts=N/FRAME_RATE/TB[v0t];"
            f"[v1]trim=start_frame={w_start_f}:end_frame={w_end_f},"
            f"setpts=N/FRAME_RATE/TB,{grade_filter}[v1g];"
            f"[v2]trim=start_frame={w_end_f},setpts=N/FRAME_RATE/TB[v2t];"
            f"[v0t][v1g][v2t]concat=n=3:v=1:a=0[outv]"
        )
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(source),
            "-filter_complex", fc,
            "-map", "[outv]", "-map", "0:a:0",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "128k",
            str(dst),
        ]
    else:
        fc = (
            f"[0:v]split=3[v0][v1][v2];"
            f"[v0]trim=end_frame={w_start_f},setpts=N/FRAME_RATE/TB[v0t];"
            f"[v1]trim=start_frame={w_start_f}:end_frame={w_end_f},"
            f"setpts=N/FRAME_RATE/TB,{grade_filter}[v1g];"
            f"[v2]trim=start_frame={w_end_f},setpts=N/FRAME_RATE/TB[v2t];"
            f"[v0t][v1g][v2t]concat=n=3:v=1:a=0[outv]"
        )
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(source),
            "-filter_complex", fc,
            "-map", "[outv]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
            "-an",
            str(dst),
        ]
    _run(cmd)


def build_task(spec: ColorRestoreTaskSpec) -> dict:
    task_dir = TASKS_DIR / spec.task_name
    if task_dir.exists():
        shutil.rmtree(task_dir)
    task_dir.mkdir(parents=True)

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        with_audio = _has_audio(spec.source_mp4)

        # 1. Extract clean clip.
        clean_clip = tmp / "clean.mp4"
        _extract_clip(spec.source_mp4, spec.clip_start_sec,
                      spec.clip_duration_sec, spec.fps,
                      clean_clip, with_audio)

        # 2. Build the BROKEN video (clean + grade applied to window).
        broken_clip = tmp / "broken.mp4"
        _apply_grade_window(
            source=clean_clip,
            dst=broken_clip,
            fps=spec.fps,
            window_start_s=spec.grade_window_sec[0],
            window_end_s=spec.grade_window_sec[1],
            lut_path=spec.grade_lut_path,
            cdl=spec.grade_cdl,
            with_audio=with_audio,
        )

        # Probe so we can sanity-check frame counts.
        def _count_frames(p: Path) -> int:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-count_frames", "-show_entries", "stream=nb_read_frames",
                 "-of", "csv=p=0", str(p)],
                capture_output=True, text=True, check=True,
            )
            return int(r.stdout.strip())
        n_clean = _count_frames(clean_clip)
        n_broken = _count_frames(broken_clip)
        if n_clean != n_broken:
            print(f"  WARNING: frame count mismatch clean={n_clean} "
                  f"broken={n_broken}")

        # 3. Build prompt — vague.
        prompt = (
            f"This video has a bad color grade applied to a contiguous "
            f"window of frames somewhere inside it: {spec.grade_hint}. "
            f"Find the affected range and restore it to the original "
            f"look. Leave every frame outside that window unchanged."
        )

        # 4. Build GT window.
        w_start_f = int(round(spec.grade_window_sec[0] * spec.fps))
        w_end_f = int(round(spec.grade_window_sec[1] * spec.fps))
        gt_window = {
            "window_start_s": float(spec.grade_window_sec[0]),
            "window_end_s": float(spec.grade_window_sec[1]),
            "window_start_frame": w_start_f,
            "window_end_frame": w_end_f,
            "fps": float(spec.fps),
            "n_frames_total": int(n_clean),
            "weights": {"in_window": 0.85, "out_window": 0.15},
            "grade_kind": "lut" if spec.grade_lut_path else "cdl",
            "grade_provenance": (
                spec.grade_lut_path.name if spec.grade_lut_path else
                {"kind": "asc_cdl", **(spec.grade_cdl or {})}),
        }

        # 5. Write task dir.
        env_dir = task_dir / "environment"
        env_dir.mkdir(parents=True, exist_ok=True)
        (env_dir / "Dockerfile").write_text(DOCKERFILE)

        tags_csv = ", ".join(f'"{t}"' for t in spec.tags)
        if spec.grade_lut_path is not None:
            corr_desc = (f"LUT {spec.grade_lut_path.name} applied to "
                         f"[{spec.grade_window_sec[0]:.2f}s, "
                         f"{spec.grade_window_sec[1]:.2f}s)")
        else:
            cdl = spec.grade_cdl or {}
            corr_desc = (f"ASC-CDL (sat={cdl.get('saturation','?')}, "
                         f"contrast={cdl.get('contrast','?')}, "
                         f"RGB={cdl.get('rr','?')}/{cdl.get('gg','?')}/"
                         f"{cdl.get('bb','?')}) applied to "
                         f"[{spec.grade_window_sec[0]:.2f}s, "
                         f"{spec.grade_window_sec[1]:.2f}s)")
        (task_dir / "task.toml").write_text(TASK_TOML.format(
            task_name=spec.task_name,
            tags_csv=tags_csv,
            source_name=spec.source_mp4.name,
            corruption_desc=corr_desc,
        ))

        step = task_dir / "steps" / "solve"
        step.mkdir(parents=True, exist_ok=True)
        (step / "instruction.md").write_text(INSTRUCTION_TEMPLATE)

        workdir = step / "workdir"
        workdir.mkdir(parents=True, exist_ok=True)
        shutil.copy(broken_clip, workdir / "source.mp4")
        (workdir / "prompt.txt").write_text(prompt + "\n")
        _write_exec(workdir / "setup.sh", SETUP_SH)

        tests = step / "tests"
        tests.mkdir(parents=True, exist_ok=True)
        shutil.copy(clean_clip, tests / "original.mp4")
        (tests / "gt_window.json").write_text(json.dumps(gt_window, indent=2))
        _write_exec(tests / "test.sh", TEST_SH)
        _write_exec(tests / "judge.py", JUDGE_PY)

        solution = step / "solution"
        solution.mkdir(parents=True, exist_ok=True)
        _write_exec(solution / "solve.sh", SOLVE_SH)

        summary = {
            "task_name": spec.task_name,
            "task_dir": str(task_dir),
            "source": str(spec.source_mp4),
            "fps": spec.fps,
            "n_frames_clean": n_clean,
            "n_frames_broken": n_broken,
            "grade_window_sec": list(spec.grade_window_sec),
            "grade_window_frames": [w_start_f, w_end_f],
            "with_audio": with_audio,
        }
        print(json.dumps(summary, indent=2))
        return summary
