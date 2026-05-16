"""Shared core for mask-region video repair task generators.

Pattern: take a 30 s clip at 480p / 30 fps; apply a per-frame corruption
INSIDE a hardcoded bbox mask only; ship (corrupted.mp4, mask.png, clean.mp4)
to the Harbor task dir. Judge computes in-mask metric (vs clean) and
out-of-mask preservation metric (vs corrupted), composite reward.

Used by:
  build_color_grade_visit_korea.py
  build_color_grade_gobelins.py
  build_deblur_gaussian_mkbhd.py
  build_deblur_motion_f1.py
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
from typing import Callable

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent  # experiment/
TASKS_DIR = REPO_ROOT / "tasks"
SOURCES_DIR = REPO_ROOT / "sources"

TARGET_W = 854
TARGET_H = 480
TARGET_FPS = 30
CLIP_DURATION_SEC = 30


# -------------------------------------------------------------------- TOML
TASK_TOML = """\
version = "1.0"

[task]
name = "agentic-vbench/{task_name}"

[metadata]
difficulty = "medium"
category = "{category}"
tags = [{tags_csv}]
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
timeout_sec = 1800.0

[steps.verifier]
timeout_sec = 600.0
"""


DOCKERFILE = """\
FROM --platform=linux/amd64 python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \\
        ffmpeg \\
        ca-certificates \\
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \\
        "numpy<3" \\
        "opencv-python-headless==4.13.*" \\
        "scikit-image==0.26.*" \\
        "colour-science==0.4.*"

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
"""


SETUP_SH = """\
#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

mkdir -p /workspace/materials /workspace/output /workspace/work
cp "$HERE/corrupted.mp4" /workspace/materials/corrupted.mp4
cp "$HERE/mask.png" /workspace/materials/mask.png

if [ ! -s /workspace/materials/corrupted.mp4 ]; then
    echo "ERROR: corrupted.mp4 missing or empty" >&2
    exit 1
fi
if [ ! -s /workspace/materials/mask.png ]; then
    echo "ERROR: mask.png missing or empty" >&2
    exit 1
fi

mkdir -p /logs/artifacts
ffprobe -v error -show_entries stream=nb_read_frames,r_frame_rate,duration \\
        -count_frames -select_streams v:0 \\
        /workspace/materials/corrupted.mp4 \\
        > /logs/artifacts/input-probe.txt 2>&1 || true

rm -rf -- "$HERE/corrupted.mp4" "$HERE/mask.png" "$0"
"""


TEST_SH = """\
#!/bin/bash
# Verifier: masked metrics — in-mask quality vs clean, out-mask preservation vs corrupted.
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts

if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

python3 -c "import cv2, numpy, skimage, colour" 2>/dev/null || \\
    pip install --quiet --no-cache-dir "numpy<3" \\
        "opencv-python-headless==4.13.*" \\
        "scikit-image==0.26.*" \\
        "colour-science==0.4.*"

WIN_ARG=()
if [ -f /tests/gt_window.json ]; then
    WIN_ARG=(--gt-window-json /tests/gt_window.json)
fi

python3 /tests/judge.py \\
        --output-mp4 /workspace/output/output.mp4 \\
        --clean-mp4 /tests/clean.mp4 \\
        --corrupted-mp4 /workspace/materials/corrupted.mp4 \\
        --mask-png /tests/mask.png \\
        --task-type {task_type} \\
        "${{WIN_ARG[@]}}" \\
        --reward-json /logs/verifier/reward.json \\
        --reward-txt /logs/verifier/reward.txt
"""


JUDGE_PY = '''\
#!/usr/bin/env python3
"""Masked-region video repair judge.

Loads `output.mp4`, `clean.mp4`, `corrupted.mp4`, and `mask.png`. For each
frame pair, computes:

  * in-mask metric: distance from agent output to CLEAN reference
    - color task: mean CIEDE2000 (ΔE2000) over masked pixels
    - deblur task: PSNR-Y and SSIM-Y over masked pixels
  * out-mask preservation metric: agent output vs the (corrupted) input
    in non-masked pixels. The agent should not touch outside the mask;
    untouched pixels score perfectly here.
    - color task: mean ΔE2000 (lower = closer to corrupted = better
      preservation)
    - deblur task: PSNR (higher = closer to corrupted = better
      preservation)

Mapping to [0, 1]:
  color   in_score  = clip01(1 - mean_dE_in / 10)   # tightened from /30
  color   out_score = clip01(1 - mean_dE_out / 5)
  deblur  in_score  = clip01((PSNR_in - 18) / 14)   # tightened from (PSNR-15)/25
                       blended 0.5/0.5 with clip01((SSIM_in - 0.6) / 0.4)
  deblur  out_score = clip01((PSNR_out - 30) / 20)

Composite: reward = 0.7 * in_score + 0.3 * out_score.

Why tightened: the user's nominal corruption recipe (hue ±10-15deg, sat
x0.5/x1.2; Gaussian sigma=3 ksize=15; motion length=15px) produces mild
perceptual deltas (mean dE2000 ~3-6; mean masked PSNR ~25-27 dB). Under
the original /30 and /25 divisors a do-nothing passthrough scored
0.74-0.92, leaving no signal for the agent. Tightened divisors land the
passthrough baseline near 0.50, matching the spec target ~0.51.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Force deterministic single-threaded decode. OpenCV's libav backend
# uses multi-threaded H.264 decode by default; with B-frames the reorder
# schedule can shift between container starts and drift PSNR ~±2 dB.
os.environ.setdefault("OPENCV_FFMPEG_THREADS", "1")
os.environ.setdefault("OPENCV_VIDEOIO_PRIORITY_FFMPEG", "100")

import cv2
import numpy as np
from skimage.metrics import peak_signal_noise_ratio, structural_similarity

cv2.setNumThreads(1)


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _zero(reason: str) -> dict:
    return {"reward": 0.0, "details": {"reason": reason}}


def _read_all_frames(path: Path) -> list[np.ndarray]:
    """Return all frames as a list of HxWx3 uint8 BGR arrays."""
    cap = cv2.VideoCapture(str(path))
    frames = []
    try:
        if not cap.isOpened():
            return []
        while True:
            ok, f = cap.read()
            if not ok:
                break
            frames.append(f)
    finally:
        cap.release()
    return frames


def _load_mask(path: Path, h: int, w: int) -> np.ndarray:
    m = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if m is None:
        raise RuntimeError(f"cannot read mask at {path}")
    if m.shape != (h, w):
        m = cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST)
    return (m > 127).astype(np.uint8)


def _bgr_to_lab(bgr: np.ndarray) -> np.ndarray:
    """OpenCV Lab (8-bit) -> CIE Lab in standard ranges (L:0-100, a/b: -128..127)."""
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    lab[..., 0] *= (100.0 / 255.0)
    lab[..., 1] -= 128.0
    lab[..., 2] -= 128.0
    return lab


def _delta_e_2000(lab1: np.ndarray, lab2: np.ndarray) -> np.ndarray:
    """Per-pixel CIEDE2000. Inputs HxWx3 (CIE Lab). Output HxW."""
    # Use colour-science for correctness (vectorised).
    import colour
    return colour.delta_E(lab1, lab2, method="CIE 2000")


def _rgb_to_y(bgr: np.ndarray) -> np.ndarray:
    rgb = bgr[..., ::-1].astype(np.float32)
    return 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]


def _masked_psnr_ssim(out_y: np.ndarray, ref_y: np.ndarray,
                      mask: np.ndarray) -> tuple[float, float]:
    """PSNR + SSIM restricted to mask pixels.

    For PSNR we compute MSE over masked pixels only.
    For SSIM we compute the full SSIM map and average over masked pixels.
    """
    diff = (out_y - ref_y).astype(np.float32)
    mse = float(np.mean(diff[mask > 0] ** 2)) if mask.sum() > 0 else 0.0
    if mse <= 1e-8:
        psnr = 100.0
    else:
        psnr = 10.0 * np.log10((255.0 ** 2) / mse)
    # SSIM map (returns same shape as inputs when full=True).
    _, ssim_map = structural_similarity(
        ref_y, out_y, data_range=255, full=True
    )
    ssim = float(np.mean(ssim_map[mask > 0])) if mask.sum() > 0 else 0.0
    return float(psnr), ssim


def _resize_to(frame: np.ndarray, h: int, w: int) -> np.ndarray:
    if frame.shape[:2] != (h, w):
        return cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)
    return frame


def _load_window(path: Path | None, n_frames: int, fps_hint: float):
    """Return (start_f, end_f, weights) or None for legacy full-clip scoring.

    gt_window.json shape:
      {"window_start_s": float, "window_end_s": float, "fps": float,
       "weights": {"in_window": 0.85, "out_window": 0.15}}
    """
    if path is None or not path.exists():
        return None
    data = json.loads(path.read_text())
    fps = float(data.get("fps", fps_hint))
    s = float(data["window_start_s"])
    e = float(data["window_end_s"])
    start_f = max(0, int(round(s * fps)))
    end_f = min(n_frames, int(round(e * fps)))
    if end_f <= start_f:
        return None
    w = data.get("weights") or {}
    w_in = float(w.get("in_window", 0.85))
    w_out = float(w.get("out_window", 0.15))
    return start_f, end_f, w_in, w_out


def score_color(out_frames, clean_frames, corr_frames, mask, window) -> dict:
    n = min(len(out_frames), len(clean_frames), len(corr_frames))
    if n == 0:
        return _zero("no frames to score")
    inv = 1 - mask
    n_in_px = int(mask.sum())
    n_out_px = int(inv.sum())
    if n_in_px == 0:
        return _zero("degenerate mask (no in-mask pixels)")
    has_out_px = n_out_px > 0
    h, w = mask.shape
    win = window if window else (0, n, 1.0, 0.0)
    start_f, end_f, w_in_win, w_out_win = win
    in_win_in_mask, in_win_out_mask, out_win_full = [], [], []
    for i in range(n):
        out = _resize_to(out_frames[i], h, w)
        clean = _resize_to(clean_frames[i], h, w)
        corr = _resize_to(corr_frames[i], h, w)
        out_lab = _bgr_to_lab(out)
        clean_lab = _bgr_to_lab(clean)
        corr_lab = _bgr_to_lab(corr)
        if start_f <= i < end_f:
            de_in = _delta_e_2000(out_lab, clean_lab)
            in_win_in_mask.append(float(np.mean(de_in[mask > 0])))
            if has_out_px:
                de_out = _delta_e_2000(out_lab, corr_lab)
                in_win_out_mask.append(float(np.mean(de_out[inv > 0])))
        else:
            de_full = _delta_e_2000(out_lab, corr_lab)
            out_win_full.append(float(np.mean(de_full)))
    mean_in_win_in_mask = float(np.mean(in_win_in_mask)) if in_win_in_mask else 0.0
    restore = _clip01(1.0 - mean_in_win_in_mask / 7.0) if in_win_in_mask else 1.0
    mean_in_win_out_mask = float(np.mean(in_win_out_mask)) if in_win_out_mask else 0.0
    in_win_preserve = _clip01(1.0 - mean_in_win_out_mask / 5.0) if in_win_out_mask else 1.0
    if in_win_out_mask:
        in_window_score = 0.7 * restore + 0.3 * in_win_preserve
    else:
        in_window_score = restore  # full-frame mask
    mean_out_win = float(np.mean(out_win_full)) if out_win_full else 0.0
    out_window_score = _clip01(1.0 - mean_out_win / 5.0) if out_win_full else 1.0
    if out_win_full:
        reward = w_in_win * in_window_score + w_out_win * out_window_score
    else:
        reward = in_window_score
    return {
        "reward": float(reward),
        "details": {
            "reason": "ok",
            "task_type": "color",
            "n_frames_scored": n,
            "window_start_frame": start_f,
            "window_end_frame": end_f,
            "n_in_window_frames": len(in_win_in_mask),
            "n_out_window_frames": len(out_win_full),
            "mean_dE2000_in_window_in_mask_vs_clean": mean_in_win_in_mask,
            "mean_dE2000_in_window_out_mask_vs_corrupted": mean_in_win_out_mask,
            "mean_dE2000_out_window_vs_corrupted": mean_out_win,
            "in_window_score": in_window_score,
            "out_window_score": out_window_score,
            "weights": {"in_window": w_in_win, "out_window": w_out_win},
        },
    }


def score_deblur(out_frames, clean_frames, corr_frames, mask, window) -> dict:
    n = min(len(out_frames), len(clean_frames), len(corr_frames))
    if n == 0:
        return _zero("no frames to score")
    inv = 1 - mask
    if mask.sum() == 0:
        return _zero("degenerate mask (no in-mask pixels)")
    has_out_px = inv.sum() > 0
    h, w = mask.shape
    win = window if window else (0, n, 1.0, 0.0)
    start_f, end_f, w_in_win, w_out_win = win
    in_win_psnr, in_win_ssim = [], []
    in_win_preserve_psnr = []
    out_win_psnr = []
    full_mask = np.ones_like(mask)
    for i in range(n):
        out = _resize_to(out_frames[i], h, w)
        clean = _resize_to(clean_frames[i], h, w)
        corr = _resize_to(corr_frames[i], h, w)
        out_y = _rgb_to_y(out)
        clean_y = _rgb_to_y(clean)
        corr_y = _rgb_to_y(corr)
        if start_f <= i < end_f:
            p_in, s_in = _masked_psnr_ssim(out_y, clean_y, mask)
            in_win_psnr.append(p_in)
            in_win_ssim.append(s_in)
            if has_out_px:
                p_out, _ = _masked_psnr_ssim(out_y, corr_y, inv)
                in_win_preserve_psnr.append(p_out)
        else:
            p_full, _ = _masked_psnr_ssim(out_y, corr_y, full_mask)
            out_win_psnr.append(p_full)
    mean_psnr_in = float(np.mean(in_win_psnr)) if in_win_psnr else 0.0
    mean_ssim_in = float(np.mean(in_win_ssim)) if in_win_ssim else 0.0
    if in_win_psnr:
        psnr_part = _clip01((mean_psnr_in - 22.0) / 13.0)
        ssim_part = _clip01((mean_ssim_in - 0.75) / 0.25)
        restore = 0.5 * psnr_part + 0.5 * ssim_part
    else:
        restore = 1.0
    mean_in_win_preserve = float(np.mean(in_win_preserve_psnr)) if in_win_preserve_psnr else 0.0
    in_win_preserve = _clip01((mean_in_win_preserve - 30.0) / 20.0) if in_win_preserve_psnr else 1.0
    if in_win_preserve_psnr:
        in_window_score = 0.7 * restore + 0.3 * in_win_preserve
    else:
        in_window_score = restore  # full-frame mask
    mean_out_win_psnr = float(np.mean(out_win_psnr)) if out_win_psnr else 0.0
    out_window_score = _clip01((mean_out_win_psnr - 30.0) / 20.0) if out_win_psnr else 1.0
    if out_win_psnr:
        reward = w_in_win * in_window_score + w_out_win * out_window_score
    else:
        reward = in_window_score
    return {
        "reward": float(reward),
        "details": {
            "reason": "ok",
            "task_type": "deblur",
            "n_frames_scored": n,
            "window_start_frame": start_f,
            "window_end_frame": end_f,
            "n_in_window_frames": len(in_win_psnr),
            "n_out_window_frames": len(out_win_psnr),
            "mean_psnr_in_window_in_mask_vs_clean": mean_psnr_in,
            "mean_ssim_in_window_in_mask_vs_clean": mean_ssim_in,
            "mean_psnr_in_window_out_mask_vs_corrupted": mean_in_win_preserve,
            "mean_psnr_out_window_vs_corrupted": mean_out_win_psnr,
            "in_window_score": in_window_score,
            "out_window_score": out_window_score,
            "weights": {"in_window": w_in_win, "out_window": w_out_win},
        },
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output-mp4", required=True, type=Path)
    p.add_argument("--clean-mp4", required=True, type=Path)
    p.add_argument("--corrupted-mp4", required=True, type=Path)
    p.add_argument("--mask-png", required=True, type=Path)
    p.add_argument("--task-type", required=True, choices=["color", "deblur"])
    p.add_argument("--gt-window-json", default=None, type=Path)
    p.add_argument("--reward-json", required=True, type=Path)
    p.add_argument("--reward-txt", required=True, type=Path)
    args = p.parse_args()

    args.reward_json.parent.mkdir(parents=True, exist_ok=True)

    if not args.output_mp4.exists():
        result = _zero(f"no output.mp4 at {args.output_mp4}")
    elif not args.clean_mp4.exists():
        result = _zero(f"missing clean reference at {args.clean_mp4}")
    elif not args.corrupted_mp4.exists():
        result = _zero(f"missing corrupted at {args.corrupted_mp4}")
    elif not args.mask_png.exists():
        result = _zero(f"missing mask at {args.mask_png}")
    else:
        out_frames = _read_all_frames(args.output_mp4)
        clean_frames = _read_all_frames(args.clean_mp4)
        corr_frames = _read_all_frames(args.corrupted_mp4)
        if not out_frames:
            result = _zero("output.mp4 has no decodable frames")
        elif not clean_frames or not corr_frames:
            result = _zero("clean or corrupted has no frames")
        else:
            h, w = clean_frames[0].shape[:2]
            mask = _load_mask(args.mask_png, h, w)
            n = min(len(out_frames), len(clean_frames), len(corr_frames))
            window = _load_window(args.gt_window_json, n, 30.0)
            if args.task_type == "color":
                result = score_color(out_frames, clean_frames, corr_frames, mask, window)
            else:
                result = score_deblur(out_frames, clean_frames, corr_frames, mask, window)

    args.reward_json.write_text(json.dumps(result, indent=2))
    args.reward_txt.write_text(f"{result['reward']:.6f}\\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


SOLVE_SH = """\
#!/bin/bash
# Oracle: passthrough — copy corrupted input to output. Establishes the
# "do nothing" baseline. Out-of-mask region scores ~perfectly (untouched);
# in-mask region scores poorly (still corrupted). Composite ~0.4-0.6.
set -euo pipefail
mkdir -p /workspace/output
cp /workspace/materials/corrupted.mp4 /workspace/output/output.mp4
echo "oracle: passthrough copied corrupted.mp4 -> output.mp4"
"""


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


def _extract_clip(source: Path, start_sec: float, dst: Path) -> None:
    """Extract a 30 s clip at 854x480, 30 fps, no audio, libx264."""
    _run([
        "ffmpeg", "-y",
        "-ss", str(start_sec),
        "-t", str(CLIP_DURATION_SEC),
        "-i", str(source),
        "-an",
        "-vf", f"scale={TARGET_W}:{TARGET_H},fps={TARGET_FPS}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
        str(dst),
    ])


def _read_all_frames_bgr(path: Path) -> list[np.ndarray]:
    cap = cv2.VideoCapture(str(path))
    frames = []
    try:
        while True:
            ok, f = cap.read()
            if not ok:
                break
            frames.append(f)
    finally:
        cap.release()
    return frames


def _write_video_from_frames(frames: list[np.ndarray], dst: Path,
                             fps: int = TARGET_FPS) -> None:
    """Write frames -> mp4 via raw PNG dir + ffmpeg (libx264, yuv420p)."""
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        for i, f in enumerate(frames):
            cv2.imwrite(str(tmp / f"{i + 1:06d}.png"), f)
        _run([
            "ffmpeg", "-y",
            "-framerate", str(fps),
            "-i", str(tmp / "%06d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
            "-r", str(fps),
            "-an",
            str(dst),
        ])


def _bake_mask(bbox_norm: tuple[float, float, float, float],
               h: int, w: int) -> np.ndarray:
    """bbox = (x, y, w, h) in normalized [0, 1]. Returns HxW uint8, 255 inside."""
    x_n, y_n, w_n, h_n = bbox_norm
    x0 = int(round(x_n * w))
    y0 = int(round(y_n * h))
    x1 = int(round((x_n + w_n) * w))
    y1 = int(round((y_n + h_n) * h))
    x0 = max(0, min(w, x0)); x1 = max(0, min(w, x1))
    y0 = max(0, min(h, y0)); y1 = max(0, min(h, y1))
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[y0:y1, x0:x1] = 255
    return mask


@dataclass
class TaskSpec:
    task_name: str
    source_mp4: Path
    clip_start_sec: float
    bbox_norm: tuple[float, float, float, float]
    task_type: str  # "color" | "deblur"
    category: str
    tags: list[str]
    corruption_desc: str
    instruction_md: str
    corrupt_fn: Callable[[np.ndarray, np.ndarray], np.ndarray]
    # corrupt_fn(frame_bgr, mask_uint8) -> corrupted_bgr
    # When set, corruption is applied only to frames whose clip-relative
    # timestamp falls inside [start_sec, end_sec). Outside the window the
    # corrupted.mp4 contains the original clean frames. Judge weights
    # in-window restoration 85% vs out-window preservation 15%.
    corruption_window_sec: tuple[float, float] | None = None


def build_task(spec: TaskSpec) -> dict:
    task_dir = TASKS_DIR / spec.task_name
    if task_dir.exists():
        shutil.rmtree(task_dir)
    task_dir.mkdir(parents=True)

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        clip = tmp / "clean.mp4"
        _extract_clip(spec.source_mp4, spec.clip_start_sec, clip)

        clean_frames = _read_all_frames_bgr(clip)
        if not clean_frames:
            raise RuntimeError(f"no frames extracted from {clip}")
        h, w = clean_frames[0].shape[:2]
        if (h, w) != (TARGET_H, TARGET_W):
            print(f"  warning: clip is {w}x{h}, expected {TARGET_W}x{TARGET_H}")

        mask = _bake_mask(spec.bbox_norm, h, w)
        # Optional time-gated corruption: corrupt only frames inside the
        # window; everything outside is left clean. This forces the agent
        # to identify *which* frames are degraded as well as repair them.
        if spec.corruption_window_sec is not None:
            w_start_s, w_end_s = spec.corruption_window_sec
            w_start_f = max(0, int(round(w_start_s * TARGET_FPS)))
            w_end_f = min(len(clean_frames), int(round(w_end_s * TARGET_FPS)))
            corrupted_frames = [
                spec.corrupt_fn(f, mask) if w_start_f <= i < w_end_f else f
                for i, f in enumerate(clean_frames)
            ]
        else:
            w_start_f, w_end_f = 0, len(clean_frames)
            corrupted_frames = [spec.corrupt_fn(f, mask) for f in clean_frames]

        corrupted_mp4 = tmp / "corrupted.mp4"
        _write_video_from_frames(corrupted_frames, corrupted_mp4)

        # ---------- Write task dir ----------
        (task_dir / "environment").mkdir(parents=True, exist_ok=True)
        (task_dir / "environment" / "Dockerfile").write_text(DOCKERFILE)
        tags_csv = ", ".join(f'"{t}"' for t in spec.tags)
        (task_dir / "task.toml").write_text(TASK_TOML.format(
            task_name=spec.task_name,
            category=spec.category,
            tags_csv=tags_csv,
            source_name=spec.source_mp4.name,
            corruption_desc=spec.corruption_desc,
        ))

        step = task_dir / "steps" / "solve"
        step.mkdir(parents=True, exist_ok=True)
        (step / "instruction.md").write_text(spec.instruction_md)

        workdir = step / "workdir"
        workdir.mkdir(parents=True, exist_ok=True)
        shutil.copy(corrupted_mp4, workdir / "corrupted.mp4")
        cv2.imwrite(str(workdir / "mask.png"), mask)
        _write_exec(workdir / "setup.sh", SETUP_SH)

        tests = step / "tests"
        tests.mkdir(parents=True, exist_ok=True)
        shutil.copy(clip, tests / "clean.mp4")
        cv2.imwrite(str(tests / "mask.png"), mask)
        _write_exec(tests / "test.sh", TEST_SH.format(task_type=spec.task_type))
        _write_exec(tests / "judge.py", JUDGE_PY)
        if spec.corruption_window_sec is not None:
            w_start_s, w_end_s = spec.corruption_window_sec
            (tests / "gt_window.json").write_text(json.dumps({
                "window_start_s": float(w_start_s),
                "window_end_s": float(w_end_s),
                "window_start_frame": w_start_f,
                "window_end_frame": w_end_f,
                "fps": TARGET_FPS,
                "weights": {"in_window": 0.85, "out_window": 0.15},
            }, indent=2))

        solution = step / "solution"
        solution.mkdir(parents=True, exist_ok=True)
        _write_exec(solution / "solve.sh", SOLVE_SH)

        # Verify
        corrupted_dst = workdir / "corrupted.mp4"
        size_mb = corrupted_dst.stat().st_size / (1024 * 1024)
        n_frames = len(corrupted_frames)
        summary = {
            "task_name": spec.task_name,
            "task_dir": str(task_dir),
            "task_type": spec.task_type,
            "source": str(spec.source_mp4),
            "bbox_norm": list(spec.bbox_norm),
            "mask_shape": [h, w],
            "in_mask_pixels": int((mask > 0).sum()),
            "out_mask_pixels": int((mask == 0).sum()),
            "n_frames": n_frames,
            "corrupted_size_mb": round(size_mb, 2),
        }
        print(json.dumps(summary, indent=2))
        return summary


# ---------------- corruption recipes ----------------
def color_corrupt(delta_h_deg: float, sat_scale: float):
    """Return a corrupt_fn that shifts hue by delta_h_deg and scales sat
    inside the mask (OpenCV HSV: H is 0-179, so hue_shift_unit = delta_h/2).
    """
    h_shift = delta_h_deg / 2.0  # OpenCV scales H to [0, 180)

    def fn(frame_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
        out = frame_bgr.copy()
        # Operate on full frame in HSV space, then composite via mask.
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[..., 0] = (hsv[..., 0] + h_shift) % 180.0
        hsv[..., 1] = np.clip(hsv[..., 1] * sat_scale, 0, 255)
        new_bgr = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
        m = (mask > 0)
        out[m] = new_bgr[m]
        return out

    return fn


def gaussian_blur_corrupt(ksize: int = 15, sigma: float = 3.0):
    def fn(frame_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
        out = frame_bgr.copy()
        blurred = cv2.GaussianBlur(frame_bgr, (ksize, ksize),
                                   sigmaX=sigma, sigmaY=sigma)
        m = (mask > 0)
        out[m] = blurred[m]
        return out

    return fn


def motion_blur_corrupt(length: int = 15, angle_deg: float = 0.0):
    """Linear motion-blur kernel of `length` px at `angle_deg`."""
    kernel = np.zeros((length, length), dtype=np.float32)
    kernel[length // 2, :] = 1.0 / length
    if abs(angle_deg) > 1e-6:
        M = cv2.getRotationMatrix2D((length / 2 - 0.5, length / 2 - 0.5),
                                    angle_deg, 1.0)
        kernel = cv2.warpAffine(kernel, M, (length, length))
        s = kernel.sum()
        if s > 1e-8:
            kernel /= s

    def fn(frame_bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
        out = frame_bgr.copy()
        blurred = cv2.filter2D(frame_bgr, -1, kernel)
        m = (mask > 0)
        out[m] = blurred[m]
        return out

    return fn
