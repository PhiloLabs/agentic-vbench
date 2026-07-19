#!/usr/bin/env python3
"""Deterministically grade an ordered Melee conversion ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


VALID_ATTACKERS = {"Ferriswheel", "Zain", "JoJo", "Bard", "Axe", "SRM13"}
VALID_BANDS = {"light", "heavy", "devastating"}
VALID_TERMINALS = {"escape", "reversal", "kill"}
MAX_PREDICTIONS = 300


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--reward-json", required=True, type=Path)
    parser.add_argument("--reward-txt", required=True, type=Path)
    return parser.parse_args()


def canonical(entry: object, *, core: bool = False) -> tuple[object, ...] | None:
    if not isinstance(entry, dict):
        return None
    game = entry.get("game")
    attacker = entry.get("attacker")
    stock = entry.get("victim_stock_before")
    hit_count = entry.get("hit_count")
    damage_band = entry.get("damage_band")
    terminal = entry.get("terminal")
    if isinstance(game, bool) or not isinstance(game, int) or not 1 <= game <= 10:
        return None
    if attacker not in VALID_ATTACKERS:
        return None
    if isinstance(stock, bool) or not isinstance(stock, int) or not 1 <= stock <= 4:
        return None
    if isinstance(hit_count, bool) or not isinstance(hit_count, int) or hit_count < 1:
        return None
    if terminal not in VALID_TERMINALS or damage_band not in VALID_BANDS:
        return None
    if terminal != "kill" and hit_count < 4:
        return None
    if core:
        return game, attacker, stock, terminal
    return game, attacker, stock, hit_count, damage_band, terminal


def lcs_matches(predicted: list[tuple[object, ...]], expected: list[tuple[object, ...]]) -> int:
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
    expected_raw = json.loads(
        Path(__file__).with_name("ground_truth.json").read_text(encoding="utf-8")
    )["events"]
    expected = [canonical(entry) for entry in expected_raw]
    expected_core = [canonical(entry, core=True) for entry in expected_raw]
    if any(item is None for item in expected + expected_core):
        raise RuntimeError("invalid verifier ground truth")

    reason = "ok"
    predictions_raw: list[object] = []
    try:
        solution = json.loads(args.solution.read_text(encoding="utf-8"))
        predictions_raw = solution.get("events", [])
        if not isinstance(predictions_raw, list):
            raise ValueError("events is not a list")
        if len(predictions_raw) > MAX_PREDICTIONS:
            raise ValueError(f"events exceeds {MAX_PREDICTIONS} entries")
    except Exception as exc:
        reason = f"unreadable solution.json: {exc}"
        predictions_raw = []

    predictions = [item for entry in predictions_raw if (item := canonical(entry)) is not None]
    predictions_core = [
        item for entry in predictions_raw if (item := canonical(entry, core=True)) is not None
    ]
    full_matches = lcs_matches(predictions, expected)
    core_matches = lcs_matches(predictions_core, expected_core)
    precision, recall, reward = f1(full_matches, len(predictions_raw), len(expected))

    details = {
        "reason": reason,
        "n_ground_truth": len(expected),
        "n_predicted": len(predictions_raw),
        "n_schema_valid": len(predictions),
        "full_event_matches": full_matches,
        "core_game_attacker_stock_terminal_matches": core_matches,
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
