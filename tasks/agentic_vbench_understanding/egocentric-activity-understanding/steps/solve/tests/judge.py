#!/usr/bin/env python3
"""Grade an egocentric fine-grained action ledger. Pure Python stdlib, deterministic.

The agent must list every annotated action in a 17-minute egocentric cooking video as
(verb, nouns, start_frame, end_frame). A predicted action is a true positive only when
it fully reconstructs the action: the same verb, the same noun set, and BOTH frame
boundaries within TOLERANCE_FRAMES of the annotated boundaries, under an
order-preserving one-to-one alignment. reward = F1, so misses and false positives both
cost. The two extra `*_matches` counters are diagnostics only and never touch reward.
"""
import argparse
import json
import math
import os
import stat
from pathlib import Path

# 12 frames = 0.50 s at the annotation's 24 Hz. The median annotated action is 35
# frames long, so this is a bit under half an action-length of slack on each boundary.
# At this width no two annotated actions sharing a verb and noun set are mutually
# confusable, so the one-to-one alignment stays well defined.
TOLERANCE_FRAMES = 12
MAX_PREDICTED_ACTIONS = 2000
MAX_SOLUTION_BYTES = 2_000_000
VIDEO_FRAMES = 25692


def _load(name):
    return json.loads(Path(__file__).with_name(name).read_text())


def load_ground_truth():
    return _load("gt.json")["actions"]


def load_vocabulary(ground_truth):
    """The closed label space is exactly the verbs and nouns the answer key uses, so
    deriving it here leaves one vocabulary.json in the repo — the agent-facing copy
    baked into the image — and makes judge/agent drift impossible by construction."""
    verbs = {action["verb"] for action in ground_truth}
    nouns = {noun for action in ground_truth for noun in action["nouns"]}
    return verbs, nouns


def load_prediction(path, valid_verbs, valid_nouns):
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

    if not isinstance(document, dict) or "actions" not in document:
        raise ValueError("solution must be an object containing actions")
    actions = document["actions"]
    if not isinstance(actions, list):
        raise ValueError("actions must be a list")
    if len(actions) > MAX_PREDICTED_ACTIONS:
        raise ValueError(f"actions exceeds the maximum of {MAX_PREDICTED_ACTIONS}")

    validated = []
    invalid = []
    previous_start = -1
    for position, action in enumerate(actions, start=1):
        try:
            if not isinstance(action, dict):
                raise ValueError("must be an object")
            if not {"verb", "nouns", "start_frame", "end_frame"}.issubset(action):
                raise ValueError("is missing required fields")
            verb = action["verb"]
            if verb not in valid_verbs:
                raise ValueError("has a verb outside the vocabulary")
            nouns = action["nouns"]
            if not isinstance(nouns, list) or not nouns:
                raise ValueError("must list at least one noun")
            if any(noun not in valid_nouns for noun in nouns):
                raise ValueError("has a noun outside the vocabulary")
            if len(set(nouns)) != len(nouns):
                raise ValueError("repeats a noun")
            start = action["start_frame"]
            end = action["end_frame"]
            for value in (start, end):
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError("has non-integer frame numbers")
            if not 0 <= start < end < VIDEO_FRAMES:
                raise ValueError("has frame numbers outside the video")
            if start < previous_start:
                raise ValueError("is not in chronological order")
            previous_start = start
            validated.append(
                {
                    "verb": verb,
                    "nouns": frozenset(nouns),
                    "start_frame": start,
                    "end_frame": end,
                }
            )
        except ValueError as error:
            invalid.append(f"action {position} {error}")
    return validated, len(actions), invalid


def localized(prediction, truth):
    return (
        abs(prediction["start_frame"] - truth["start_frame"]) <= TOLERANCE_FRAMES
        and abs(prediction["end_frame"] - truth["end_frame"]) <= TOLERANCE_FRAMES
    )


def matches(prediction, truth):
    return (
        prediction["verb"] == truth["verb"]
        and prediction["nouns"] == frozenset(truth["nouns"])
        and localized(prediction, truth)
    )


def matches_verb_only(prediction, truth):
    return prediction["verb"] == truth["verb"] and localized(prediction, truth)


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
        "ground_truth_actions": len(ground_truth),
        "predicted_actions": predicted_count,
        "valid_predicted_actions": len(predictions),
        "invalid_predicted_actions": predicted_count - len(predictions),
        "true_positives": true_positives,
        "false_positives": predicted_count - true_positives,
        "false_negatives": len(ground_truth) - true_positives,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(reward, 6),
        "frame_tolerance": TOLERANCE_FRAMES,
        # Diagnostics: how far the ledger got without the full tuple. Not scored.
        "verb_and_boundary_matches": monotonic_true_positives(
            predictions, ground_truth, matches_verb_only
        ),
        "boundary_only_matches": monotonic_true_positives(
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
    valid_verbs, valid_nouns = load_vocabulary(ground_truth)

    reason = "ok"
    predicted_count = 0
    try:
        predictions, predicted_count, invalid = load_prediction(
            args.solution, valid_verbs, valid_nouns
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
