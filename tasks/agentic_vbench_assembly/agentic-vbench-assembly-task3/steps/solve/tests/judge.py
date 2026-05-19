#!/usr/bin/env python3
"""Score one agentic_vbench_assembly solution. Ports the per-slot exact-pick
verifier from video-agent-runner/verifiers/video_assembly/runner.py
(no S3, stdlib only).

Reward = fraction of slots whose `source` matches the baked-in CORRECT_PICKS,
in slot order.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CORRECT_PICKS = ['14.mp4', '6.mp4', '15.mp4', '10.mp4', '3.mp4', '1.mp4']


def _normalize(src) -> str:
    """Agent may emit `"3"`, `"3.mp4"`, or `3`; normalize to `"<N>.mp4"`."""
    s = str(src).strip()
    if not s.endswith(".mp4"):
        s = f"{s}.mp4"
    return s


def _zero(reason):
    return {
        "reward": 0.0,
        "details": {
            "reason": reason,
            "n_slots": len(CORRECT_PICKS),
            "n_correct": 0,
            "pred": [],
            "correct": CORRECT_PICKS,
        },
    }


def score(solution_path):
    if not solution_path.exists():
        return _zero(f"solution.json not found at {solution_path}")
    try:
        sol = json.loads(solution_path.read_text())
    except json.JSONDecodeError as e:
        return _zero(f"solution.json invalid JSON: {e}")

    segments = sol.get("segments")
    if not isinstance(segments, list):
        return _zero("solution.json: segments not a list")

    pred = [_normalize(seg.get("source", "")) for seg in segments]
    n = len(CORRECT_PICKS)
    if len(pred) != n:
        return _zero(f"slot count mismatch: expected {n}, got {len(pred)}")

    correct_count = sum(1 for i in range(n) if pred[i] == CORRECT_PICKS[i])
    reward = correct_count / n

    return {
        "reward": reward,
        "details": {
            "reason": "ok",
            "n_slots": n,
            "n_correct": correct_count,
            "pred": pred,
            "correct": CORRECT_PICKS,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--reward-json", required=True, type=Path)
    parser.add_argument("--reward-txt", required=True, type=Path)
    args = parser.parse_args()

    result = score(args.solution)
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps(result, indent=2))
    args.reward_txt.write_text(f"{result['reward']:.6f}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
