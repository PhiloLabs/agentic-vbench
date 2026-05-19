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
    args.reward_txt.write_text(f"{result['reward']:.6f}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
