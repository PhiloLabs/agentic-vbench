#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


EVENT_FIELDS = {
    "clearance_index",
    "issued_time_s",
    "command_type",
    "target_value",
    "target_unit",
    "issue_altitude_ft",
    "issue_heading_deg",
    "issue_airspeed_kt",
    "maximum_commanded_progress",
    "execution_altitude_ft",
    "execution_heading_deg",
    "execution_airspeed_kt",
    "completion_altitude_ft",
    "completion_heading_deg",
    "completion_airspeed_kt",
    "ending_altitude_ft",
    "ending_heading_deg",
    "ending_airspeed_kt",
    "execution_start_time_s",
    "completion_time_s",
    "status",
    "superseded_by_index",
    "overshoot_bucket",
}
COMMAND_TYPES = {
    "climb",
    "descend",
    "turn_left_heading",
    "turn_right_heading",
    "accelerate",
    "decelerate",
}
STATUSES = {"complied", "complied_late", "superseded", "violated", "incomplete"}
OVERSHOOT_BUCKETS = {"none", "small", "large", "not_applicable"}
UNITS = {"feet", "degrees", "knots"}
TARGET_TOLERANCE = {"feet": 25.0, "degrees": 2.0, "knots": 2.0}
ISSUE_TOLERANCE_S = 2.0
EVENT_TOLERANCE_S = 4.0


def finite_number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def validate_document(value: Any, *, allow_source: bool = False) -> dict[str, Any]:
    allowed_top = {"clearances", "source"} if allow_source else {"clearances"}
    if not isinstance(value, dict) or set(value) - allowed_top or "clearances" not in value:
        raise ValueError("top-level object must contain only clearances")
    if not isinstance(value["clearances"], list):
        raise ValueError("clearances must be an array")

    previous_index = 0
    previous_issue = -math.inf
    for event in value["clearances"]:
        if not isinstance(event, dict) or set(event) != EVENT_FIELDS:
            raise ValueError("each clearance must contain exactly the required fields")
        index = event["clearance_index"]
        issue = event["issued_time_s"]
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or index != previous_index + 1
        ):
            raise ValueError("clearance_index values must be contiguous from 1")
        if not finite_number(issue) or issue < previous_issue or not 0 <= issue < 3600:
            raise ValueError("issued_time_s values must be finite and chronological")
        if event["command_type"] not in COMMAND_TYPES:
            raise ValueError("invalid command_type")
        if event["target_unit"] not in UNITS:
            raise ValueError("invalid target_unit")
        if not finite_number(event["target_value"]):
            raise ValueError("target_value must be finite")
        expected_unit = (
            "degrees"
            if "heading" in event["command_type"]
            else "feet"
            if event["command_type"] in {"climb", "descend"}
            else "knots"
        )
        if event["target_unit"] != expected_unit:
            raise ValueError("target_unit does not match command_type")
        if event["target_unit"] == "degrees" and not 0 <= event["target_value"] < 360:
            raise ValueError("heading targets must be in [0, 360)")
        if event["target_unit"] != "degrees" and event["target_value"] <= 0:
            raise ValueError("altitude and airspeed targets must be positive")
        for field in (
            "issue_altitude_ft",
            "issue_heading_deg",
            "issue_airspeed_kt",
            "maximum_commanded_progress",
            "execution_altitude_ft",
            "execution_heading_deg",
            "execution_airspeed_kt",
            "completion_altitude_ft",
            "completion_heading_deg",
            "completion_airspeed_kt",
            "ending_altitude_ft",
            "ending_heading_deg",
            "ending_airspeed_kt",
            "execution_start_time_s",
            "completion_time_s",
        ):
            timestamp = event[field]
            if field.endswith("_time_s"):
                if timestamp is not None and (
                    not finite_number(timestamp) or timestamp < issue
                ):
                    raise ValueError(f"{field} must be null or a finite time after issue")
            elif timestamp is not None and not finite_number(timestamp):
                raise ValueError(f"{field} must be finite")
        if event["maximum_commanded_progress"] < 0:
            raise ValueError("maximum_commanded_progress cannot be negative")
        for prefix in ("issue", "execution", "completion", "ending"):
            values = (
                event[f"{prefix}_altitude_ft"],
                event[f"{prefix}_heading_deg"],
                event[f"{prefix}_airspeed_kt"],
            )
            if any(value is None for value in values):
                if prefix in {"issue", "ending"}:
                    raise ValueError(f"{prefix} state must be numeric")
                if not all(value is None for value in values):
                    raise ValueError(f"{prefix} state must be entirely null or numeric")
            else:
                if values[0] <= 0 or values[2] <= 0:
                    raise ValueError(f"{prefix} altitude and airspeed must be positive")
                if not 0 <= values[1] < 360:
                    raise ValueError(f"{prefix} heading must be in [0, 360)")
        for prefix, time_field in (
            ("execution", "execution_start_time_s"),
            ("completion", "completion_time_s"),
        ):
            state_is_null = event[f"{prefix}_altitude_ft"] is None
            if state_is_null != (event[time_field] is None):
                raise ValueError(f"{prefix} state nullness must match {time_field}")
        if event["status"] not in STATUSES:
            raise ValueError("invalid status")
        if event["overshoot_bucket"] not in OVERSHOOT_BUCKETS:
            raise ValueError("invalid overshoot_bucket")
        superseded_by = event["superseded_by_index"]
        if superseded_by is not None and (
            not isinstance(superseded_by, int)
            or isinstance(superseded_by, bool)
            or superseded_by <= index
        ):
            raise ValueError("superseded_by_index must refer to a later clearance")
        if event["status"] in {"complied", "complied_late"}:
            if event["execution_start_time_s"] is None or event["completion_time_s"] is None:
                raise ValueError("complied clearances require execution and completion times")
            if superseded_by is not None:
                raise ValueError("complied clearances cannot be superseded")
        elif event["completion_time_s"] is not None:
            raise ValueError("non-complied clearances cannot have completion_time_s")
        if event["status"] == "superseded" and superseded_by is None:
            raise ValueError("superseded clearances require superseded_by_index")
        if event["status"] != "superseded" and superseded_by is not None:
            raise ValueError("only superseded clearances may name a superseding index")
        previous_index = index
        previous_issue = float(issue)
    indexed = {event["clearance_index"]: event for event in value["clearances"]}
    for event in value["clearances"]:
        superseded_by = event["superseded_by_index"]
        if superseded_by is None:
            continue
        later = indexed.get(superseded_by)
        if later is None:
            raise ValueError("superseded_by_index must resolve to an event")
        dimension = (
            "heading"
            if event["target_unit"] == "degrees"
            else "altitude"
            if event["target_unit"] == "feet"
            else "airspeed"
        )
        later_dimension = (
            "heading"
            if later["target_unit"] == "degrees"
            else "altitude"
            if later["target_unit"] == "feet"
            else "airspeed"
        )
        if dimension != later_dimension:
            raise ValueError("supersession must stay on the same control dimension")
    return value


def load_json(path: Path, *, allow_source: bool = False) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, RecursionError, json.JSONDecodeError) as exc:
        raise ValueError(f"unreadable JSON: {exc}") from exc
    return validate_document(value, allow_source=allow_source)


def time_matches(predicted: Any, expected: Any, tolerance_s: float) -> bool:
    if predicted is None or expected is None:
        return predicted is expected
    return abs(float(predicted) - float(expected)) <= tolerance_s


def value_matches(
    predicted: Any,
    expected: Any,
    tolerance: float,
    *,
    circular: bool = False,
) -> bool:
    if predicted is None or expected is None:
        return predicted is expected
    difference = abs(float(predicted) - float(expected))
    if circular:
        difference = abs((float(predicted) - float(expected) + 180.0) % 360.0 - 180.0)
    return difference <= tolerance


def strict_match(predicted: dict[str, Any], expected: dict[str, Any]) -> bool:
    exact_fields = (
        "command_type",
        "target_unit",
        "status",
        "superseded_by_index",
        "overshoot_bucket",
    )
    if any(predicted[field] != expected[field] for field in exact_fields):
        return False
    if not value_matches(
        predicted["target_value"],
        expected["target_value"],
        TARGET_TOLERANCE[expected["target_unit"]],
        circular=expected["target_unit"] == "degrees",
    ):
        return False
    if not value_matches(
        predicted["maximum_commanded_progress"],
        expected["maximum_commanded_progress"],
        TARGET_TOLERANCE[expected["target_unit"]],
    ):
        return False
    for prefix in ("issue", "execution", "completion", "ending"):
        if not value_matches(
            predicted[f"{prefix}_altitude_ft"],
            expected[f"{prefix}_altitude_ft"],
            25.0,
        ):
            return False
        if not value_matches(
            predicted[f"{prefix}_heading_deg"],
            expected[f"{prefix}_heading_deg"],
            2.0,
            circular=True,
        ):
            return False
        if not value_matches(
            predicted[f"{prefix}_airspeed_kt"],
            expected[f"{prefix}_airspeed_kt"],
            2.0,
        ):
            return False
    if not time_matches(
        predicted["issued_time_s"], expected["issued_time_s"], ISSUE_TOLERANCE_S
    ):
        return False
    return all(
        time_matches(predicted[field], expected[field], EVENT_TOLERANCE_S)
        for field in ("execution_start_time_s", "completion_time_s")
    )


def monotonic_matches(
    predicted: list[dict[str, Any]], expected: list[dict[str, Any]]
) -> int:
    table = [[0] * (len(expected) + 1) for _ in range(len(predicted) + 1)]
    for i, predicted_event in enumerate(predicted, start=1):
        for j, expected_event in enumerate(expected, start=1):
            if strict_match(predicted_event, expected_event):
                table[i][j] = table[i - 1][j - 1] + 1
            else:
                table[i][j] = max(table[i - 1][j], table[i][j - 1])
    return table[-1][-1]


def score(prediction: dict[str, Any], ground_truth: dict[str, Any]) -> dict[str, Any]:
    predicted = prediction["clearances"]
    expected = ground_truth["clearances"]
    true_positives = monotonic_matches(predicted, expected)
    false_positives = len(predicted) - true_positives
    false_negatives = len(expected) - true_positives
    precision = (
        true_positives / (true_positives + false_positives)
        if true_positives + false_positives
        else 0.0
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if true_positives + false_negatives
        else 0.0
    )
    clearance_f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    predicted_legs: dict[int, list[dict[str, Any]]] = {}
    expected_legs: dict[int, list[dict[str, Any]]] = {}
    for event in predicted:
        predicted_legs.setdefault(int(event["issued_time_s"] // 720), []).append(event)
    for event in expected:
        expected_legs.setdefault(int(event["issued_time_s"] // 720), []).append(event)
    exact_legs = 0
    for leg, expected_events in expected_legs.items():
        predicted_events = predicted_legs.get(leg, [])
        if (
            len(predicted_events) == len(expected_events)
            and monotonic_matches(predicted_events, expected_events) == len(expected_events)
        ):
            exact_legs += 1
    leg_accuracy = exact_legs / len(expected_legs) if expected_legs else 0.0
    reward = 0.9 * leg_accuracy + 0.1 * clearance_f1
    return {
        "reward": round(reward, 4),
        "details": {
            "reason": "ok",
            "strict_leg_chains": exact_legs,
            "n_leg_chains": len(expected_legs),
            "leg_chain_accuracy": round(leg_accuracy, 4),
            "clearance_chain_f1": round(clearance_f1, 4),
            "strict_matches": true_positives,
            "n_predicted": len(predicted),
            "n_ground_truth": len(expected),
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "issued_time_tolerance_s": ISSUE_TOLERANCE_S,
            "event_time_tolerance_s": EVENT_TOLERANCE_S,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--ground-truth", required=True, type=Path)
    parser.add_argument("--reward-json", required=True, type=Path)
    parser.add_argument("--reward-txt", required=True, type=Path)
    args = parser.parse_args()

    try:
        result = score(
            load_json(args.solution),
            load_json(args.ground_truth, allow_source=True),
        )
    except (OverflowError, RecursionError, TypeError, ValueError) as exc:
        result = {
            "reward": 0.0,
            "details": {
                "reason": str(exc),
                "strict_matches": 0,
                "n_predicted": 0,
                "n_ground_truth": 0,
                "false_positives": 0,
                "false_negatives": 0,
                "precision": 0.0,
                "recall": 0.0,
                "issued_time_tolerance_s": ISSUE_TOLERANCE_S,
                "event_time_tolerance_s": EVENT_TOLERANCE_S,
            },
        }

    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    args.reward_txt.write_text(f"{result['reward']}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
