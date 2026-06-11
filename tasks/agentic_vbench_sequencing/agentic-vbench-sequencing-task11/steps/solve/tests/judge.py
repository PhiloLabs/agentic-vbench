#!/usr/bin/env python3
"""Score one agentic_vbench_sequencing solution: ordering quality + SSIM honesty.

Ordering metrics (agent's claimed order vs the golden order; vendored from
the primary runner's grade kit):
  ND  — normalized footrule displacement, sum|pred_pos − correct_pos| / (n²//2)
  ADJ — fraction of golden adjacent transitions preserved, / (n−1)
  LIS — longest correctly-ordered subsequence ratio, len(LIS) / len(pred)
  ordering = (1 − ND) · ADJ · LIS   (= 1 for a perfect order)

SSIM-honesty: sample 3 frames at 25%/50%/75% through each segment's
output range in solution.mp4, sample the matching offsets from the
claimed source clip's source_range, and require every pair's SSIM ≥ 0.95
(robust to re-encoding noise, fails on real mismatch). Run on every slot —
under the partial-credit ordering metric a mis-placed clip still earns
score, so its content must be verified too. honesty_factor is the fraction
of slots that pass.

Reward = honesty_factor · ordering.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from bisect import bisect_left
from pathlib import Path

os.environ.setdefault("OPENCV_FFMPEG_THREADS", "1")
os.environ.setdefault("OPENCV_VIDEOIO_PRIORITY_FFMPEG", "100")

import cv2
import numpy as np

cv2.setNumThreads(1)

CORRECT_ORDER = ['19', '20', '15', '18', '1', '3', '5', '10', '7', '14', '17', '8', '4', '11', '13', '9', '2', '12', '6', '16']

SSIM_THRESHOLD = 0.95
N_SAMPLES = 3  # at 25%, 50%, 75% through each segment


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


def _metric_nd(pred: list[str], correct: list[str]) -> float:
    """Normalized footrule displacement, in [0, 1]; lower is better."""
    pred_pos = {c: i for i, c in enumerate(pred)}
    correct_pos = {c: i for i, c in enumerate(correct)}
    n = len(correct)
    total = sum(abs(pred_pos[c] - correct_pos[c]) for c in correct_pos)
    max_total = (n * n) // 2
    return total / max_total if max_total else 0.0


def _metric_lis(pred: list[str], correct: list[str]) -> float:
    """Longest correctly-ordered subsequence ratio, in [0, 1]; higher better."""
    rank = {c: i for i, c in enumerate(correct)}
    seq = [rank[c] for c in pred if c in rank]
    if not seq:
        return 0.0
    tails: list[int] = []
    for x in seq:
        i = bisect_left(tails, x)
        if i == len(tails):
            tails.append(x)
        else:
            tails[i] = x
    return len(tails) / len(pred)


def _metric_adj(pred: list[str], correct: list[str]) -> float:
    """Fraction of true adjacent transitions caught, in [0, 1]; higher better."""
    if len(correct) <= 1:
        return 1.0
    pred_pos = {c: i for i, c in enumerate(pred)}
    caught = 0
    for i in range(len(correct) - 1):
        a, b = correct[i], correct[i + 1]
        if pred_pos.get(b, -2) - pred_pos.get(a, -1) == 1:
            caught += 1
    return caught / (len(correct) - 1)


def _zero(reason, pred=None):
    return {
        "reward": 0.0,
        "details": {
            "reason": reason,
            "n_slots": len(CORRECT_ORDER),
            "n_correct": 0,
            "n_honest": 0,
            "pred": pred or [],
            "correct": CORRECT_ORDER,
        },
    }


class TaskMisconfiguredError(Exception):
    """Provisioned materials do not match the answer key (CORRECT_ORDER);
    the task is misconfigured. Fail loudly rather than producing a score."""


def _assert_materials_match_key(materials_dir: Path) -> None:
    provisioned = {p.stem for p in materials_dir.glob("*.mp4") if p.stem.isdigit()}
    expected = set(CORRECT_ORDER)
    if provisioned != expected:
        order = lambda s: int(s) if s.isdigit() else 0
        raise TaskMisconfiguredError(
            f"materials clips {sorted(provisioned, key=order)} != answer-key clips "
            f"{sorted(expected, key=order)} (have {len(provisioned)}, key wants {len(expected)})"
        )


def score(solution_json: Path, solution_mp4: Path, materials_dir: Path) -> dict:
    _assert_materials_match_key(materials_dir)
    if not solution_json.exists():
        return _zero(f"solution.json not found at {solution_json}")
    try:
        sol = json.loads(solution_json.read_text())
    except json.JSONDecodeError as e:
        return _zero(f"solution.json invalid JSON: {e}")

    segments = sol.get("segments")
    if not isinstance(segments, list):
        return _zero("solution.json: segments not a list")

    pred = [str(seg.get("source", "")) for seg in segments]
    n = len(CORRECT_ORDER)
    if len(pred) != n:
        return _zero(f"slot count mismatch: expected {n}, got {len(pred)}", pred=pred)

    if sorted(pred) != sorted(CORRECT_ORDER):
        return _zero(
            f"slot set mismatch: expected {sorted(CORRECT_ORDER)}, got {sorted(pred)}",
            pred=pred,
        )

    nd = _metric_nd(pred, CORRECT_ORDER)
    lis = _metric_lis(pred, CORRECT_ORDER)
    adj = _metric_adj(pred, CORRECT_ORDER)
    ordering = (1.0 - nd) * adj * lis
    n_correct = sum(1 for i in range(n) if pred[i] == CORRECT_ORDER[i])

    if not solution_mp4.exists():
        return {
            "reward": 0.0,
            "details": {
                "reason": f"solution.mp4 not found at {solution_mp4}",
                "n_slots": n,
                "n_correct": n_correct,
                "nd": nd, "lis": lis, "adj": adj, "ordering": ordering,
                "honesty_factor": 0.0,
                "pred": pred,
                "correct": CORRECT_ORDER,
            },
        }

    # Honesty is verified on every slot: under the partial-credit ordering
    # metric a mis-placed clip still earns score, so its content must be
    # confirmed too (an exact-position-only check wouldn't catch a faked
    # clip in a wrong slot). honesty_factor scales the ordering score.
    per_slot = []
    n_honest = 0
    for i in range(n):
        slot = {"slot": i, "pred": pred[i], "expected": CORRECT_ORDER[i],
                "match": pred[i] == CORRECT_ORDER[i]}
        source_path = materials_dir / f"{pred[i]}.mp4"
        if not source_path.exists():
            slot["honest"] = False
            slot["honesty_reason"] = f"missing source clip {source_path}"
        else:
            honest, samples = _check_honesty(solution_mp4, source_path, segments[i])
            slot["honest"] = honest
            slot["samples"] = samples
            if honest:
                n_honest += 1
        per_slot.append(slot)

    honesty_factor = n_honest / n
    reward = honesty_factor * ordering

    return {
        "reward": reward,
        "details": {
            "reason": "ok",
            "n_slots": n,
            "n_correct": n_correct,
            "nd": nd, "lis": lis, "adj": adj,
            "ordering": ordering,
            "n_honest": n_honest,
            "honesty_factor": honesty_factor,
            "ssim_threshold": SSIM_THRESHOLD,
            "n_samples_per_segment": N_SAMPLES,
            "pred": pred,
            "correct": CORRECT_ORDER,
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

    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = score(args.solution, args.solution_mp4, args.materials_dir)
    except TaskMisconfiguredError as e:
        msg = f"TASK MISCONFIGURED (materials vs answer key out of sync): {e}"
        print(msg, file=sys.stderr)
        result = {"reward": None, "error": "task_misconfigured",
                  "details": {"reason": msg, "correct": CORRECT_ORDER}}
        args.reward_json.write_text(json.dumps(result, indent=2))
        args.reward_txt.write_text("ERROR task_misconfigured\n")
        return 2
    args.reward_json.write_text(json.dumps(result, indent=2))
    args.reward_txt.write_text(f"{result['reward']:.6f}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
