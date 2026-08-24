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


FULL_CREDIT_UNITS = 8


def canonical(entry: object) -> tuple[object, ...] | None:
    if not isinstance(entry, dict):
        return None
    half = entry.get("half")
    team = entry.get("team")
    kick_count = entry.get("kick_count")
    zone_path = entry.get("zone_path")
    terminal = entry.get("terminal")
    if isinstance(half, bool) or half not in (1, 2) or team not in VALID_TEAMS:
        return None
    if isinstance(kick_count, bool) or not isinstance(kick_count, int) or kick_count < 2:
        return None
    if not isinstance(zone_path, list) or not zone_path:
        return None
    if any(zone not in VALID_ZONES for zone in zone_path):
        return None
    if any(left == right for left, right in zip(zone_path, zone_path[1:])):
        return None
    if terminal not in VALID_TERMINALS:
        return None
    return half, team, kick_count, tuple(zone_path), terminal


def edit_distance(left: tuple[object, ...], right: tuple[object, ...]) -> int:
    previous = list(range(len(right) + 1))
    for left_item in left:
        current = [previous[0] + 1]
        for index, right_item in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[index] + 1,
                    previous[index - 1] + (left_item != right_item),
                )
            )
        previous = current
    return previous[-1]


def pair_credit_units(
    prediction: tuple[object, ...], ground_truth: tuple[object, ...]
) -> int:
    """Return exact credit or gated detail credit in eighth-point units."""
    if prediction[:2] != ground_truth[:2]:
        return 0
    if prediction == ground_truth:
        return FULL_CREDIT_UNITS

    kick_delta = abs(int(prediction[2]) - int(ground_truth[2]))
    kick_units = 2 if kick_delta == 0 else 1 if kick_delta == 1 else 0
    zone_delta = edit_distance(prediction[3], ground_truth[3])
    zone_units = 2 if zone_delta == 0 else 1 if zone_delta == 1 else 0
    return kick_units + zone_units


def alignment_key(alignment: tuple[int, int, int]) -> tuple[int, int, int]:
    credit_units, full_matches, partial_matches = alignment
    return credit_units, full_matches, -partial_matches


def weighted_ordered_alignment(
    predicted: list[tuple[object, ...]], expected: list[tuple[object, ...]]
) -> tuple[int, int, int]:
    """Maximize gated credit under order-preserving one-to-one alignment."""
    previous = [(0, 0, 0)] * (len(expected) + 1)
    for prediction in predicted:
        current = [(0, 0, 0)]
        for index, ground_truth in enumerate(expected, start=1):
            candidates = [previous[index], current[-1]]
            units = pair_credit_units(prediction, ground_truth)
            if units:
                prior_units, prior_full, prior_partial = previous[index - 1]
                candidates.append(
                    (
                        prior_units + units,
                        prior_full + (units == FULL_CREDIT_UNITS),
                        prior_partial + (units != FULL_CREDIT_UNITS),
                    )
                )
            current.append(max(candidates, key=alignment_key))
        previous = current
    return previous[-1]


def lcs_matches(predicted: list[tuple[object, ...]], expected: list[tuple[object, ...]]) -> int:
    """Return exact order-preserving one-to-one matches for diagnostics."""
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


def f1(credit: float, predicted: int, expected: int) -> tuple[float, float, float]:
    precision = credit / predicted if predicted else 0.0
    recall = credit / expected if expected else 0.0
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
    if any(item is None for item in expected):
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
    credit_units, full_matches, partial_matches = weighted_ordered_alignment(
        predictions, expected
    )
    credit = credit_units / FULL_CREDIT_UNITS
    core_matches = lcs_matches(
        [item[:2] for item in predictions], [item[:2] for item in expected]
    )
    precision, recall, reward = f1(credit, len(predictions_raw), len(expected))

    details = {
        "reason": reason,
        "n_ground_truth": len(expected),
        "n_predicted": len(predictions_raw),
        "n_schema_valid": len(predictions),
        "full_chain_matches": full_matches,
        "partial_chain_matches": partial_matches,
        "credited_matches": round(credit, 4),
        "half_team_core_matches": core_matches,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(reward, 4),
        "matching": "maximum-credit order-preserving one-to-one",
        "credit_policy": {
            "core_gate": ["half", "team"],
            "full": "1.0 for exact kick_count, zone_path, and terminal",
            "partial": {
                "maximum": 0.5,
                "kick_count_exact": 0.25,
                "kick_count_off_by_one": 0.125,
                "zone_path_exact": 0.25,
                "zone_path_edit_distance_one": 0.125,
                "team_or_terminal_standalone": 0.0,
            },
        },
    }
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(
        json.dumps({"reward": round(reward, 4), "details": details}, indent=2) + "\n",
        encoding="utf-8",
    )
    args.reward_txt.write_text(f"{round(reward, 4)}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
