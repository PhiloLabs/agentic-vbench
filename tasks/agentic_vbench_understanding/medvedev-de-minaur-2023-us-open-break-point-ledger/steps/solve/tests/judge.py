#!/usr/bin/env python3
"""Score ordered break-point identities with hierarchical field-level credit."""

import argparse
from collections import Counter
from fractions import Fraction
import json
from pathlib import Path

SCORER_VERSION = "hierarchical-bottleneck-v1"
MAX_PREDICTED_EVENTS = 256
MAX_SHOTS_PER_EVENT = 512
MAX_TOTAL_PREDICTED_SHOTS = 4096

IDENTITY_FIELDS = (
    "set",
    "medvedev_games",
    "de_minaur_games",
    "medvedev_points",
    "de_minaur_points",
    "server",
    "opportunity",
)

SUMMARY_FIELDS = (
    "outcome",
    "first_serve_in",
    "serve_direction",
    "rally_shots",
    "terminal_player",
    "terminal_stroke",
    "terminal_court_position",
    "terminal_result",
    "terminal_error",
)

SHOT_FIELDS = ("stroke", "direction")
SCALAR_FIELDS = IDENTITY_FIELDS + SUMMARY_FIELDS
EVENT_FIELDS = SCALAR_FIELDS + ("shots",)

EVENT_ROWS = [
    (1, 1, 1, "30", "40", "Daniil Medvedev", 1, "saved", True, "down_the_t", 7, "Alex De Minaur", "backhand_lob", "baseline", "forced_error", "deep"),
    (1, 2, 2, "30", "40", "Daniil Medvedev", 1, "converted", True, "wide", 4, "Alex De Minaur", "backhand_groundstroke", "net", "winner", "none"),
    (1, 2, 4, "15", "40", "Daniil Medvedev", 1, "converted", True, "down_the_t", 2, "Daniil Medvedev", "forehand_groundstroke", "baseline", "forced_error", "net"),
    (2, 2, 1, "40", "15", "Alex De Minaur", 1, "saved", False, "body", 9, "Daniil Medvedev", "backhand_groundstroke", "baseline", "unforced_error", "net"),
    (2, 2, 1, "40", "30", "Alex De Minaur", 2, "saved", True, "wide", 3, "Alex De Minaur", "forehand_volley", "net", "winner", "none"),
    (2, 2, 1, "AD", "40", "Alex De Minaur", 3, "saved", False, "body", 25, "Alex De Minaur", "forehand_groundstroke", "baseline", "winner", "none"),
    (2, 2, 1, "AD", "40", "Alex De Minaur", 4, "saved", True, "body", 1, "Daniil Medvedev", "backhand_groundstroke", "baseline", "forced_error", "deep"),
    (2, 2, 1, "AD", "40", "Alex De Minaur", 5, "saved", True, "wide", 1, "Alex De Minaur", "serve", "serve", "ace", "none"),
    (2, 5, 4, "40", "15", "Alex De Minaur", 1, "converted", True, "body", 6, "Alex De Minaur", "forehand_slice", "baseline", "forced_error", "deep"),
    (3, 2, 1, "AD", "40", "Alex De Minaur", 1, "converted", True, "wide", 12, "Alex De Minaur", "backhand_groundstroke", "baseline", "unforced_error", "deep"),
    (3, 4, 1, "40", "30", "Alex De Minaur", 1, "converted", False, "wide", 2, "Alex De Minaur", "forehand_groundstroke", "baseline", "unforced_error", "deep"),
    (4, 0, 1, "30", "40", "Daniil Medvedev", 1, "saved", True, "wide", 11, "Daniil Medvedev", "backhand_groundstroke", "net", "winner", "none"),
    (4, 1, 1, "40", "0", "Alex De Minaur", 1, "converted", False, "body", 6, "Alex De Minaur", "backhand_volley", "net", "unforced_error", "net"),
    (4, 3, 1, "40", "0", "Alex De Minaur", 1, "converted", False, "body", 8, "Daniil Medvedev", "backhand_groundstroke", "baseline", "winner", "none"),
    (4, 4, 1, "30", "40", "Daniil Medvedev", 1, "saved", True, "down_the_t", 1, "Daniil Medvedev", "serve", "serve", "unreturnable", "none"),
    (4, 4, 1, "40", "AD", "Daniil Medvedev", 2, "saved", False, "body", 5, "Alex De Minaur", "backhand_groundstroke", "baseline", "unforced_error", "deep"),
]

LIVE_RALLY_CODES = (
    "6f28f1f3b3y1f-3m3d#",
    "4+b27h^3b-1*",
    "6b29f2n#",
    "5f28b1f2f2f3b2b3b3b3n@",
    "4+b2v3*",
    "5b29f3b3b3b3b2b3b3b3b3b3b2f2f2f3s3f3b3b3b3b3b3b2f3*",
    "5b2d#",
    "4*",
    "5b38s3b1r2f1r1d#",
    "4b28f3b3b3b3s1f1f2b3b3b3b3d@",
    "4b39f2d@",
    "4b28f1f1f3b1f3u1f-1f2b-3*",
    "5b29f1f1u+3i3z1n@",
    "5b38b2b2b2b2b+2b1*",
    "6#",
    "5f38b1f2f2b1d@",
)

STROKE_CODES = {
    "f": "forehand_groundstroke",
    "b": "backhand_groundstroke",
    "r": "forehand_slice",
    "s": "backhand_slice",
    "v": "forehand_volley",
    "z": "backhand_volley",
    "o": "overhead",
    "p": "backhand_overhead",
    "u": "forehand_drop_shot",
    "y": "backhand_drop_shot",
    "l": "forehand_lob",
    "m": "backhand_lob",
    "h": "forehand_half_volley",
    "i": "backhand_half_volley",
    "j": "forehand_swinging_volley",
    "k": "backhand_swinging_volley",
    "t": "trick_shot",
    "q": "unknown",
}

SERVE_DIRECTIONS = {
    "0": "unknown",
    "4": "wide",
    "5": "body",
    "6": "down_the_t",
}

RALLY_DIRECTIONS = {
    "0": "unknown",
    "1": "receiver_forehand",
    "2": "middle",
    "3": "receiver_backhand",
}


def decode_live_rally(code):
    index = 0
    while code[index] == "c":
        index += 1
    serve_code = code[index]
    if serve_code not in SERVE_DIRECTIONS:
        raise ValueError(f"invalid serve code: {code}")
    shots = [{"stroke": "serve", "direction": SERVE_DIRECTIONS[serve_code]}]
    index += 1
    while index < len(code) and code[index] == "+":
        index += 1
    if index < len(code) and code[index] in "*#":
        if index != len(code) - 1:
            raise ValueError(f"trailing serve outcome data: {code}")
        return shots

    first_rally_contact = True
    while index < len(code):
        stroke_code = code[index]
        if stroke_code not in STROKE_CODES:
            raise ValueError(f"invalid stroke code at {index}: {code}")
        index += 1
        while index < len(code) and code[index] in "+-=;^":
            index += 1
        direction = "unknown"
        if index < len(code) and code[index] in RALLY_DIRECTIONS:
            direction = RALLY_DIRECTIONS[code[index]]
            index += 1
        if first_rally_contact and index < len(code) and code[index] in "789":
            index += 1
        first_rally_contact = False
        shots.append({"stroke": STROKE_CODES[stroke_code], "direction": direction})
        if index < len(code) and code[index] in "nwdxe!":
            index += 1
        if index < len(code) and code[index] in "*@#":
            index += 1
            if index != len(code):
                raise ValueError(f"trailing rally outcome data: {code}")
    return shots


REFERENCE_EVENTS = []
if len(EVENT_ROWS) != len(LIVE_RALLY_CODES):
    raise ValueError("event and rally-code counts differ")
for row, code in zip(EVENT_ROWS, LIVE_RALLY_CODES):
    if len(row) != len(SCALAR_FIELDS):
        raise ValueError("event row has the wrong number of fields")
    event = dict(zip(SCALAR_FIELDS, row))
    event["shots"] = decode_live_rally(code)
    REFERENCE_EVENTS.append(event)

EXPECTED_TYPES = {
    field: type(REFERENCE_EVENTS[0][field]) for field in SCALAR_FIELDS
}


def identity_key(event):
    if not isinstance(event, dict):
        return None
    values = []
    for field in IDENTITY_FIELDS:
        if field not in event or type(event[field]) is not EXPECTED_TYPES[field]:
            return None
        values.append(event[field])
    return tuple(values)


def validate_resource_limits(predictions):
    if len(predictions) > MAX_PREDICTED_EVENTS:
        raise ValueError(
            f"break_points exceeds {MAX_PREDICTED_EVENTS} events"
        )
    total_shots = 0
    for event in predictions:
        if not isinstance(event, dict) or not isinstance(event.get("shots"), list):
            continue
        shot_count = len(event["shots"])
        if shot_count > MAX_SHOTS_PER_EVENT:
            raise ValueError(
                f"one shots array exceeds {MAX_SHOTS_PER_EVENT} entries"
            )
        total_shots += shot_count
    if total_shots > MAX_TOTAL_PREDICTED_SHOTS:
        raise ValueError(
            "all shots arrays exceed "
            f"{MAX_TOTAL_PREDICTED_SHOTS} entries"
        )


def correct_summary_fields(prediction, reference):
    return tuple(
        field
        for field in SUMMARY_FIELDS
        if field in prediction
        and type(prediction[field]) is EXPECTED_TYPES[field]
        and prediction[field] == reference[field]
    )


def shot_token(shot):
    if not isinstance(shot, dict):
        return (None, None)
    return tuple(
        shot.get(field) if type(shot.get(field)) is str else None
        for field in SHOT_FIELDS
    )


def shot_tokens(event):
    if not isinstance(event, dict) or "shots" not in event:
        return []
    shots = event["shots"]
    if not isinstance(shots, list):
        return [(None, None)]
    return [shot_token(shot) for shot in shots]


def aligned_shot_fields(predicted, reference):
    previous = [0] * (len(reference) + 1)
    for predicted_token in predicted:
        current = [0]
        for reference_index, reference_token in enumerate(reference, start=1):
            field_credit = sum(
                predicted_value is not None
                and predicted_value == reference_value
                for predicted_value, reference_value
                in zip(predicted_token, reference_token)
            )
            current.append(max(
                previous[reference_index],
                current[-1],
                previous[reference_index - 1] + field_credit,
            ))
        previous = current
    return previous[-1]


def layer_atoms(event, reference):
    prediction_tokens = shot_tokens(event)
    reference_tokens = shot_tokens(reference)
    return (
        len(correct_summary_fields(event, reference)),
        aligned_shot_fields(prediction_tokens, reference_tokens),
        len(SHOT_FIELDS) * len(prediction_tokens),
        len(SHOT_FIELDS) * len(reference_tokens),
    )


def pair_quality(event, reference):
    """Return bottleneck detail credit and the atoms used to derive it."""
    summary_correct, shot_correct, shot_predicted, shot_reference = layer_atoms(
        event, reference
    )
    summary_accuracy = Fraction(summary_correct, len(SUMMARY_FIELDS))
    shot_denominator = max(shot_predicted, shot_reference)
    shot_accuracy = (
        Fraction(shot_correct, shot_denominator)
        if shot_denominator
        else Fraction(0)
    )
    return (
        min(summary_accuracy, shot_accuracy),
        summary_correct,
        shot_correct,
        shot_predicted,
        shot_reference,
    )


def better_alignment(candidate, incumbent):
    """Choose a deterministic weighted-LCS state."""
    for index in (0, 1, 2, 3):
        if candidate[index] != incumbent[index]:
            return candidate[index] > incumbent[index]
    if candidate[4] != incumbent[4]:
        return candidate[4] < incumbent[4]
    return candidate[5] < incumbent[5]


def ordered_identity_matches(prediction_keys, reference_keys):
    """Return the identity-only ordered LCS length for diagnostics."""
    previous = [0] * (len(reference_keys) + 1)
    for prediction_key in prediction_keys:
        current = [0]
        for reference_index, reference_key in enumerate(reference_keys, start=1):
            current.append(max(
                previous[reference_index],
                current[-1],
                previous[reference_index - 1]
                + int(prediction_key is not None and prediction_key == reference_key),
            ))
        previous = current
    return previous[-1]


def exact_event_match(prediction, reference):
    """Require every identity, summary, and ordered shot field to be correct."""
    prediction_key = identity_key(prediction)
    return (
        prediction_key is not None
        and prediction_key == identity_key(reference)
        and len(correct_summary_fields(prediction, reference))
        == len(SUMMARY_FIELDS)
        and shot_tokens(prediction) == shot_tokens(reference)
    )


def ordered_exact_matches(predictions):
    """Return the exact-event LCS length retained as a strict diagnostic."""
    previous = [0] * (len(REFERENCE_EVENTS) + 1)
    for prediction in predictions:
        current = [0]
        for reference_index, reference in enumerate(REFERENCE_EVENTS, start=1):
            current.append(max(
                previous[reference_index],
                current[-1],
                previous[reference_index - 1]
                + int(exact_event_match(prediction, reference)),
            ))
        previous = current
    return previous[-1]


def align_events(predictions):
    """Maximize summed per-event quality under exact ordered identity matching."""
    prediction_keys = [identity_key(event) for event in predictions]
    reference_keys = [identity_key(event) for event in REFERENCE_EVENTS]
    columns = len(REFERENCE_EVENTS) + 1
    empty = (Fraction(0), 0, 0, 0, 0, ())
    previous = [empty for _ in range(columns)]

    for prediction_index, prediction in enumerate(predictions, start=1):
        current = [previous[0]]
        for reference_index in range(1, columns):
            candidates = [previous[reference_index], current[reference_index - 1]]
            if (
                prediction_keys[prediction_index - 1]
                == reference_keys[reference_index - 1]
                and prediction_keys[prediction_index - 1] is not None
            ):
                reference = REFERENCE_EVENTS[reference_index - 1]
                (
                    event_credit,
                    summary_correct,
                    shot_correct,
                    shot_predicted,
                    shot_reference,
                ) = pair_quality(prediction, reference)
                diagonal = previous[reference_index - 1]
                candidates.append((
                    diagonal[0] + event_credit,
                    diagonal[1] + 1,
                    diagonal[2] + summary_correct,
                    diagonal[3] + shot_correct,
                    diagonal[4] + max(shot_predicted, shot_reference),
                    diagonal[5] + ((prediction_index - 1, reference_index - 1),),
                ))
            best = candidates[0]
            for candidate in candidates[1:]:
                if better_alignment(candidate, best):
                    best = candidate
            current.append(best)
        previous = current
    return previous[-1]


def score_predictions(predictions):
    validate_resource_limits(predictions)
    predicted_count = len(predictions)
    (
        aligned_event_credit,
        quality_matched_count,
        aligned_summary_correct,
        aligned_shot_correct,
        aligned_pair_shot_denominator,
        matched_pairs,
    ) = align_events(predictions)
    ground_truth_count = len(REFERENCE_EVENTS)
    prediction_keys = [identity_key(event) for event in predictions]
    reference_keys = [identity_key(event) for event in REFERENCE_EVENTS]
    identity_matched_count = ordered_identity_matches(
        prediction_keys, reference_keys
    )
    exact_matched_count = ordered_exact_matches(predictions)
    identity_precision = (
        identity_matched_count / predicted_count if predicted_count else 0.0
    )
    identity_recall = identity_matched_count / ground_truth_count
    identity_f1 = (
        2 * identity_precision * identity_recall / (identity_precision + identity_recall)
        if identity_precision + identity_recall
        else 0.0
    )

    summary_correct = 0
    present_summary_fields = 0
    summary_total = len(SUMMARY_FIELDS) * quality_matched_count
    per_field = Counter()
    pair_details = []
    predicted_shot_fields = 0
    reference_shot_fields = 0
    correct_shot_fields = 0
    fully_correct_events_in_quality_alignment = 0
    scored_event_credit = Fraction(0)
    scored_pair_shot_denominator = 0

    for prediction_index, reference_index in matched_pairs:
        prediction = predictions[prediction_index]
        reference = REFERENCE_EVENTS[reference_index]
        (
            event_credit,
            pair_summary_correct,
            pair_shot_fields,
            pair_predicted_shot_fields,
            pair_reference_shot_fields,
        ) = pair_quality(prediction, reference)
        fields = correct_summary_fields(prediction, reference)
        if pair_summary_correct != len(fields):
            raise ValueError("pair summary totals do not match scored fields")
        summary_correct += len(fields)
        present_summary_fields += sum(
            field in prediction for field in SUMMARY_FIELDS
        )
        per_field.update(fields)
        prediction_tokens = shot_tokens(prediction)
        reference_tokens = shot_tokens(reference)
        predicted_shot_fields += pair_predicted_shot_fields
        reference_shot_fields += pair_reference_shot_fields
        correct_shot_fields += pair_shot_fields
        scored_event_credit += event_credit
        pair_shot_denominator = max(
            pair_predicted_shot_fields, pair_reference_shot_fields
        )
        scored_pair_shot_denominator += pair_shot_denominator
        fully_correct_events_in_quality_alignment += (
            len(fields) == len(SUMMARY_FIELDS)
            and prediction_tokens == reference_tokens
        )
        pair_details.append({
            "prediction_index": prediction_index,
            "reference_index": reference_index,
            "correct_summary_fields": list(fields),
            "predicted_shots": len(prediction_tokens),
            "reference_shots": len(reference_tokens),
            "correct_shot_fields": pair_shot_fields,
            "summary_accuracy": round(
                pair_summary_correct / len(SUMMARY_FIELDS), 4
            ),
            "shot_denominator": pair_shot_denominator,
            "shot_accuracy": round(float(
                Fraction(
                    pair_shot_fields,
                    pair_shot_denominator,
                )
            ), 4),
            "event_credit": round(float(event_credit), 4),
        })

    shot_precision = (
        correct_shot_fields / predicted_shot_fields if predicted_shot_fields else 0.0
    )
    shot_recall = (
        correct_shot_fields / reference_shot_fields if reference_shot_fields else 0.0
    )
    shot_f1 = (
        2 * shot_precision * shot_recall / (shot_precision + shot_recall)
        if shot_precision + shot_recall
        else 0.0
    )
    summary_accuracy = summary_correct / summary_total if summary_total else 0.0
    shot_denominator = scored_pair_shot_denominator
    shot_accuracy = (
        correct_shot_fields / shot_denominator if shot_denominator else 0.0
    )
    detail_fields_correct = summary_correct + correct_shot_fields
    detail_fields_predicted = summary_total + predicted_shot_fields
    detail_fields_reference = summary_total + reference_shot_fields
    detail_precision = (
        detail_fields_correct / detail_fields_predicted
        if detail_fields_predicted
        else 0.0
    )
    detail_recall = (
        detail_fields_correct / detail_fields_reference
        if detail_fields_reference
        else 0.0
    )
    detail_f1 = (
        2 * detail_precision * detail_recall / (detail_precision + detail_recall)
        if detail_precision + detail_recall
        else 0.0
    )
    detail_denominator = summary_total + scored_pair_shot_denominator
    detail_accuracy = (
        detail_fields_correct / detail_denominator if detail_denominator else 0.0
    )
    if (
        scored_event_credit,
        summary_correct,
        correct_shot_fields,
        scored_pair_shot_denominator,
    ) != (
        aligned_event_credit,
        aligned_summary_correct,
        aligned_shot_correct,
        aligned_pair_shot_denominator,
    ):
        raise ValueError("alignment totals do not match scored pairs")
    if exact_matched_count > identity_matched_count:
        raise ValueError("exact matches exceed identity matches")
    reward_denominator = predicted_count + ground_truth_count
    hierarchical_event_f1 = (
        Fraction(2) * scored_event_credit / reward_denominator
        if reward_denominator
        else Fraction(0)
    )
    hierarchical_precision = (
        scored_event_credit / predicted_count
        if predicted_count
        else Fraction(0)
    )
    hierarchical_recall = Fraction(
        scored_event_credit, ground_truth_count
    )
    exact_event_f1 = (
        Fraction(2 * exact_matched_count, reward_denominator)
        if reward_denominator
        else Fraction(0)
    )
    reward = hierarchical_event_f1
    exact_precision = (
        Fraction(exact_matched_count, predicted_count)
        if predicted_count
        else Fraction(0)
    )
    exact_recall = Fraction(exact_matched_count, ground_truth_count)

    reference_key_counts = Counter(identity_key(event) for event in REFERENCE_EVENTS)
    prediction_key_counts = Counter(key for key in prediction_keys if key is not None)
    unordered_matches = sum(
        min(count, reference_key_counts.get(key, 0))
        for key, count in prediction_key_counts.items()
    )
    duplicates = sum(
        max(0, count - reference_key_counts[key])
        for key, count in prediction_key_counts.items()
        if key in reference_key_counts
    )
    false_identities = sum(
        count
        for key, count in prediction_key_counts.items()
        if key not in reference_key_counts
    )
    schema_issue_events = sum(
        not isinstance(event, dict) or set(event) != set(EVENT_FIELDS)
        for event in predictions
    )
    malformed_shot_sequences = sum(
        isinstance(event, dict)
        and "shots" in event
        and not isinstance(event["shots"], list)
        for event in predictions
    )
    shot_schema_issue_entries = sum(
        not isinstance(shot, dict)
        or set(shot) != set(SHOT_FIELDS)
        or any(type(shot.get(field)) is not str for field in SHOT_FIELDS)
        for event in predictions
        if isinstance(event, dict) and isinstance(event.get("shots"), list)
        for shot in event["shots"]
    )
    invalid_shot_entries = sum(
        not isinstance(shot, dict)
        or any(type(shot.get(field)) is not str for field in SHOT_FIELDS)
        for event in predictions
        if isinstance(event, dict) and isinstance(event.get("shots"), list)
        for shot in event["shots"]
    )

    return round(float(reward), 4), {
        "scorer_version": SCORER_VERSION,
        "n_ground_truth": ground_truth_count,
        "n_predicted": predicted_count,
        "identity_matches_ordered": identity_matched_count,
        "identity_matches_in_quality_alignment": quality_matched_count,
        "exact_event_matches_ordered": exact_matched_count,
        "identity_matches_unordered": unordered_matches,
        "invalid_identity_events": sum(key is None for key in prediction_keys),
        "false_identity_events": false_identities,
        "duplicate_identity_events": duplicates,
        "out_of_order_identity_matches": max(
            0, unordered_matches - identity_matched_count
        ),
        "schema_issue_events": schema_issue_events,
        "malformed_shot_sequences": malformed_shot_sequences,
        "shot_schema_issue_entries": shot_schema_issue_entries,
        "invalid_shot_entries": invalid_shot_entries,
        "identity_precision": round(identity_precision, 4),
        "identity_recall": round(identity_recall, 4),
        "identity_f1": round(identity_f1, 4),
        "exact_event_precision": round(float(exact_precision), 4),
        "exact_event_recall": round(float(exact_recall), 4),
        "exact_event_f1": round(float(exact_event_f1), 4),
        "summary_fields_correct": summary_correct,
        "summary_fields_present": present_summary_fields,
        "summary_fields_predicted": summary_total,
        "summary_fields_total": summary_total,
        "summary_accuracy": round(summary_accuracy, 4),
        "summary_correct_by_field": {
            field: per_field[field] for field in SUMMARY_FIELDS
        },
        "shot_fields_correct_ordered": correct_shot_fields,
        "shot_fields_predicted_in_matched_events": predicted_shot_fields,
        "shot_fields_reference_in_matched_events": reference_shot_fields,
        "shot_precision": round(shot_precision, 4),
        "shot_recall": round(shot_recall, 4),
        "shot_f1": round(shot_f1, 4),
        "shot_denominator": shot_denominator,
        "shot_accuracy": round(shot_accuracy, 4),
        "detail_fields_correct": detail_fields_correct,
        "detail_fields_predicted": detail_fields_predicted,
        "detail_fields_reference": detail_fields_reference,
        "detail_precision": round(detail_precision, 4),
        "detail_recall": round(detail_recall, 4),
        "detail_f1": round(detail_f1, 4),
        "detail_denominator": detail_denominator,
        "detail_accuracy": round(detail_accuracy, 4),
        "fully_correct_events": exact_matched_count,
        "fully_correct_events_in_quality_alignment": (
            fully_correct_events_in_quality_alignment
        ),
        "hierarchical_true_positive_credit": round(float(scored_event_credit), 4),
        "hierarchical_precision": round(float(hierarchical_precision), 4),
        "hierarchical_recall": round(float(hierarchical_recall), 4),
        "hierarchical_event_f1": round(float(hierarchical_event_f1), 4),
        "reward_denominator": reward_denominator,
        "matched_pairs": pair_details,
        "formula": (
            "2 * sum(min(per_event_summary_accuracy, "
            "per_event_ordered_shot_accuracy)) "
            "/ (n_predicted + n_reference)"
        ),
        "exact_event_formula": (
            "2 * exact_ordered_event_matches "
            "/ (n_predicted + n_reference)"
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--reward-json", required=True, type=Path)
    parser.add_argument("--reward-txt", required=True, type=Path)
    args = parser.parse_args()

    reason = "ok"
    predictions = []
    root_schema_issue = False
    try:
        solution = json.loads(args.solution.read_text())
        if not isinstance(solution, dict):
            root_schema_issue = True
            raise ValueError("solution root is not an object")
        root_schema_issue = set(solution) != {"break_points"}
        if "break_points" not in solution:
            raise ValueError("solution must contain the break_points key")
        predictions = solution["break_points"]
        if not isinstance(predictions, list):
            raise ValueError("break_points is not a list")
        reward, details = score_predictions(predictions)
    except Exception as exc:  # noqa: BLE001
        reason = f"unreadable solution.json: {exc}"
        predictions = []
        reward, details = score_predictions(predictions)
    details = {"reason": reason, "root_schema_issue": root_schema_issue, **details}
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps({"reward": reward, "details": details}, indent=2))
    args.reward_txt.write_text(f"{reward}\n")


if __name__ == "__main__":
    main()
