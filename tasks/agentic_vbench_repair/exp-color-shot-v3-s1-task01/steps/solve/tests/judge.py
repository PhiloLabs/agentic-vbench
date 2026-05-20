#!/usr/bin/env python3
"""Color-restoration judge with in/out window scoring.

For each frame i:
    if window_start_frame <= i < window_end_frame  (in-window):
        dE_in[i]   = mean ΔE(output[i], original[i])   -- restoration quality
    else                                                (out-window):
        ssim_out[i] = SSIM(output[i], source[i])       -- preservation gate

    in_window_score  = 1 - clip(mean(dE_in) / 10.0, 0, 1)   -- ΔE: color-faithful
    out_window_score = 1 if mean(ssim_out) >= 0.95 else 0   -- SSIM: identity gate
    reward = 0.90 * in_window_score + 0.10 * out_window_score

Each window uses the metric appropriate to the question it asks: ΔE for
restoration quality (in-window), SSIM for content preservation (out-window).
SSIM tolerates re-encoding noise (~0.98 on clean re-encode); ΔE doesn't (~0.5-1
even on clean re-encode), which previously dragged the oracle ceiling below 1.0.

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
OUT_WINDOW_SSIM_THRESHOLD = 0.95  # out-window: binary "preservation passes" gate


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _ssim_gray(a_bgr: np.ndarray, b_bgr: np.ndarray) -> float:
    """Mean SSIM on grayscale frames. Std implementation (Wang 2004) using
    11×11 Gaussian kernel with σ=1.5. Robust to encoder noise — a clean
    re-encode of the same content scores ≥ 0.98; an agent that actually
    corrupts pixels (filter, brightness shift) drops below 0.95.
    """
    if a_bgr.shape != b_bgr.shape:
        b_bgr = cv2.resize(b_bgr, (a_bgr.shape[1], a_bgr.shape[0]),
                           interpolation=cv2.INTER_AREA)
    a = cv2.cvtColor(a_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    b = cv2.cvtColor(b_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2
    mu_a = cv2.GaussianBlur(a, (11, 11), 1.5)
    mu_b = cv2.GaussianBlur(b, (11, 11), 1.5)
    mu_a_sq, mu_b_sq, mu_ab = mu_a * mu_a, mu_b * mu_b, mu_a * mu_b
    s_a = cv2.GaussianBlur(a * a, (11, 11), 1.5) - mu_a_sq
    s_b = cv2.GaussianBlur(b * b, (11, 11), 1.5) - mu_b_sq
    s_ab = cv2.GaussianBlur(a * b, (11, 11), 1.5) - mu_ab
    num = (2 * mu_ab + C1) * (2 * s_ab + C2)
    den = (mu_a_sq + mu_b_sq + C1) * (s_a + s_b + C2)
    return float(np.mean(num / den))


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
        w_in = float(w.get("in_window", 0.90))
        w_out = float(w.get("out_window", 0.10))

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
            # Out-window switches to SSIM as a binary preservation gate
            # (ΔE was too sensitive to encoder-floor noise; honest re-encode
            # → ΔE ~0.5-1 but SSIM ~0.98).
            ssim_out_sum = 0.0; ssim_out_n = 0
            dE_out_sum = 0.0  # kept for diagnostic only
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
                    ssim_out_sum += _ssim_gray(of, sf)
                    dE_out_sum += _delta_e_lab(of, sf)
                    ssim_out_n += 1
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
            out_coverage = (ssim_out_n / expected_out) if expected_out > 0 else 1.0
            in_coverage = _clip01(in_coverage)
            out_coverage = _clip01(out_coverage)

            end_f_eff = min(end_f, n)
            mean_in = (dE_in_sum / dE_in_n) if dE_in_n else 0.0
            mean_ssim_out = (ssim_out_sum / ssim_out_n) if ssim_out_n else 1.0
            mean_dE_out = (dE_out_sum / ssim_out_n) if ssim_out_n else 0.0
            raw_in = _clip01(1.0 - mean_in / DELTAE_IN_NORM) if dE_in_n else 0.0
            # Binary preservation gate.
            out_pass = mean_ssim_out >= OUT_WINDOW_SSIM_THRESHOLD
            raw_out = 1.0 if out_pass else 0.0
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
                    "n_out_window_frames": ssim_out_n,
                    "expected_in_window_frames": expected_in,
                    "expected_out_window_frames": expected_out,
                    "in_window_coverage": in_coverage,
                    "out_window_coverage": out_coverage,
                    "mean_deltaE_in_window_vs_original": mean_in,
                    "mean_ssim_out_window_vs_source": mean_ssim_out,
                    "mean_deltaE_out_window_vs_source_diag": mean_dE_out,
                    "out_window_ssim_threshold": OUT_WINDOW_SSIM_THRESHOLD,
                    "out_window_preservation_pass": bool(out_pass),
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
