#!/usr/bin/env python3
"""Score one task7_3 solution.

Ports the per-slot-exact-match metric from
`video-agent-runner/verifiers/video_assembly/runner.py` (no S3, stdlib only).

Reward = n_correct / n_slots in [0, 1]; 1.0 = every slot picked correctly.
A strict-match binary signal is reported as a side-channel detail but does
not affect the reward (matches the upstream weight=0 convention).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Answer key already uses the "{N}.mp4" suffix from the HF dataset.
CORRECT_PICKS = ['6.mp4', '2.mp4', '3.mp4']


def _normalize(src) -> str:
    """Agent may emit `"3"`, `"3.mp4"`, or `3`; normalize to `"<N>.mp4"`."""
    s = str(src).strip()
    if not s.endswith(".mp4"):
        s = f"{s}.mp4"
    return s


def _zero(reason) -> dict:
    return {
        "reward": 0.0,
        "details": {
            "reason": reason,
            "assembly_score": 0.0,
            "strict_match": 0.0,
        },
    }


def score(solution_path: Path) -> dict:
    if not solution_path.exists():
        return _zero(f"solution.json not found at {solution_path}")
    try:
        sol = json.loads(solution_path.read_text())
    except json.JSONDecodeError as e:
        return _zero(f"solution.json invalid JSON: {e}")

    segments = sol.get("segments")
    if not isinstance(segments, list):
        return _zero("solution.json: segments not a list")

    n_slots = len(CORRECT_PICKS)
    if len(segments) != n_slots:
        return _zero(
            f"malformed: expected {n_slots} segments, got {len(segments)}"
        )

    picks = [_normalize(seg.get("source", "")) for seg in segments]
    n_correct = sum(1 for p, c in zip(picks, CORRECT_PICKS) if p == c)
    reward = n_correct / n_slots
    strict = 1.0 if picks == CORRECT_PICKS else 0.0

    return {
        "reward": reward,
        "details": {
            "reason": "ok",
            "assembly_score": reward,
            "strict_match": strict,
            "n_correct": n_correct,
            "n_slots": n_slots,
            "picks": picks,
            "correct": CORRECT_PICKS,
        },
    }


def main() -> int:
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
