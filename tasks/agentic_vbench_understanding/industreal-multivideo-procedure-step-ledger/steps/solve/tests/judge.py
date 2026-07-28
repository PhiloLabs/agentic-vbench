#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

TOLERANCE_S = 2.0
VIDEOS = set("ABCDEFG")
GROUND_TRUTH = json.loads(
    Path(__file__).with_name("ground_truth.json").read_text()
)["checkpoints"]


def _checkpoint_match(
    pred: dict,
    truth: dict,
    *,
    require_changes: bool,
    require_state: bool,
) -> bool:
    return (
        pred["video"] == truth["video"]
        and abs(pred["time_s"] - truth["time_s"]) <= TOLERANCE_S
        and (not require_changes or pred["changes"] == truth["changes"])
        and (
            not require_state
            or pred["state_after"] == truth["state_after"]
        )
    )


def _sort_key(checkpoint: dict) -> tuple:
    return (
        checkpoint["video"],
        checkpoint["time_s"],
        tuple(checkpoint["changes"]),
        tuple(checkpoint["state_after"]),
    )


def _maximum_matches(
    truth: list[dict],
    pred: list[dict],
    *,
    require_changes: bool,
    require_state: bool,
) -> int:
    truth = sorted(truth, key=_sort_key)
    pred = sorted(pred, key=_sort_key)
    previous = [0] * (len(pred) + 1)
    for truth_checkpoint in truth:
        current = [0]
        for j, pred_checkpoint in enumerate(pred, start=1):
            best = max(previous[j], current[j - 1])
            if _checkpoint_match(
                pred_checkpoint,
                truth_checkpoint,
                require_changes=require_changes,
                require_state=require_state,
            ):
                best = max(best, previous[j - 1] + 1)
            current.append(best)
        previous = current
    return previous[-1]


def _parse_predictions(solution: Path) -> tuple[list[dict], int, str]:
    try:
        raw = json.loads(solution.read_text())
        checkpoints = raw.get("checkpoints")
        if not isinstance(checkpoints, list):
            raise ValueError("checkpoints is not a list")
    except Exception as exc:
        return [], 0, f"unreadable solution.json: {exc}"

    parsed = []
    for checkpoint in checkpoints:
        if not isinstance(checkpoint, dict):
            continue
        video = checkpoint.get("video")
        time_s = checkpoint.get("time_s")
        changes = checkpoint.get("changes")
        state_after = checkpoint.get("state_after")
        if not isinstance(video, str) or video.upper() not in VIDEOS:
            continue
        if isinstance(time_s, bool) or not isinstance(time_s, (int, float)):
            continue
        if not math.isfinite(float(time_s)) or float(time_s) < 0:
            continue
        if not isinstance(changes, list) or not changes or len(set(changes)) != len(changes):
            continue
        if any(
            isinstance(step_id, bool)
            or not isinstance(step_id, int)
            or not 0 <= step_id <= 32
            for step_id in changes
        ):
            continue
        if not isinstance(state_after, list) or len(state_after) != 11:
            continue
        if any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or value not in {-1, 0, 1}
            for value in state_after
        ):
            continue
        parsed.append({
            "video": video.upper(),
            "time_s": float(time_s),
            "changes": sorted(changes),
            "state_after": state_after,
        })
    malformed = len(checkpoints) - len(parsed)
    reason = "ok" if malformed == 0 else f"ignored {malformed} malformed checkpoint(s)"
    return parsed, len(checkpoints), reason


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--reward-json", required=True, type=Path)
    parser.add_argument("--reward-txt", required=True, type=Path)
    parser.add_argument("--details-json", required=True, type=Path)
    args = parser.parse_args()

    predictions, n_predicted, reason = _parse_predictions(args.solution)
    true_positives = _maximum_matches(
        GROUND_TRUTH,
        predictions,
        require_changes=True,
        require_state=True,
    )
    changes_only = _maximum_matches(
        GROUND_TRUTH,
        predictions,
        require_changes=True,
        require_state=False,
    )
    time_only = _maximum_matches(
        GROUND_TRUTH,
        predictions,
        require_changes=False,
        require_state=False,
    )
    n_truth = len(GROUND_TRUTH)
    precision = true_positives / n_predicted if n_predicted else 0.0
    recall = true_positives / n_truth
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    details = {
        "reason": reason,
        "n_ground_truth": n_truth,
        "n_predicted": n_predicted,
        "true_positives": true_positives,
        "video_time_only_matches": time_only,
        "video_time_changes_matches": changes_only,
        "match_requires": "video, time, changes, and full state_after",
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "timestamp_tolerance_s": TOLERANCE_S,
    }
    reward = round(f1, 6)
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.details_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps({"reward": reward}, indent=2) + "\n")
    args.reward_txt.write_text(f"{reward}\n")
    args.details_json.write_text(json.dumps(details, indent=2) + "\n")


if __name__ == "__main__":
    main()
