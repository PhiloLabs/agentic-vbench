#!/usr/bin/env python3
"""Deterministically grade the complete balance-beam routine timeline."""

import argparse
import json
import re
from pathlib import Path

START_TOLERANCE_S = 0.25
END_TOLERANCE_S = 0.25
DISMOUNT_TAKEOFF_TOLERANCE_S = 0.25
SCORE_TIME_TOLERANCE_S = 1.00
DIAGNOSTIC_MATCH_WINDOW_S = 20.0
REQUIRED_FIELDS = {
    "start_time",
    "end_time",
    "dismount_takeoff_time",
    "school",
    "gymnast_name",
    "beam_score",
    "score_time",
}
SCHOOLS = {"Stanford", "Arizona State", "Oregon State", "Arizona"}
SCORE_RE = re.compile(r"^(?:[0-9]\.\d{3}|10\.000)$")
TIMESTAMP_RE = re.compile(
    r"^(?P<hours>\d{2}):(?P<minutes>\d{2}):"
    r"(?P<seconds>\d{2})\.(?P<milliseconds>\d{3})$"
)


def parse_timestamp(value):
    if not isinstance(value, str):
        return None
    match = TIMESTAMP_RE.fullmatch(value)
    if match is None:
        return None
    hours = int(match.group("hours"))
    minutes = int(match.group("minutes"))
    seconds = int(match.group("seconds"))
    milliseconds = int(match.group("milliseconds"))
    if minutes >= 60 or seconds >= 60:
        return None
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def validate_record(record):
    if not isinstance(record, dict) or set(record) != REQUIRED_FIELDS:
        return False
    start = parse_timestamp(record["start_time"])
    end = parse_timestamp(record["end_time"])
    dismount_takeoff = parse_timestamp(record["dismount_takeoff_time"])
    score_time = parse_timestamp(record["score_time"])
    return (
        start is not None
        and end is not None
        and dismount_takeoff is not None
        and start < dismount_takeoff < end
        and end > start
        and score_time is not None
        and score_time > end
        and record["school"] in SCHOOLS
        and isinstance(record["gymnast_name"], str)
        and record["gymnast_name"]
        and record["gymnast_name"] == record["gymnast_name"].strip()
        and isinstance(record["beam_score"], str)
        and SCORE_RE.fullmatch(record["beam_score"]) is not None
    )


def prediction_set_error(records):
    for index, record in enumerate(records):
        if not validate_record(record):
            return f"schema-invalid record at index {index}"

    starts = [parse_timestamp(record["start_time"]) for record in records]
    if any(current <= previous for previous, current in zip(starts, starts[1:])):
        return "beam_routines must be strictly chronological by start_time"
    return None


def load_ground_truth(path):
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or set(data) != {"beam_routines"}:
        raise ValueError("ground truth must contain only beam_routines")
    records = data["beam_routines"]
    if not isinstance(records, list) or not records:
        raise ValueError("ground truth beam_routines must be a non-empty list")
    error = prediction_set_error(records)
    if error is not None:
        raise ValueError(f"invalid ground truth: {error}")
    return records


def load_predictions(path):
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or set(data) != {"beam_routines"}:
            raise ValueError("top level must contain only beam_routines")
        records = data["beam_routines"]
        if not isinstance(records, list):
            raise ValueError("beam_routines is not a list")
        return records, prediction_set_error(records) or "ok"
    except Exception as exc:  # noqa: BLE001
        return [], f"unreadable or malformed solution: {exc}"


def full_record_match(predicted, expected):
    predicted_start = parse_timestamp(predicted["start_time"])
    expected_start = parse_timestamp(expected["start_time"])
    predicted_end = parse_timestamp(predicted["end_time"])
    expected_end = parse_timestamp(expected["end_time"])
    predicted_dismount_takeoff = parse_timestamp(
        predicted["dismount_takeoff_time"]
    )
    expected_dismount_takeoff = parse_timestamp(
        expected["dismount_takeoff_time"]
    )
    predicted_score_time = parse_timestamp(predicted["score_time"])
    expected_score_time = parse_timestamp(expected["score_time"])
    return (
        abs(predicted_start - expected_start) <= START_TOLERANCE_S
        and abs(predicted_end - expected_end) <= END_TOLERANCE_S
        and abs(predicted_dismount_takeoff - expected_dismount_takeoff)
        <= DISMOUNT_TAKEOFF_TOLERANCE_S
        and abs(predicted_score_time - expected_score_time)
        <= SCORE_TIME_TOLERANCE_S
        and predicted["school"] == expected["school"]
        and predicted["gymnast_name"] == expected["gymnast_name"]
        and predicted["beam_score"] == expected["beam_score"]
    )


def count_true_positives(predictions, ground_truth):
    used = [False] * len(ground_truth)
    true_positives = 0
    for predicted in predictions:
        for index, expected in enumerate(ground_truth):
            if not used[index] and full_record_match(predicted, expected):
                used[index] = True
                true_positives += 1
                break
    return true_positives


def empty_diagnostics():
    return {
        "broadly_matched_records": 0,
        "start_within_tolerance": 0,
        "end_within_tolerance": 0,
        "dismount_takeoff_within_tolerance": 0,
        "score_time_within_tolerance": 0,
        "school_exact": 0,
        "gymnast_name_exact": 0,
        "beam_score_exact": 0,
    }


def diagnostic_counts(predictions, ground_truth):
    available = set(range(len(ground_truth)))
    counts = empty_diagnostics()
    for predicted in predictions:
        predicted_start = parse_timestamp(predicted["start_time"])
        candidates = sorted(
            available,
            key=lambda index: abs(
                predicted_start - parse_timestamp(ground_truth[index]["start_time"])
            ),
        )
        if not candidates:
            continue
        index = candidates[0]
        expected = ground_truth[index]
        start_delta = abs(
            predicted_start - parse_timestamp(expected["start_time"])
        )
        if start_delta > DIAGNOSTIC_MATCH_WINDOW_S:
            continue
        available.remove(index)
        counts["broadly_matched_records"] += 1
        counts["start_within_tolerance"] += start_delta <= START_TOLERANCE_S
        counts["end_within_tolerance"] += abs(
            parse_timestamp(predicted["end_time"])
            - parse_timestamp(expected["end_time"])
        ) <= END_TOLERANCE_S
        counts["dismount_takeoff_within_tolerance"] += abs(
            parse_timestamp(predicted["dismount_takeoff_time"])
            - parse_timestamp(expected["dismount_takeoff_time"])
        ) <= DISMOUNT_TAKEOFF_TOLERANCE_S
        counts["score_time_within_tolerance"] += abs(
            parse_timestamp(predicted["score_time"])
            - parse_timestamp(expected["score_time"])
        ) <= SCORE_TIME_TOLERANCE_S
        counts["school_exact"] += predicted["school"] == expected["school"]
        counts["gymnast_name_exact"] += (
            predicted["gymnast_name"] == expected["gymnast_name"]
        )
        counts["beam_score_exact"] += (
            predicted["beam_score"] == expected["beam_score"]
        )
    return counts


def grade(predictions, ground_truth, reason="ok"):
    validation_reason = reason
    if validation_reason == "ok":
        validation_reason = prediction_set_error(predictions) or "ok"

    predicted_count = len(predictions)
    expected_count = len(ground_truth)
    invalid_count = sum(not validate_record(record) for record in predictions)

    if validation_reason != "ok":
        true_positives = 0
        precision = 0.0
        recall = 0.0
        f1 = 0.0
        diagnostics = empty_diagnostics()
    else:
        true_positives = count_true_positives(predictions, ground_truth)
        precision = true_positives / predicted_count if predicted_count else 0.0
        recall = true_positives / expected_count if expected_count else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        diagnostics = diagnostic_counts(predictions, ground_truth)

    details = {
        "reason": validation_reason,
        "n_ground_truth": expected_count,
        "n_predicted": predicted_count,
        "n_invalid_records": invalid_count,
        "true_positives_complete_record": true_positives,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "start_tolerance_s": START_TOLERANCE_S,
        "end_tolerance_s": END_TOLERANCE_S,
        "dismount_takeoff_tolerance_s": DISMOUNT_TAKEOFF_TOLERANCE_S,
        "score_time_tolerance_s": SCORE_TIME_TOLERANCE_S,
        "diagnostics": diagnostics,
    }
    return round(f1, 6), details


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--reward-json", required=True, type=Path)
    parser.add_argument("--reward-txt", required=True, type=Path)
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=Path(__file__).with_name("ground_truth.json"),
    )
    args = parser.parse_args()

    ground_truth = load_ground_truth(args.ground_truth)
    predictions, reason = load_predictions(args.solution)
    reward, details = grade(predictions, ground_truth, reason)

    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_txt.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(
        json.dumps({"reward": reward, "details": details}, indent=2) + "\n"
    )
    args.reward_txt.write_text(f"{reward}\n")


if __name__ == "__main__":
    main()
