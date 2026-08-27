#!/usr/bin/env python3
"""Grade a tennis rally-stroke ledger. Pure Python stdlib, deterministic.

The agent must list every rally stroke in an 82.6-minute broadcast of a tennis match as
(player, stroke, start_frame). A predicted stroke is a true positive only when it fully
reconstructs the stroke: the right player, the right stroke class, and a start frame
within TOLERANCE_FRAMES of the annotated one, under an order-preserving one-to-one
alignment. reward = F1, so misses and false positives both cost. The two extra
`*_matches` counters are diagnostics only and never touch reward.
"""
import argparse
import json
import os
import stat
from pathlib import Path

# 8 frames = 0.32 s at the video's 25 Hz. A stroke's start_frame is the take-back,
# roughly 10 frames before racquet-ball contact; measured across the annotation, the
# take-back is placed with a spread of about +/-7 frames (interval between successive
# strokes in a rally: median 31, sd 6.6), so this tolerance sits just above one
# standard deviation of the annotator's own consistency.
#
# The tightest gap between any two consecutive strokes in the match is 17 frames, so a
# prediction cannot drift onto its neighbour; and the closest two strokes of the SAME
# class start 47 frames apart, so the one-to-one alignment stays well defined with a
# wide margin. build_ground_truth.py asserts both against this constant.
TOLERANCE_FRAMES = 8
MAX_PREDICTED_STROKES = 2000
MAX_SOLUTION_BYTES = 2_000_000
VIDEO_FRAMES = 123875


def _load(name):
    return json.loads(Path(__file__).with_name(name).read_text())


def load_ground_truth():
    return _load("gt.json")["strokes"]


def load_vocabulary(ground_truth):
    """The closed label space is exactly the players and stroke classes the answer key
    uses, so deriving it here leaves one vocabulary.json in the repo — the agent-facing
    copy baked into the image — and makes judge/agent drift impossible by construction."""
    players = {stroke["player"] for stroke in ground_truth}
    strokes = {stroke["stroke"] for stroke in ground_truth}
    return players, strokes


def load_prediction(path, valid_players, valid_strokes):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("solution must be a regular file")
        if metadata.st_size > MAX_SOLUTION_BYTES:
            raise ValueError(f"solution exceeds {MAX_SOLUTION_BYTES} bytes")
        with os.fdopen(descriptor, encoding="utf-8") as solution:
            descriptor = -1
            document = json.load(solution)
    finally:
        if descriptor >= 0:
            os.close(descriptor)

    if not isinstance(document, dict) or "strokes" not in document:
        raise ValueError("solution must be an object containing strokes")
    strokes = document["strokes"]
    if not isinstance(strokes, list):
        raise ValueError("strokes must be a list")
    if len(strokes) > MAX_PREDICTED_STROKES:
        raise ValueError(f"strokes exceeds the maximum of {MAX_PREDICTED_STROKES}")

    validated = []
    invalid = []
    previous_start = -1
    for position, stroke in enumerate(strokes, start=1):
        try:
            if not isinstance(stroke, dict):
                raise ValueError("must be an object")
            if not {"player", "stroke", "start_frame"}.issubset(stroke):
                raise ValueError("is missing required fields")
            player = stroke["player"]
            if player not in valid_players:
                raise ValueError("has a player outside the vocabulary")
            name = stroke["stroke"]
            if name not in valid_strokes:
                raise ValueError("has a stroke outside the vocabulary")
            start = stroke["start_frame"]
            if isinstance(start, bool) or not isinstance(start, int):
                raise ValueError("has a non-integer start_frame")
            if not 0 <= start < VIDEO_FRAMES:
                raise ValueError("has a start_frame outside the video")
            if start < previous_start:
                raise ValueError("is not in chronological order")
            previous_start = start
            validated.append(
                {"player": player, "stroke": name, "start_frame": start}
            )
        except ValueError as error:
            invalid.append(f"stroke {position} {error}")
    return validated, len(strokes), invalid


def localized(prediction, truth):
    return abs(prediction["start_frame"] - truth["start_frame"]) <= TOLERANCE_FRAMES


def matches(prediction, truth):
    return (
        prediction["player"] == truth["player"]
        and prediction["stroke"] == truth["stroke"]
        and localized(prediction, truth)
    )


def matches_player_only(prediction, truth):
    return prediction["player"] == truth["player"] and localized(prediction, truth)


def monotonic_true_positives(predictions, ground_truth, matcher):
    """Largest order-preserving one-to-one alignment (LCS-style DP). Predictions are
    consumed in the order submitted and the key is chronological, so an out-of-order
    ledger loses matches."""
    columns = len(ground_truth) + 1
    previous = [0] * columns
    for prediction in predictions:
        current = [0]
        for index in range(1, columns):
            best = max(previous[index], current[index - 1])
            if matcher(prediction, ground_truth[index - 1]):
                best = max(best, previous[index - 1] + 1)
            current.append(best)
        previous = current
    return previous[-1]


def score(predictions, ground_truth, predicted_count):
    true_positives = monotonic_true_positives(predictions, ground_truth, matches)
    precision = true_positives / predicted_count if predicted_count else 0.0
    recall = true_positives / len(ground_truth) if ground_truth else 0.0
    reward = (
        2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    )
    return reward, {
        "ground_truth_strokes": len(ground_truth),
        "predicted_strokes": predicted_count,
        "valid_predicted_strokes": len(predictions),
        "invalid_predicted_strokes": predicted_count - len(predictions),
        "true_positives": true_positives,
        "false_positives": predicted_count - true_positives,
        "false_negatives": len(ground_truth) - true_positives,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(reward, 6),
        "frame_tolerance": TOLERANCE_FRAMES,
        # Diagnostics: how far the ledger got without the full tuple. Not scored.
        "player_and_frame_matches": monotonic_true_positives(
            predictions, ground_truth, matches_player_only
        ),
        "frame_only_matches": monotonic_true_positives(
            predictions, ground_truth, localized
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--reward-json", required=True, type=Path)
    parser.add_argument("--reward-txt", required=True, type=Path)
    # Harbor parses the whole of reward.json as dict[str, float | int], so the
    # non-numeric `reason` and any nesting have to live in a separate file.
    parser.add_argument("--details-json", type=Path)
    args = parser.parse_args()

    ground_truth = load_ground_truth()
    valid_players, valid_strokes = load_vocabulary(ground_truth)

    reason = "ok"
    predicted_count = 0
    try:
        predictions, predicted_count, invalid = load_prediction(
            args.solution, valid_players, valid_strokes
        )
        if invalid:
            reason = "; ".join(invalid[:10])
    except Exception as error:  # noqa: BLE001 - a malformed submission scores 0
        predictions = []
        reason = f"invalid solution: {error}"

    reward, details = score(predictions, ground_truth, predicted_count)

    rewards = {"reward": round(reward, 6), **details}
    assert all(
        isinstance(v, (int, float)) and not isinstance(v, bool)
        for v in rewards.values()
    ), "reward.json must stay a flat map of numbers"

    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps(rewards, indent=2) + "\n")
    args.reward_txt.write_text(f"{round(reward, 6)}\n")

    if args.details_json:
        args.details_json.parent.mkdir(parents=True, exist_ok=True)
        args.details_json.write_text(
            json.dumps({**rewards, "reason": reason}, indent=2) + "\n"
        )


if __name__ == "__main__":
    main()
