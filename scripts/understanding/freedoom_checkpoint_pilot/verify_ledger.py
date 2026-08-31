#!/usr/bin/env python3
"""Deterministic scorer for the Freedoom state-transition ledger pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


STATE_KEYS = {
    "active_weapon",
    "held_keys",
    "active_switches",
    "current_checkpoint",
}
TOP_LEVEL_KEYS = {"episodes"}
EPISODE_KEYS = {"episode_id", "events"}
EVENT_KEYS = {"timestamp_ms", "event_type", "entity_id", "state"}
MAX_DOCUMENT_EPISODES = 100
MAX_EVENTS_PER_EPISODE = 1000
MAX_SOLUTION_BYTES = 1_000_000


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _episode_map(document: Any) -> dict[str, list[Any]]:
    if not isinstance(document, dict) or set(document) != TOP_LEVEL_KEYS:
        raise ValueError("top level must contain exactly `episodes`")
    if not isinstance(document["episodes"], list):
        raise ValueError("top-level `episodes` must be a list")
    if len(document["episodes"]) > MAX_DOCUMENT_EPISODES:
        raise ValueError("too many episodes")

    result: dict[str, list[Any]] = {}
    for episode in document["episodes"]:
        if not isinstance(episode, dict) or set(episode) != EPISODE_KEYS:
            raise ValueError(
                "each episode must contain exactly `episode_id` and `events`"
            )
        episode_id = episode.get("episode_id")
        events = episode.get("events")
        if not isinstance(episode_id, str) or not episode_id:
            raise ValueError("each episode needs a non-empty string `episode_id`")
        if episode_id in result:
            raise ValueError(f"duplicate episode_id: {episode_id}")
        if not isinstance(events, list):
            raise ValueError(f"`events` must be a list for {episode_id}")
        if len(events) > MAX_EVENTS_PER_EPISODE:
            raise ValueError(f"too many events for {episode_id}")
        previous_timestamp = -1
        for event in events:
            if not isinstance(event, dict) or set(event) != EVENT_KEYS:
                raise ValueError(f"invalid event schema for {episode_id}")
            timestamp = event["timestamp_ms"]
            if (
                isinstance(timestamp, bool)
                or not isinstance(timestamp, int)
                or timestamp < 0
                or timestamp < previous_timestamp
            ):
                raise ValueError(
                    f"timestamps must be non-negative and non-decreasing "
                    f"for {episode_id}"
                )
            if (
                not isinstance(event["event_type"], str)
                or not event["event_type"]
                or not isinstance(event["entity_id"], str)
                or not event["entity_id"]
                or _normalized_state(event["state"]) is None
            ):
                raise ValueError(f"invalid event values for {episode_id}")
            previous_timestamp = timestamp
        result[episode_id] = events
    return result


def _normalized_state(value: Any) -> tuple[Any, ...] | None:
    if not isinstance(value, dict) or set(value) != STATE_KEYS:
        return None
    active_weapon = value["active_weapon"]
    held_keys = value["held_keys"]
    active_switches = value["active_switches"]
    checkpoint = value["current_checkpoint"]
    if not isinstance(active_weapon, str):
        return None
    if not isinstance(held_keys, list) or not all(isinstance(v, str) for v in held_keys):
        return None
    if len(set(held_keys)) != len(held_keys):
        return None
    if not isinstance(active_switches, list) or not all(
        isinstance(v, str) for v in active_switches
    ):
        return None
    if len(set(active_switches)) != len(active_switches):
        return None
    if checkpoint is not None and not isinstance(checkpoint, str):
        return None
    return (
        active_weapon,
        tuple(sorted(held_keys)),
        tuple(sorted(active_switches)),
        checkpoint,
    )


def _event_matches(ground_truth: Any, prediction: Any, tolerance_ms: int) -> bool:
    if not isinstance(ground_truth, dict) or not isinstance(prediction, dict):
        return False
    gt_timestamp = ground_truth.get("timestamp_ms")
    pred_timestamp = prediction.get("timestamp_ms")
    if isinstance(gt_timestamp, bool) or isinstance(pred_timestamp, bool):
        return False
    if not isinstance(gt_timestamp, int) or not isinstance(pred_timestamp, int):
        return False
    return (
        ground_truth.get("event_type") == prediction.get("event_type")
        and ground_truth.get("entity_id") == prediction.get("entity_id")
        and abs(gt_timestamp - pred_timestamp) <= tolerance_ms
        and _normalized_state(ground_truth.get("state"))
        == _normalized_state(prediction.get("state"))
        and _normalized_state(ground_truth.get("state")) is not None
    )


def _ordered_matches(
    ground_truth: list[Any], prediction: list[Any], tolerance_ms: int
) -> int:
    previous = [0] * (len(prediction) + 1)
    for gt_event in ground_truth:
        current = [0]
        for index, pred_event in enumerate(prediction, start=1):
            if _event_matches(gt_event, pred_event, tolerance_ms):
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[-1]))
        previous = current
    return previous[-1]


def score_documents(
    ground_truth: Any, prediction: Any, tolerance_ms: int = 750
) -> dict[str, Any]:
    if tolerance_ms < 0:
        raise ValueError("timestamp tolerance must be non-negative")
    gt_episodes = _episode_map(ground_truth)
    if any(not events for events in gt_episodes.values()):
        raise ValueError("ground-truth episodes must not be empty")
    parse_error = None
    try:
        pred_episodes = _episode_map(prediction)
    except ValueError as exc:
        pred_episodes = {}
        parse_error = str(exc)

    unknown_episode_ids = sorted(set(pred_episodes) - set(gt_episodes))
    if unknown_episode_ids:
        pred_episodes = {}
        parse_error = "unknown episode_id: " + ", ".join(unknown_episode_ids)

    episode_ids = sorted(gt_episodes)
    episode_scores: dict[str, Any] = {}
    rewards: list[float] = []
    for episode_id in episode_ids:
        gt_events = gt_episodes.get(episode_id, [])
        pred_events = pred_episodes.get(episode_id, [])
        matches = _ordered_matches(gt_events, pred_events, tolerance_ms)
        denominator = len(gt_events) + len(pred_events)
        if parse_error is not None:
            f1 = 0.0
        else:
            f1 = (2.0 * matches / denominator) if denominator else 1.0
        rewards.append(f1)
        episode_scores[episode_id] = {
            "ground_truth_events": len(gt_events),
            "predicted_events": len(pred_events),
            "ordered_exact_matches": matches,
            "event_f1": round(f1, 6),
        }

    reward = sum(rewards) / len(rewards) if rewards else 0.0
    return {
        "reward": round(reward, 6),
        "details": {
            "parse_error": parse_error,
            "timestamp_tolerance_ms": tolerance_ms,
            "episode_macro_event_f1": round(reward, 6),
            "episodes": episode_scores,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", required=True, type=Path)
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--reward-json", required=True, type=Path)
    parser.add_argument("--reward-txt", type=Path)
    parser.add_argument("--timestamp-tolerance-ms", type=int, default=750)
    args = parser.parse_args()

    ground_truth = json.loads(args.ground_truth.read_text(encoding="utf-8"))
    try:
        if args.solution.stat().st_size > MAX_SOLUTION_BYTES:
            raise ValueError(
                f"solution exceeds {MAX_SOLUTION_BYTES} byte limit"
            )
        prediction = json.loads(
            args.solution.read_text(encoding="utf-8"),
            parse_constant=_reject_json_constant,
        )
    except (
        FileNotFoundError,
        IsADirectoryError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
    ) as exc:
        prediction = {"invalid_solution": str(exc)}
    result = score_documents(
        ground_truth, prediction, tolerance_ms=args.timestamp_tolerance_ms
    )

    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if args.reward_txt:
        args.reward_txt.parent.mkdir(parents=True, exist_ok=True)
        args.reward_txt.write_text(f"{result['reward']}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
