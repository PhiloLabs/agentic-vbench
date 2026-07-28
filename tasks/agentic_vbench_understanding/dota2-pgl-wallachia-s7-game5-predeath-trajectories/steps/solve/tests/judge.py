#!/usr/bin/env python3
"""Deterministically grade Dota 2 pre-death minimap trajectories."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Callable


PLAYERS = {
    "watson",
    "CHIRA_JUNIOR",
    "DM",
    "Malady",
    "Saksa",
    "tOfu",
    "Ace",
    "Nisha",
    "Boxi",
    "m1CKe",
}
PLAYER_ALIASES = {name.casefold(): name for name in PLAYERS}
CELL_FIELDS = ("cell_10s_before", "cell_5s_before", "death_cell")
MAX_EVENTS = 120
CLOCK_TOLERANCE_S = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", type=Path, required=True)
    parser.add_argument("--reward-json", type=Path, required=True)
    parser.add_argument("--reward-txt", type=Path, required=True)
    parser.add_argument("--details-json", type=Path, required=True)
    return parser.parse_args()


def clock_seconds(value: object) -> int | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"(\d{1,3}):(\d{2})", value.strip())
    if match is None:
        return None
    minutes, seconds = (int(part) for part in match.groups())
    if seconds >= 60:
        return None
    return minutes * 60 + seconds


def normalize_player(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return PLAYER_ALIASES.get(value.strip().casefold())


def parse_cell(value: object) -> tuple[int, int] | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"([A-Na-n])(14|13|12|11|10|[1-9])", value.strip())
    if match is None:
        return None
    return ord(match.group(1).upper()) - ord("A"), int(match.group(2)) - 1


def parse_event(value: object) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    game = value.get("game")
    if isinstance(game, bool) or not isinstance(game, int) or game != 5:
        return None
    clock = clock_seconds(value.get("clock"))
    victim = normalize_player(value.get("victim"))
    killer = normalize_player(value.get("killer"))
    cells = {field: parse_cell(value.get(field)) for field in CELL_FIELDS}
    if (
        clock is None
        or victim is None
        or killer is None
        or any(cell is None for cell in cells.values())
    ):
        return None
    return {
        "game": game,
        "clock": clock,
        "victim": victim,
        "killer": killer,
        **cells,
    }


def flatten(values: list[object]) -> list[dict[str, Any]]:
    return [parsed for value in values if (parsed := parse_event(value)) is not None]


def same_time(prediction: dict[str, Any], target: dict[str, Any]) -> bool:
    return (
        prediction["game"] == target["game"]
        and abs(prediction["clock"] - target["clock"]) <= CLOCK_TOLERANCE_S
    )


def same_victim(prediction: dict[str, Any], target: dict[str, Any]) -> bool:
    return same_time(prediction, target) and prediction["victim"] == target["victim"]


def same_killer(prediction: dict[str, Any], target: dict[str, Any]) -> bool:
    return same_victim(prediction, target) and prediction["killer"] == target["killer"]


def cell_distance(
    prediction: dict[str, Any], target: dict[str, Any], field: str
) -> int:
    predicted_cell = prediction[field]
    target_cell = target[field]
    return max(
        abs(predicted_cell[0] - target_cell[0]),
        abs(predicted_cell[1] - target_cell[1]),
    )


def same_cell(field: str) -> Callable[[dict[str, Any], dict[str, Any]], bool]:
    return lambda prediction, target: (
        same_killer(prediction, target) and cell_distance(prediction, target, field) == 0
    )


def same_exact_trajectory(prediction: dict[str, Any], target: dict[str, Any]) -> bool:
    return same_killer(prediction, target) and all(
        cell_distance(prediction, target, field) == 0 for field in CELL_FIELDS
    )


def same_neighboring_trajectory(
    prediction: dict[str, Any], target: dict[str, Any]
) -> bool:
    return same_killer(prediction, target) and all(
        cell_distance(prediction, target, field) <= 1 for field in CELL_FIELDS
    )


def maximum_matches(
    predicted: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    compatible: Callable[[dict[str, Any], dict[str, Any]], bool],
) -> int:
    edges = [
        sorted(
            (index for index, target in enumerate(expected) if compatible(item, target)),
            key=lambda index: abs(item["clock"] - expected[index]["clock"]),
        )
        for item in predicted
    ]
    target_to_prediction = [-1] * len(expected)

    def augment(prediction_index: int, seen: set[int]) -> bool:
        for target_index in edges[prediction_index]:
            if target_index in seen:
                continue
            seen.add(target_index)
            owner = target_to_prediction[target_index]
            if owner == -1 or augment(owner, seen):
                target_to_prediction[target_index] = prediction_index
                return True
        return False

    return sum(augment(index, set()) for index in range(len(predicted)))


def f1(matches: int, predicted_count: int, expected_count: int) -> dict[str, float | int]:
    precision = matches / predicted_count if predicted_count else 0.0
    recall = matches / expected_count if expected_count else 0.0
    score = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "matches": matches,
        "predicted": predicted_count,
        "expected": expected_count,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(score, 6),
    }


def component(
    predicted: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    raw_predicted_count: int,
    compatible: Callable[[dict[str, Any], dict[str, Any]], bool],
) -> dict[str, float | int]:
    return f1(
        maximum_matches(predicted, expected, compatible),
        raw_predicted_count,
        len(expected),
    )


def main() -> None:
    args = parse_args()
    expected_raw = json.loads(
        Path(__file__).with_name("ground_truth.json").read_text(encoding="utf-8")
    )["events"]
    expected = flatten(expected_raw)

    reason = "ok"
    predicted_raw: list[object] = []
    try:
        solution = json.loads(args.solution.read_text(encoding="utf-8"))
        predicted_raw = solution.get("events", [])
        if not isinstance(predicted_raw, list):
            raise ValueError("events is not a list")
        if len(predicted_raw) > MAX_EVENTS:
            raise ValueError(f"events exceeds {MAX_EVENTS} entries")
        predicted = flatten(predicted_raw)
    except Exception as exc:
        reason = f"unreadable solution.json: {exc}"
        predicted_raw = []
        predicted = []

    raw_count = len(predicted_raw)
    components = {
        "event_localization": component(predicted, expected, raw_count, same_time),
        "victim_attribution": component(predicted, expected, raw_count, same_victim),
        "killer_attribution": component(predicted, expected, raw_count, same_killer),
        "cell_10s_before": component(
            predicted, expected, raw_count, same_cell("cell_10s_before")
        ),
        "cell_5s_before": component(
            predicted, expected, raw_count, same_cell("cell_5s_before")
        ),
        "death_cell": component(predicted, expected, raw_count, same_cell("death_cell")),
        "neighboring_trajectory": component(
            predicted, expected, raw_count, same_neighboring_trajectory
        ),
        "exact_trajectory": component(
            predicted, expected, raw_count, same_exact_trajectory
        ),
    }
    reward = round(float(components["exact_trajectory"]["f1"]), 4)
    details = {
        "reason": reason,
        "n_ground_truth_events": len(expected_raw),
        "n_predicted_events": raw_count,
        "n_schema_valid_events": len(predicted),
        "game": 5,
        "clock_tolerance_s": CLOCK_TOLERANCE_S,
        "grid": "14x14; exact three-point trajectory required for reward",
        "reward_metric": "F1 over exact game/time/victim/killer/three-cell trajectories",
        "components": components,
        "reward": reward,
    }
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.details_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(
        json.dumps({"reward": reward}, indent=2) + "\n",
        encoding="utf-8",
    )
    args.reward_txt.write_text(f"{reward}\n", encoding="utf-8")
    args.details_json.write_text(
        json.dumps(details, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
