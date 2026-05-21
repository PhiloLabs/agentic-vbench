#!/usr/bin/env python3
"""Score one agentic_vbench_assembly solution: per-slot pick + SSIM honesty.

Per-slot score:
  slot_score = 1 iff pred[i] == CORRECT_PICKS[i] AND SSIM-honesty passes
             = 0 otherwise

SSIM-honesty: sample 3 frames at 25%/50%/75% through each segment's
output range in solution.mp4, sample the matching offsets from the
claimed source clip's source_range, and require every pair's SSIM ≥ 0.95
(same threshold the repair-task preservation gates use — robust to
re-encoding noise, fails on real mismatch).

Reward = (# slots that pass both gates) / n_slots.
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

CORRECT_PICKS = ['10.mp4', '4.mp4', '6.mp4', '8.mp4']

SSIM_THRESHOLD = 0.95
N_SAMPLES = 3  # at 25%, 50%, 75% through each segment


def _normalize(src) -> str:
    """Agent may emit `"3"`, `"3.mp4"`, or `3`; normalize to `"<N>.mp4"`."""
    s = str(src).strip()
    if not s.endswith(".mp4"):
        s = f"{s}.mp4"
    return s


SSIM_MAX_SIDE = 360  # downscale frames before SSIM — 4K SSIM at full
                     # res is prohibitively slow (~25× window search × 3 samples × N slots
                     # blows the verifier timeout). 360p preserves structure for the
                     # identity/diff discrimination this gate is doing.


def _downscale_max(frame: np.ndarray, max_side: int = SSIM_MAX_SIDE) -> np.ndarray:
    h, w = frame.shape[:2]
    m = max(h, w)
    if m <= max_side:
        return frame
    scale = max_side / m
    return cv2.resize(frame, (int(round(w * scale)), int(round(h * scale))),
                      interpolation=cv2.INTER_AREA)


def _ssim_gray(a_bgr: np.ndarray, b_bgr: np.ndarray) -> float:
    """Mean SSIM on grayscale frames. 11×11 Gaussian kernel, σ=1.5.
    Robust to encoder noise (≥0.98 on clean re-encode); drops below 0.95
    on real pixel mismatch (different content, filter, scaling)."""
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


def _read_frames_around(path: Path, t_s: float, n: int = 5,
                       pre_offset_s: float = 0.10):
    """Seek to t_s − pre_offset_s and read up to `n` consecutive frames.
    Returns a list of BGR ndarrays (may be shorter than n at end of video).
    Used to absorb cv2 keyframe-seek imprecision — codec seeks land at
    the nearest keyframe and decode forward, so a single read at a target
    time can be off by 1-3 frames. Comparing a small frame window pair-wise
    finds the matching alignment."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return []
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, (t_s - pre_offset_s) * 1000.0))
    out = []
    for _ in range(n):
        ok, frame = cap.read()
        if not ok:
            break
        out.append(_downscale_max(frame))
    cap.release()
    return out


def _max_ssim_pair(frames_a, frames_b) -> float:
    best = 0.0
    for fa in frames_a:
        for fb in frames_b:
            s = _ssim_gray(fa, fb)
            if s > best:
                best = s
    return best


def _check_honesty(solution_mp4: Path, source_mp4: Path,
                   segment: dict) -> tuple[bool, list]:
    """Sample N frames across the segment's output range and matching
    positions in the source clip's source_range. Returns (pass, details)."""
    try:
        out_lo, out_hi = float(segment["output"][0]), float(segment["output"][1])
        src_lo, src_hi = float(segment["source_range"][0]), float(segment["source_range"][1])
    except (KeyError, IndexError, TypeError, ValueError):
        return False, [{"reason": "malformed segment ranges"}]
    dur_out = out_hi - out_lo
    dur_src = src_hi - src_lo
    if dur_out <= 0 or dur_src <= 0:
        return False, [{"reason": f"non-positive duration out={dur_out} src={dur_src}"}]
    samples = []
    # Sample at internal positions only: 1/(N+1), 2/(N+1), ..., N/(N+1).
    # Avoids both range endpoints; cv2 seek can land off-by-one at exact
    # boundaries on some codecs.
    for k_i in range(1, N_SAMPLES + 1):
        k = k_i / (N_SAMPLES + 1)
        t_out = out_lo + k * dur_out
        t_src = src_lo + k * dur_src
        # Read a small frame window from each video to absorb seek
        # imprecision; pair-wise max SSIM finds the matching alignment.
        f_out_list = _read_frames_around(solution_mp4, t_out)
        f_src_list = _read_frames_around(source_mp4, t_src)
        if not f_out_list or not f_src_list:
            samples.append({"k": round(k, 3), "t_out_s": round(t_out, 3),
                            "t_src_s": round(t_src, 3), "ssim": None,
                            "reason": "frame read failed"})
            return False, samples
        ssim = _max_ssim_pair(f_out_list, f_src_list)
        samples.append({"k": round(k, 3), "t_out_s": round(t_out, 3),
                        "t_src_s": round(t_src, 3), "ssim": round(ssim, 4),
                        "window": f"{len(f_out_list)}x{len(f_src_list)}"})
        if ssim < SSIM_THRESHOLD:
            return False, samples
    return True, samples


def _zero(reason, pred=None):
    return {
        "reward": 0.0,
        "details": {
            "reason": reason,
            "n_slots": len(CORRECT_PICKS),
            "n_correct": 0,
            "n_honest_correct": 0,
            "pred": pred or [],
            "correct": CORRECT_PICKS,
        },
    }


def score(solution_json: Path, solution_mp4: Path, materials_dir: Path) -> dict:
    if not solution_json.exists():
        return _zero(f"solution.json not found at {solution_json}")
    try:
        sol = json.loads(solution_json.read_text())
    except json.JSONDecodeError as e:
        return _zero(f"solution.json invalid JSON: {e}")

    segments = sol.get("segments")
    if not isinstance(segments, list):
        return _zero("solution.json: segments not a list")

    pred = [_normalize(seg.get("source", "")) for seg in segments]
    n = len(CORRECT_PICKS)
    if len(pred) != n:
        return _zero(f"slot count mismatch: expected {n}, got {len(pred)}", pred=pred)

    n_correct = sum(1 for i in range(n) if pred[i] == CORRECT_PICKS[i])

    if not solution_mp4.exists():
        return {
            "reward": 0.0,
            "details": {
                "reason": f"solution.mp4 not found at {solution_mp4}",
                "n_slots": n,
                "n_correct": n_correct,
                "n_honest_correct": 0,
                "pred": pred,
                "correct": CORRECT_PICKS,
            },
        }

    per_slot = []
    n_honest_correct = 0
    for i in range(n):
        slot = {"slot": i, "pred": pred[i], "expected": CORRECT_PICKS[i]}
        if pred[i] != CORRECT_PICKS[i]:
            slot["match"] = False
            slot["honest"] = None  # not checked
            slot["score"] = 0
        else:
            slot["match"] = True
            source_path = materials_dir / pred[i]
            if not source_path.exists():
                slot["honest"] = False
                slot["honesty_reason"] = f"missing source clip {source_path}"
                slot["score"] = 0
            else:
                honest, samples = _check_honesty(solution_mp4, source_path, segments[i])
                slot["honest"] = honest
                slot["samples"] = samples
                slot["score"] = 1 if honest else 0
                if honest:
                    n_honest_correct += 1
        per_slot.append(slot)

    return {
        "reward": n_honest_correct / n,
        "details": {
            "reason": "ok",
            "n_slots": n,
            "n_correct": n_correct,
            "n_honest_correct": n_honest_correct,
            "ssim_threshold": SSIM_THRESHOLD,
            "n_samples_per_segment": N_SAMPLES,
            "pred": pred,
            "correct": CORRECT_PICKS,
            "per_slot": per_slot,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", required=True, type=Path,
                        help="path to solution.json")
    parser.add_argument("--solution-mp4", required=True, type=Path,
                        help="path to solution.mp4")
    parser.add_argument("--materials-dir", required=True, type=Path,
                        help="dir containing the candidate clips (1.mp4 ... N.mp4)")
    parser.add_argument("--reward-json", required=True, type=Path)
    parser.add_argument("--reward-txt", required=True, type=Path)
    args = parser.parse_args()

    result = score(args.solution, args.solution_mp4, args.materials_dir)
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps(result, indent=2))
    args.reward_txt.write_text(f"{result['reward']:.6f}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
