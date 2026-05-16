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
    args.reward_txt.write_text(f"{result['reward']:.6f}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
