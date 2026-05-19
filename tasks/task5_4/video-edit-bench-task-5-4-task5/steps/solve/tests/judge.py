#!/usr/bin/env python3
"""Score one task5_4 solution. Ports the three metrics from
video-agent-runner/verifiers/video_order/runner.py (no S3, stdlib only).

Composite reward = 0.4*(1-nd) + 0.3*lis + 0.3*adj in [0,1].
"""
from __future__ import annotations

import argparse
import json
import sys
from bisect import bisect_left
from pathlib import Path

CORRECT_ORDER = ['3', '6', '2', '9', '1', '4', '8', '7', '5']


def metric_nd(pred, correct):
    pred_pos = {c: i for i, c in enumerate(pred)}
    correct_pos = {c: i for i, c in enumerate(correct)}
    n = len(correct)
    total = sum(abs(pred_pos[c] - correct_pos[c]) for c in correct_pos)
    max_total = (n * n) // 2
    return total / max_total if max_total else 0.0


def metric_lis(pred, correct):
    rank = {c: i for i, c in enumerate(correct)}
    seq = [rank[c] for c in pred if c in rank]
    if not seq:
        return 0.0
    tails = []
    for x in seq:
        i = bisect_left(tails, x)
        if i == len(tails):
            tails.append(x)
        else:
            tails[i] = x
    return len(tails) / len(pred)


def metric_adj(pred, correct):
    if len(correct) <= 1:
        return 1.0
    pred_pos = {c: i for i, c in enumerate(pred)}
    caught = 0
    for i in range(len(correct) - 1):
        a, b = correct[i], correct[i + 1]
        if pred_pos.get(b, -2) - pred_pos.get(a, -1) == 1:
            caught += 1
    return caught / (len(correct) - 1)


def _zero(reason):
    return {
        "reward": 0.0,
        "details": {
            "reason": reason,
            "nd_score": 0.0,
            "lis_score": 0.0,
            "adj_score": 0.0,
            "strict_match": 0.0,
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

    pred = [str(seg.get("source", "")) for seg in segments]
    if sorted(pred) != sorted(CORRECT_ORDER):
        return _zero(
            f"slot set mismatch: expected {sorted(CORRECT_ORDER)}, got {sorted(pred)}"
        )

    nd = metric_nd(pred, CORRECT_ORDER)
    lis = metric_lis(pred, CORRECT_ORDER)
    adj = metric_adj(pred, CORRECT_ORDER)
    strict = 1.0 if pred == CORRECT_ORDER else 0.0
    nd_score = 1.0 - nd
    final = 0.4 * nd_score + 0.3 * lis + 0.3 * adj

    return {
        "reward": final,
        "details": {
            "reason": "ok",
            "nd_score": nd_score,
            "lis_score": lis,
            "adj_score": adj,
            "strict_match": strict,
            "pred": pred,
            "correct": CORRECT_ORDER,
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
