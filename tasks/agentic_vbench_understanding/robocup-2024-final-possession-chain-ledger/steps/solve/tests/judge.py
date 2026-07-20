#!/usr/bin/env python3
"""Deterministically grade an ordered RoboCup possession-chain ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


VALID_TEAMS = {"white", "black"}
VALID_ZONES = {"defensive", "middle", "attacking"}
VALID_TERMINALS = {"turnover", "stoppage", "goal"}
MAX_PREDICTIONS = 500


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--reward-json", required=True, type=Path)
    parser.add_argument("--reward-txt", required=True, type=Path)
    return parser.parse_args()


def canonical(entry: object, *, loose: bool = False) -> tuple[object, ...] | None:
    if not isinstance(entry, dict):
        return None
    half = entry.get("half")
    team = entry.get("team")
    kick_count = entry.get("kick_count")
    zone_path = entry.get("zone_path")
    terminal = entry.get("terminal")
    if half not in (1, 2) or team not in VALID_TEAMS:
        return None
    if isinstance(kick_count, bool) or not isinstance(kick_count, int) or kick_count < 2:
        return None
    if loose:
        return half, team, kick_count
    if not isinstance(zone_path, list) or not zone_path:
        return None
    if any(zone not in VALID_ZONES for zone in zone_path):
        return None
    if any(left == right for left, right in zip(zone_path, zone_path[1:])):
        return None
    if terminal not in VALID_TERMINALS:
        return None
    return half, team, kick_count, tuple(zone_path), terminal


def lcs_matches(predicted: list[tuple[object, ...]], expected: list[tuple[object, ...]]) -> int:
    """Return exact order-preserving one-to-one matches."""
    previous = [0] * (len(expected) + 1)
    for prediction in predicted:
        current = [0]
        for index, ground_truth in enumerate(expected, start=1):
            if prediction == ground_truth:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[-1]))
        previous = current
    return previous[-1]


def f1(tp: int, predicted: int, expected: int) -> tuple[float, float, float]:
    precision = tp / predicted if predicted else 0.0
    recall = tp / expected if expected else 0.0
    score = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return precision, recall, score


def main() -> None:
    args = parse_args()
    ground_truth_path = Path(__file__).with_name("ground_truth.json")
    expected_raw = json.loads(ground_truth_path.read_text(encoding="utf-8"))["chains"]
    expected = [canonical(entry) for entry in expected_raw]
    expected_loose = [canonical(entry, loose=True) for entry in expected_raw]
    if any(item is None for item in expected + expected_loose):
        raise RuntimeError("invalid verifier ground truth")

    reason = "ok"
    predictions_raw: list[object] = []
    try:
        solution = json.loads(args.solution.read_text(encoding="utf-8"))
        predictions_raw = solution.get("chains", [])
        if not isinstance(predictions_raw, list):
            raise ValueError("chains is not a list")
        if len(predictions_raw) > MAX_PREDICTIONS:
            raise ValueError(f"chains exceeds {MAX_PREDICTIONS} entries")
    except Exception as exc:  # malformed output deterministically scores zero
        reason = f"unreadable solution.json: {exc}"
        predictions_raw = []

    predictions = [item for entry in predictions_raw if (item := canonical(entry)) is not None]
    predictions_loose = [
        item for entry in predictions_raw if (item := canonical(entry, loose=True)) is not None
    ]
    full_matches = lcs_matches(predictions, expected)
    loose_matches = lcs_matches(predictions_loose, expected_loose)
    precision, recall, reward = f1(full_matches, len(predictions_raw), len(expected))

    details = {
        "reason": reason,
        "n_ground_truth": len(expected),
        "n_predicted": len(predictions_raw),
        "n_schema_valid": len(predictions),
        "full_chain_matches": full_matches,
        "half_team_kick_count_matches": loose_matches,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(reward, 4),
        "matching": "exact order-preserving one-to-one",
    }
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(
        json.dumps({"reward": round(reward, 4), "details": details}, indent=2) + "\n",
        encoding="utf-8",
    )
    args.reward_txt.write_text(f"{round(reward, 4)}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
