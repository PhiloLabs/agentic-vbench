#!/usr/bin/env python3

"""Grade OpenTTGames full-match rally event-chain reconstruction."""

from __future__ import annotations

import argparse
import json

import os

import stat
from pathlib import Path
from typing import Any


RALLY_START_TOLERANCE_S = 1.0
STROKE_TOLERANCE_S = 0.35
ENDING_TOLERANCE_S = 1.0

STROKE_FIELDS = (
    "player",
    "hand",
    "stroke",
)


MAX_SOLUTION_BYTES = 8 * 1024 * 1024


def load_solution_safely(path: Path) -> Any:
    """Load an agent submission without following special filesystem objects."""
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    fd = os.open(path, flags)

    try:
        info = os.fstat(fd)

        if not stat.S_ISREG(info.st_mode):
            raise ValueError("solution.json is not a regular file")

        if info.st_size > MAX_SOLUTION_BYTES:
            raise ValueError(
                f"solution.json exceeds {MAX_SOLUTION_BYTES} bytes"
            )

        # Read only from the descriptor validated by fstat().
        with os.fdopen(fd, "rb") as f:
            fd = -1
            payload = f.read(MAX_SOLUTION_BYTES + 1)

        if len(payload) > MAX_SOLUTION_BYTES:
            raise ValueError(
                f"solution.json exceeds {MAX_SOLUTION_BYTES} bytes"
            )

        return json.loads(payload)

    finally:
        if fd >= 0:
            os.close(fd)


def numeric(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def f1_from_hits(hits: int, predicted: int, reference: int) -> float:
    precision = hits / predicted if predicted else 0.0
    recall = hits / reference if reference else 0.0

    return (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )


def get_reference_rallies(reference: Any) -> list[dict[str, Any]]:
    if not isinstance(reference, dict):
        return []

    rallies = reference.get("rallies", [])

    return rallies if isinstance(rallies, list) else []


def get_prediction_rallies(solution: Any) -> list[Any]:
    if not isinstance(solution, dict):
        return []

    rallies = solution.get("rallies", [])

    return rallies if isinstance(rallies, list) else []


def match_rallies(
    predictions: list[Any],
    references: list[dict[str, Any]],
) -> list[tuple[int, int, float]]:
    """Greedily match rallies by serve timestamp."""

    candidates = []

    for pred_index, prediction in enumerate(predictions):
        if not isinstance(prediction, dict):
            continue

        pred_start = numeric(prediction.get("serve_time_sec"))

        if pred_start is None:
            continue

        for ref_index, reference in enumerate(references):
            ref_start = numeric(reference.get("serve_time_sec"))

            if ref_start is None:
                continue

            delta = abs(pred_start - ref_start)

            if delta <= RALLY_START_TOLERANCE_S:
                candidates.append((delta, pred_index, ref_index))

    used_predictions = set()
    used_references = set()
    matches = []

    for delta, pred_index, ref_index in sorted(candidates):
        if pred_index in used_predictions:
            continue

        if ref_index in used_references:
            continue

        used_predictions.add(pred_index)
        used_references.add(ref_index)

        matches.append((pred_index, ref_index, delta))

    return matches


def match_strokes(
    predicted: list[Any],
    reference: list[dict[str, Any]],
) -> list[tuple[int, int, float]]:
    """
    Maximum-cardinality order-preserving timestamp matching.

    Among matchings with the same number of matched strokes, prefer the one
    with the smaller total timestamp error.
    """

    pred_times = [
        numeric(item.get("time_sec")) if isinstance(item, dict) else None
        for item in predicted
    ]

    ref_times = [
        numeric(item.get("time_sec")) if isinstance(item, dict) else None
        for item in reference
    ]

    n = len(predicted)
    m = len(reference)

    # dp[i][j] = (matched_count, total_error, matches)
    dp = [
        [(0, 0.0, []) for _ in range(m + 1)]
        for _ in range(n + 1)
    ]

    def better(a, b):
        if a[0] != b[0]:
            return a if a[0] > b[0] else b

        return a if a[1] <= b[1] else b

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            best = better(
                dp[i - 1][j],
                dp[i][j - 1],
            )

            pred_time = pred_times[i - 1]
            ref_time = ref_times[j - 1]

            if pred_time is not None and ref_time is not None:
                delta = abs(pred_time - ref_time)

                if delta <= STROKE_TOLERANCE_S:
                    prev_count, prev_error, prev_matches = dp[i - 1][j - 1]

                    matched = (
                        prev_count + 1,
                        prev_error + delta,
                        prev_matches + [
                            (i - 1, j - 1, delta)
                        ],
                    )

                    best = better(best, matched)

            dp[i][j] = best

    return dp[n][m][2]


def score(
    solution: Any,
    reference_data: Any,
) -> dict[str, Any]:
    predictions = get_prediction_rallies(solution)
    references = get_reference_rallies(reference_data)

    rally_matches = match_rallies(predictions, references)

    rally_f1 = f1_from_hits(
        len(rally_matches),
        len(predictions),
        len(references),
    )

    total_predicted_strokes = 0

    total_reference_strokes = sum(
        len(rally.get("strokes", []))
        for rally in references
        if isinstance(rally.get("strokes", []), list)
    )

    matched_stroke_hits = 0

    semantic_hits = {
        field: 0
        for field in STROKE_FIELDS
    }

    semantic_joint_hits = 0
    ending_label_hits = 0
    ending_time_hits = 0
    ending_joint_hits = 0

    matched_details = []

    for pred_index, ref_index, start_delta in rally_matches:
        prediction = predictions[pred_index]
        reference = references[ref_index]

        pred_strokes = prediction.get("strokes", [])
        ref_strokes = reference.get("strokes", [])

        if not isinstance(pred_strokes, list):
            pred_strokes = []

        if not isinstance(ref_strokes, list):
            ref_strokes = []

        total_predicted_strokes += len(pred_strokes)

        stroke_matches = match_strokes(
            pred_strokes,
            ref_strokes,
        )

        matched_stroke_hits += len(stroke_matches)

        for pred_stroke_index, ref_stroke_index, _ in stroke_matches:
            pred_stroke = pred_strokes[pred_stroke_index]
            ref_stroke = ref_strokes[ref_stroke_index]

            if not isinstance(pred_stroke, dict):
                continue

            if not isinstance(ref_stroke, dict):
                continue

            for field in STROKE_FIELDS:
                if pred_stroke.get(field) == ref_stroke.get(field):
                    semantic_hits[field] += 1

            semantic_joint_ok = all(
                pred_stroke.get(field) == ref_stroke.get(field)
                for field in STROKE_FIELDS
            )
            semantic_joint_hits += int(semantic_joint_ok)

        ending_label_ok = (
            prediction.get("ending") == reference.get("ending")
        )

        pred_ending_time = numeric(
            prediction.get("ending_time_sec")
        )

        ref_ending_time = numeric(
            reference.get("ending_time_sec")
        )

        ending_time_ok = (
            pred_ending_time is not None
            and ref_ending_time is not None
            and abs(pred_ending_time - ref_ending_time)
            <= ENDING_TOLERANCE_S
        )

        ending_joint_ok = ending_label_ok and ending_time_ok

        ending_label_hits += int(ending_label_ok)
        ending_time_hits += int(ending_time_ok)
        ending_joint_hits += int(ending_joint_ok)

        matched_details.append(
            {
                "prediction_index": pred_index,
                "reference_rally_id": reference.get("rally_id"),
                "reference_start_s": reference.get("serve_time_sec"),
                "start_delta_s": round(start_delta, 3),
                "predicted_strokes": len(pred_strokes),
                "reference_strokes": len(ref_strokes),
                "matched_strokes": len(stroke_matches),
                "ending_label_ok": ending_label_ok,
                "ending_time_ok": ending_time_ok,
                "ending_joint_ok": ending_joint_ok,
            }
        )

    # Predictions in unmatched rallies still count against stroke precision.
    matched_prediction_indices = {
        pred_index
        for pred_index, _, _ in rally_matches
    }

    for pred_index, prediction in enumerate(predictions):
        if pred_index in matched_prediction_indices:
            continue

        if not isinstance(prediction, dict):
            continue

        strokes = prediction.get("strokes", [])

        if isinstance(strokes, list):
            total_predicted_strokes += len(strokes)

    stroke_timing_f1 = f1_from_hits(
        matched_stroke_hits,
        total_predicted_strokes,
        total_reference_strokes,
    )

    semantic_scores = {}

    for field in STROKE_FIELDS:
        semantic_scores[field] = f1_from_hits(
            semantic_hits[field],
            total_predicted_strokes,
            total_reference_strokes,
        )

    stroke_semantic_score = f1_from_hits(
        semantic_joint_hits,
        total_predicted_strokes,
        total_reference_strokes,
    )

    matched_rally_count = len(rally_matches)

    ending_label_accuracy = (
        ending_label_hits / matched_rally_count
        if matched_rally_count
        else 0.0
    )

    ending_time_accuracy = (
        ending_time_hits / matched_rally_count
        if matched_rally_count
        else 0.0
    )

    ending_score = (
        ending_joint_hits / matched_rally_count
        if matched_rally_count
        else 0.0
    )

    reward = (
        rally_f1
        * ending_score
        * stroke_timing_f1
        * stroke_semantic_score
    )

    return {
        "reward": round(reward, 6),

        "predicted_rallies": len(predictions),
        "reference_rallies": len(references),
        "matched_rallies": matched_rally_count,

        "rally_discovery": {
            "f1": round(rally_f1, 6),
        },

        "stroke_timing": {
            "matched": matched_stroke_hits,
            "predicted": total_predicted_strokes,
            "reference": total_reference_strokes,
            "f1": round(stroke_timing_f1, 6),
        },

        "stroke_semantics": {
            field: round(score_value, 6)
            for field, score_value in semantic_scores.items()
        },

        "stroke_semantic_joint": round(
            stroke_semantic_score,
            6,
        ),

        "rally_endings": {
            "label_accuracy": round(
                ending_label_accuracy,
                6,
            ),
            "timing_accuracy": round(
                ending_time_accuracy,
                6,
            ),
            "joint_accuracy": round(
                ending_score,
                6,
            ),
        },

        "matched_details": matched_details,
    }


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--solution",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--reference",
        type=Path,
        required=True,
    )

    # Kept for local regression tests.
    parser.add_argument(
        "--output",
        type=Path,
        required=False,
    )

    # Harbor verifier outputs.
    parser.add_argument(
        "--reward-json",
        type=Path,
        required=False,
    )

    parser.add_argument(
        "--reward-txt",
        type=Path,
        required=False,
    )

    parser.add_argument(
        "--details-json",
        type=Path,
        required=False,
    )

    args = parser.parse_args()

    try:
        solution = load_solution_safely(args.solution)

        reason = "ok"

    except (
        FileNotFoundError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        ValueError,
        OSError,
    ) as exc:
        solution = {}
        reason = f"unreadable solution.json: {exc}"

    with args.reference.open() as f:
        reference = json.load(f)

    result = score(
        solution,
        reference,
    )

    result["reason"] = reason

    text = json.dumps(
        result,
        indent=2,
    )

    # Used by the local regression suite.
    if args.output:
        args.output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        args.output.write_text(
            text + "\n"
        )

    # Used by Harbor. Reward values must be numeric.
    if args.reward_json:
        args.reward_json.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        args.reward_json.write_text(
            json.dumps(
                {"reward": result["reward"]},
                indent=2,
            ) + "\n"
        )

    # Keep full diagnostics separately.
    if args.details_json:
        args.details_json.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        args.details_json.write_text(
            text + "\n"
        )

    if args.reward_txt:
        args.reward_txt.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        args.reward_txt.write_text(
            f"{result['reward']}\n"
        )

    print(text)


if __name__ == "__main__":
    main()
