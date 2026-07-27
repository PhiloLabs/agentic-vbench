#!/usr/bin/env python3
import argparse
import json
import math
import os
import stat
from pathlib import Path

TOLERANCE_S = 4.0
MAX_PREDICTED_TURNS = 1000
MAX_SOLUTION_BYTES = 2_000_000


def load_ground_truth():
    return json.loads(Path(__file__).with_name("gt.json").read_text())["turns"]


def load_prediction(path, valid_speaker_ids):
    descriptor = os.open(
        path,
        os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
    )
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("solution must be a regular file")
        if metadata.st_size > MAX_SOLUTION_BYTES:
            raise ValueError(
                f"solution exceeds {MAX_SOLUTION_BYTES} bytes"
            )
        with os.fdopen(descriptor, encoding="utf-8") as solution:
            descriptor = -1
            document = json.load(solution)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if not isinstance(document, dict) or "turns" not in document:
        raise ValueError("solution must be an object containing turns")
    turns = document["turns"]
    if not isinstance(turns, list):
        raise ValueError("turns must be a list")
    if len(turns) > MAX_PREDICTED_TURNS:
        raise ValueError(
            f"turns exceeds the maximum of {MAX_PREDICTED_TURNS}"
        )

    validated = []
    previous_start = -1.0
    for position, turn in enumerate(turns, start=1):
        if not isinstance(turn, dict):
            raise ValueError(f"turn {position} must be an object")
        required = {"turn_index", "speaker_id", "start_time_s", "end_time_s"}
        if not required.issubset(turn):
            raise ValueError(f"turn {position} is missing required fields")
        if turn["turn_index"] != position:
            raise ValueError("turn_index must be consecutive and one-based")
        if turn["speaker_id"] not in valid_speaker_ids:
            raise ValueError(f"turn {position} has an invalid speaker_id")
        start = turn["start_time_s"]
        end = turn["end_time_s"]
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not isinstance(start, (int, float))
            or not isinstance(end, (int, float))
            or not math.isfinite(start)
            or not math.isfinite(end)
            or start < 0
            or end <= start
        ):
            raise ValueError(f"turn {position} has invalid timestamps")
        if start < previous_start:
            raise ValueError("turns must be chronological")
        previous_start = float(start)
        validated.append(
            {
                "turn_index": position,
                "speaker_id": turn["speaker_id"],
                "start_time_s": float(start),
                "end_time_s": float(end),
            }
        )
    return validated


def matches(prediction, ground_truth):
    return (
        prediction["speaker_id"] == ground_truth["speaker_id"]
        and abs(prediction["start_time_s"] - ground_truth["start_time_s"])
        <= TOLERANCE_S
        and abs(prediction["end_time_s"] - ground_truth["end_time_s"])
        <= TOLERANCE_S
    )


def monotonic_true_positives(predictions, ground_truth):
    columns = len(ground_truth) + 1
    previous = [0] * columns
    for prediction in predictions:
        current = [0]
        for gt_index in range(1, columns):
            best = max(
                previous[gt_index],
                current[gt_index - 1],
            )
            if matches(prediction, ground_truth[gt_index - 1]):
                best = max(
                    best,
                    previous[gt_index - 1] + 1,
                )
            current.append(best)
        previous = current
    return previous[-1]


def score(predictions, ground_truth):
    true_positives = monotonic_true_positives(predictions, ground_truth)
    precision = true_positives / len(predictions) if predictions else 0.0
    recall = true_positives / len(ground_truth) if ground_truth else 0.0
    reward = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return reward, {
        "ground_truth_turns": len(ground_truth),
        "predicted_turns": len(predictions),
        "true_positives": true_positives,
        "false_positives": len(predictions) - true_positives,
        "false_negatives": len(ground_truth) - true_positives,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(reward, 6),
        "boundary_tolerance_s": TOLERANCE_S,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--reward-json", required=True, type=Path)
    parser.add_argument("--reward-txt", required=True, type=Path)
    args = parser.parse_args()

    reason = "ok"
    ground_truth = load_ground_truth()
    valid_speaker_ids = {turn["speaker_id"] for turn in ground_truth}
    try:
        predictions = load_prediction(args.solution, valid_speaker_ids)
    except Exception as error:
        predictions = []
        reason = f"invalid solution: {error}"

    reward, details = score(predictions, ground_truth)
    details["reason"] = reason
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(
        json.dumps({"reward": round(reward, 6), "details": details}, indent=2)
        + "\n"
    )
    args.reward_txt.write_text(f"{round(reward, 6)}\n")


if __name__ == "__main__":
    main()
