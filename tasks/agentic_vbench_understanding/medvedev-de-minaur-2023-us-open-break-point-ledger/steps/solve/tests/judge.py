#!/usr/bin/env python3
"""Deterministically score a complete break-point ledger by exact event F1."""

import argparse
import json
from pathlib import Path

FIELDS = (
    "set",
    "medvedev_games",
    "de_minaur_games",
    "medvedev_points",
    "de_minaur_points",
    "server",
    "opportunity",
    "first_serve_in",
    "outcome",
    "serve_direction",
    "rally_shots",
    "terminal_player",
    "terminal_stroke",
    "terminal_court_position",
    "terminal_result",
    "terminal_error",
)

GROUND_TRUTH = [
    (1, 1, 1, "30", "40", "Daniil Medvedev", 1, True, "saved", "down_the_t", 7, "Alex De Minaur", "backhand_lob", "baseline", "forced_error", "deep"),
    (1, 2, 2, "30", "40", "Daniil Medvedev", 1, True, "converted", "wide", 4, "Alex De Minaur", "backhand_groundstroke", "net", "winner", "none"),
    (1, 2, 4, "15", "40", "Daniil Medvedev", 1, True, "converted", "down_the_t", 2, "Daniil Medvedev", "forehand_groundstroke", "baseline", "forced_error", "net"),
    (2, 2, 1, "40", "15", "Alex De Minaur", 1, False, "saved", "body", 9, "Daniil Medvedev", "backhand_groundstroke", "baseline", "unforced_error", "net"),
    (2, 2, 1, "40", "30", "Alex De Minaur", 2, True, "saved", "wide", 3, "Alex De Minaur", "forehand_volley", "net", "winner", "none"),
    (2, 2, 1, "AD", "40", "Alex De Minaur", 3, False, "saved", "body", 25, "Alex De Minaur", "forehand_groundstroke", "baseline", "winner", "none"),
    (2, 2, 1, "AD", "40", "Alex De Minaur", 4, True, "saved", "body", 1, "Daniil Medvedev", "backhand_groundstroke", "baseline", "forced_error", "deep"),
    (2, 2, 1, "AD", "40", "Alex De Minaur", 5, True, "saved", "wide", 1, "Alex De Minaur", "serve", "serve", "ace", "none"),
    (2, 5, 4, "40", "15", "Alex De Minaur", 1, True, "converted", "body", 6, "Alex De Minaur", "forehand_slice", "baseline", "forced_error", "deep"),
    (3, 2, 1, "AD", "40", "Alex De Minaur", 1, True, "converted", "wide", 12, "Alex De Minaur", "backhand_groundstroke", "baseline", "unforced_error", "deep"),
    (3, 4, 1, "40", "30", "Alex De Minaur", 1, False, "converted", "wide", 2, "Alex De Minaur", "forehand_groundstroke", "baseline", "unforced_error", "deep"),
    (4, 0, 1, "30", "40", "Daniil Medvedev", 1, True, "saved", "wide", 11, "Daniil Medvedev", "backhand_groundstroke", "net", "winner", "none"),
    (4, 1, 1, "40", "0", "Alex De Minaur", 1, False, "converted", "body", 6, "Alex De Minaur", "backhand_volley", "net", "unforced_error", "net"),
    (4, 3, 1, "40", "0", "Alex De Minaur", 1, False, "converted", "body", 8, "Daniil Medvedev", "backhand_groundstroke", "baseline", "winner", "none"),
    (4, 4, 1, "30", "40", "Daniil Medvedev", 1, True, "saved", "down_the_t", 1, "Daniil Medvedev", "serve", "serve", "unreturnable", "none"),
    (4, 4, 1, "AD", "40", "Daniil Medvedev", 2, False, "saved", "body", 5, "Alex De Minaur", "backhand_groundstroke", "baseline", "unforced_error", "deep"),
]


def event_key(event):
    if not isinstance(event, dict) or set(event) != set(FIELDS):
        return None
    values = tuple(event[field] for field in FIELDS)
    if not all(type(value) is type(expected) for value, expected in zip(values, GROUND_TRUTH[0])):
        return None
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--reward-json", required=True, type=Path)
    parser.add_argument("--reward-txt", required=True, type=Path)
    args = parser.parse_args()

    reason = "ok"
    predictions = []
    try:
        solution = json.loads(args.solution.read_text())
        predictions = solution["break_points"]
        if not isinstance(predictions, list):
            raise ValueError("break_points is not a list")
    except Exception as exc:  # noqa: BLE001
        reason = f"unreadable solution.json: {exc}"

    unmatched = set(GROUND_TRUTH)
    true_positives = 0
    invalid_events = 0
    for prediction in predictions:
        key = event_key(prediction)
        if key is None:
            invalid_events += 1
        elif key in unmatched:
            unmatched.remove(key)
            true_positives += 1

    predicted_count = len(predictions)
    precision = true_positives / predicted_count if predicted_count else 0.0
    recall = true_positives / len(GROUND_TRUTH)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    details = {
        "reason": reason,
        "n_ground_truth": len(GROUND_TRUTH),
        "n_predicted": predicted_count,
        "true_positives_exact_event": true_positives,
        "invalid_events": invalid_events,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps({"reward": round(f1, 4), "details": details}, indent=2))
    args.reward_txt.write_text(f"{round(f1, 4)}\n")


if __name__ == "__main__":
    main()
