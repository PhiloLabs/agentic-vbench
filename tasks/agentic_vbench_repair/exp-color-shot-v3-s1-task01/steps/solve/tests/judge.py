#!/usr/bin/env python3
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
