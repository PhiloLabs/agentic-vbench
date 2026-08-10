#!/usr/bin/env python3
"""Deterministic ordered event and state scorer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


TOP_KEYS = {"episodes"}
EPISODE_KEYS = {"episode_id", "events"}
EVENT_KEYS = {"timestamp_ms", "event_type", "entity_id", "state"}
STATE_FIELDS = (
    "active_weapon",
    "held_keys",
    "active_switches",
    "open_doors",
    "current_checkpoint",
)
STATE_KEYS = set(STATE_FIELDS)
FULL_EVENT_WEIGHT = 0.90
GATED_FIELD_WEIGHT = 0.10
EPISODE_IDS = {f"episode_{index:02d}" for index in range(1, 7)}
EVENT_ENTITIES = {
    "key_pickup": {"blue_key", "yellow_key", "red_key"},
    "weapon_pickup": {
        "shotgun",
        "chaingun",
        "rocket_launcher",
        "plasma_rifle",
    },
    "switch_activate": {
        "switch_amber",
        "switch_cyan",
        "switch_violet",
        "switch_white",
    },
    "checkpoint_activate": {"checkpoint_alpha", "checkpoint_beta"},
    "locked_door_open": {"door_blue", "door_yellow", "door_red"},
    "checkpoint_restore": {"checkpoint_alpha", "checkpoint_beta"},
    "level_exit": {"episode_exit"},
}
WEAPONS = {
    "pistol",
    "shotgun",
    "chaingun",
    "rocket_launcher",
    "plasma_rifle",
}
KEYS = {"blue_key", "yellow_key", "red_key"}
SWITCHES = {
    "switch_amber",
    "switch_cyan",
    "switch_violet",
    "switch_white",
}
DOORS = {"door_blue", "door_yellow", "door_red"}
CHECKPOINTS = {"checkpoint_alpha", "checkpoint_beta"}
MAX_SOLUTION_BYTES = 1_000_000
MAX_EVENTS_PER_EPISODE = 100


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _set_field(
    state: dict[str, Any],
    field: str,
    vocabulary: set[str],
) -> tuple[str, ...]:
    values = state[field]
    if (
        not isinstance(values, list)
        or any(value not in vocabulary for value in values)
        or len(values) != len(set(values))
    ):
        raise ValueError(f"invalid {field}")
    return tuple(sorted(values))


def _state(value: Any) -> tuple[Any, ...]:
    if not isinstance(value, dict) or set(value) != STATE_KEYS:
        raise ValueError("invalid state schema")
    weapon = value["active_weapon"]
    checkpoint = value["current_checkpoint"]
    if weapon not in WEAPONS:
        raise ValueError("unknown active weapon")
    if checkpoint is not None and checkpoint not in CHECKPOINTS:
        raise ValueError("unknown checkpoint")
    return (
        weapon,
        _set_field(value, "held_keys", KEYS),
        _set_field(value, "active_switches", SWITCHES),
        _set_field(value, "open_doors", DOORS),
        checkpoint,
    )


def _episodes(
    document: Any,
    require_all: bool,
) -> dict[str, list[Any]]:
    if not isinstance(document, dict) or set(document) != TOP_KEYS:
        raise ValueError("invalid top-level schema")
    values = document["episodes"]
    if not isinstance(values, list) or len(values) > len(EPISODE_IDS):
        raise ValueError("invalid episodes array")
    result: dict[str, list[Any]] = {}
    for episode in values:
        if not isinstance(episode, dict) or set(episode) != EPISODE_KEYS:
            raise ValueError("invalid episode schema")
        episode_id = episode["episode_id"]
        events = episode["events"]
        if episode_id not in EPISODE_IDS or episode_id in result:
            raise ValueError("unknown or duplicate episode")
        if not isinstance(events, list) or len(events) > MAX_EVENTS_PER_EPISODE:
            raise ValueError("invalid events array")
        previous = -1
        normalized: list[Any] = []
        for event in events:
            if not isinstance(event, dict) or set(event) != EVENT_KEYS:
                raise ValueError("invalid event schema")
            timestamp = event["timestamp_ms"]
            event_type = event["event_type"]
            entity = event["entity_id"]
            if (
                isinstance(timestamp, bool)
                or not isinstance(timestamp, int)
                or timestamp < previous
                or timestamp < 0
            ):
                raise ValueError("invalid event timestamp")
            if (
                event_type not in EVENT_ENTITIES
                or entity not in EVENT_ENTITIES[event_type]
            ):
                raise ValueError("invalid event identity")
            normalized.append(
                (
                    timestamp,
                    event_type,
                    entity,
                    _state(event["state"]),
                )
            )
            previous = timestamp
        result[episode_id] = normalized
    if require_all and set(result) != EPISODE_IDS:
        raise ValueError("all six episodes are required")
    return result


def _identity_matches(left: Any, right: Any, tolerance_ms: int) -> bool:
    return (
        left[1:3] == right[1:3]
        and abs(left[0] - right[0]) <= tolerance_ms
    )


def _better_alignment(
    left: tuple[int, int, tuple[tuple[int, int], ...]],
    right: tuple[int, int, tuple[tuple[int, int], ...]],
) -> tuple[int, int, tuple[tuple[int, int], ...]]:
    def key(
        value: tuple[int, int, tuple[tuple[int, int], ...]],
    ) -> tuple[Any, ...]:
        return (
            -value[0],
            value[1],
            tuple(
                (prediction_index, truth_index)
                for truth_index, prediction_index in value[2]
            ),
        )

    return left if key(left) <= key(right) else right


def _ordered_alignment(
    truth: list[Any],
    prediction: list[Any],
    tolerance_ms: int,
) -> tuple[tuple[int, int], ...]:
    empty: tuple[int, int, tuple[tuple[int, int], ...]] = (0, 0, ())
    previous = [empty] * (len(prediction) + 1)
    for truth_index, truth_event in enumerate(truth):
        current = [empty]
        for prediction_index, predicted_event in enumerate(prediction):
            best = _better_alignment(
                previous[prediction_index + 1],
                current[-1],
            )
            if _identity_matches(
                truth_event,
                predicted_event,
                tolerance_ms,
            ):
                base = previous[prediction_index]
                candidate = (
                    base[0] + 1,
                    base[1] + abs(truth_event[0] - predicted_event[0]),
                    base[2] + ((truth_index, prediction_index),),
                )
                best = _better_alignment(best, candidate)
            current.append(best)
        previous = current
    return previous[-1][2]


def score(
    ground_truth: Any,
    prediction: Any,
    tolerance_ms: int = 750,
) -> dict[str, Any]:
    truth = _episodes(ground_truth, require_all=True)
    parse_error = None
    try:
        predicted = _episodes(prediction, require_all=True)
    except ValueError as error:
        predicted = {}
        parse_error = str(error)
    details: dict[str, Any] = {}
    rewards: list[float] = []
    for episode_id in sorted(EPISODE_IDS):
        truth_events = truth[episode_id]
        predicted_events = predicted.get(episode_id, [])
        alignment = _ordered_alignment(
            truth_events,
            predicted_events,
            tolerance_ms,
        )
        denominator = len(truth_events) + len(predicted_events)
        full_matches = 0
        field_matches = {field: 0 for field in STATE_FIELDS}
        for truth_index, prediction_index in alignment:
            truth_state = truth_events[truth_index][3]
            predicted_state = predicted_events[prediction_index][3]
            if truth_state == predicted_state:
                full_matches += 1
            for field_index, field in enumerate(STATE_FIELDS):
                if truth_state[field_index] == predicted_state[field_index]:
                    field_matches[field] += 1
        full_event_f1 = (
            0.0 if denominator == 0 else 2.0 * full_matches / denominator
        )
        field_f1 = {
            field: (
                0.0
                if denominator == 0
                else 2.0 * field_matches[field] / denominator
            )
            for field in STATE_FIELDS
        }
        gated_field_f1 = sum(field_f1.values()) / len(STATE_FIELDS)
        reward = (
            FULL_EVENT_WEIGHT * full_event_f1
            + GATED_FIELD_WEIGHT * gated_field_f1
        )
        rewards.append(reward)
        details[episode_id] = {
            "ground_truth_events": len(truth_events),
            "predicted_events": len(predicted_events),
            "identity_time_matches": len(alignment),
            "full_state_matches": full_matches,
            "field_exact_matches": field_matches,
            "full_event_f1": round(full_event_f1, 6),
            "field_f1": {
                field: round(value, 6)
                for field, value in field_f1.items()
            },
            "gated_field_f1": round(gated_field_f1, 6),
            "episode_reward": round(reward, 6),
        }
    return {
        "reward": round(sum(rewards) / len(rewards), 6),
        "details": {
            "parse_error": parse_error,
            "timestamp_tolerance_ms": tolerance_ms,
            "weights": {
                "full_event_f1": FULL_EVENT_WEIGHT,
                "gated_field_f1": GATED_FIELD_WEIGHT,
            },
            "episodes": details,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", required=True, type=Path)
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--reward-json", required=True, type=Path)
    parser.add_argument("--reward-txt", required=True, type=Path)
    args = parser.parse_args()
    ground_truth = json.loads(
        args.ground_truth.read_text(encoding="utf-8"),
        parse_constant=_reject_constant,
    )
    try:
        if args.solution.stat().st_size > MAX_SOLUTION_BYTES:
            raise ValueError("solution is too large")
        prediction = json.loads(
            args.solution.read_text(encoding="utf-8"),
            parse_constant=_reject_constant,
        )
    except (
        FileNotFoundError,
        IsADirectoryError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as error:
        prediction = {"invalid_solution": str(error)}
    result = score(ground_truth, prediction)
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.reward_txt.write_text(
        f"{result['reward']}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
