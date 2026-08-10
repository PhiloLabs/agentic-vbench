#!/usr/bin/env python3
"""Grade full-match badminton long-rally checkpoint reconstruction."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


CHECKPOINT_FIELDS = (
    "stroke_index",
    "hitter",
    "hitter_zone",
    "receiver_zone",
    "destination_zone",
)


def numeric(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def match_rallies(
    predictions: list[Any], references: list[dict[str, Any]]
) -> list[tuple[int, int, float]]:
    candidates = []
    for pred_index, prediction in enumerate(predictions):
        if not isinstance(prediction, dict):
            continue
        pred_stroke_count = numeric(prediction.get("stroke_count"))
        if pred_stroke_count is None or pred_stroke_count < 20:
            continue
        pred_start = numeric(prediction.get("rally_start_s"))
        if pred_start is None:
            continue
        for ref_index, reference in enumerate(references):
            if prediction.get("set") != reference["set"]:
                continue
            delta = abs(pred_start - reference["rally_start_s"])
            if delta <= 2.0:
                candidates.append((delta, pred_index, ref_index))

    used_predictions = set()
    used_references = set()
    matches = []
    for delta, pred_index, ref_index in sorted(candidates):
        if pred_index in used_predictions or ref_index in used_references:
            continue
        used_predictions.add(pred_index)
        used_references.add(ref_index)
        matches.append((pred_index, ref_index, delta))
    return matches


def score(solution: Any, references: list[dict[str, Any]]) -> dict[str, Any]:
    predictions = (
        solution.get("rallies", [])
        if isinstance(solution, dict)
        and isinstance(solution.get("rallies", []), list)
        else []
    )
    matches = match_rallies(predictions, references)

    predicted_count = sum(
        len(rally.get("checkpoints", []))
        for rally in predictions
        if isinstance(rally, dict)
        and isinstance(rally.get("checkpoints", []), list)
    )
    reference_count = sum(len(rally["checkpoints"]) for rally in references)
    matched_predicted_count = sum(
        len(predictions[pred_index].get("checkpoints", []))
        for pred_index, _, _ in matches
        if isinstance(predictions[pred_index].get("checkpoints", []), list)
    )
    matched_reference_count = sum(
        len(references[ref_index]["checkpoints"])
        for _, ref_index, _ in matches
    )
    true_positives = 0
    field_hits = defaultdict(int)
    field_total = defaultdict(int)
    composite_hits = defaultdict(int)
    composite_total = defaultdict(int)
    parent_exact_rallies = 0
    matched_details = []

    for pred_index, ref_index, start_delta in matches:
        prediction = predictions[pred_index]
        reference = references[ref_index]
        parent_ok = (
            prediction.get("stroke_count") == reference["stroke_count"]
            and prediction.get("rally_winner") == reference["rally_winner"]
        )
        parent_exact_rallies += int(parent_ok)
        pred_checkpoints = prediction.get("checkpoints", [])
        if not isinstance(pred_checkpoints, list):
            pred_checkpoints = []

        used_pred_checkpoints = set()
        rally_true_positives = 0
        for ref_checkpoint in reference["checkpoints"]:
            kind = ref_checkpoint["kind"]
            candidate_indices = [
                index
                for index, item in enumerate(pred_checkpoints)
                if index not in used_pred_checkpoints
                and isinstance(item, dict)
                and item.get("kind") == kind
            ]
            if not candidate_indices:
                continue
            pred_checkpoint_index = candidate_indices[0]
            used_pred_checkpoints.add(pred_checkpoint_index)
            pred_checkpoint = pred_checkpoints[pred_checkpoint_index]

            for field in CHECKPOINT_FIELDS:
                field_total[field] += 1
                if pred_checkpoint.get(field) == ref_checkpoint[field]:
                    field_hits[field] += 1

            pred_contact = numeric(pred_checkpoint.get("contact_s"))
            contact_ok = (
                pred_contact is not None
                and abs(pred_contact - ref_checkpoint["contact_s"]) <= 1.0
            )
            field_total["contact_s"] += 1
            field_hits["contact_s"] += int(contact_ok)

            exact_checkpoint = all(
                pred_checkpoint.get(field) == ref_checkpoint[field]
                for field in CHECKPOINT_FIELDS
            )
            identity_time_ok = (
                pred_checkpoint.get("stroke_index")
                == ref_checkpoint["stroke_index"]
                and pred_checkpoint.get("hitter") == ref_checkpoint["hitter"]
                and contact_ok
            )
            location_pair_ok = (
                pred_checkpoint.get("hitter_zone")
                == ref_checkpoint["hitter_zone"]
                and pred_checkpoint.get("receiver_zone")
                == ref_checkpoint["receiver_zone"]
            )
            zone_triplet_ok = (
                location_pair_ok
                and pred_checkpoint.get("destination_zone")
                == ref_checkpoint["destination_zone"]
            )
            for name, value in (
                ("identity_time", identity_time_ok),
                ("location_pair", location_pair_ok),
                ("zone_triplet", zone_triplet_ok),
                ("checkpoint_without_parent", exact_checkpoint and contact_ok),
            ):
                composite_total[name] += 1
                composite_hits[name] += int(value)

            parent_required = kind == "final"
            if (
                (parent_ok or not parent_required)
                and exact_checkpoint
                and contact_ok
            ):
                true_positives += 1
                rally_true_positives += 1

        matched_details.append(
            {
                "prediction_index": pred_index,
                "reference_set": reference["set"],
                "reference_start_s": reference["rally_start_s"],
                "start_delta_s": round(start_delta, 3),
                "stroke_count_ok": (
                    prediction.get("stroke_count") == reference["stroke_count"]
                ),
                "winner_ok": (
                    prediction.get("rally_winner") == reference["rally_winner"]
                ),
                "checkpoint_true_positives": rally_true_positives,
            }
        )

    checkpoint_precision = (
        true_positives / matched_predicted_count
        if matched_predicted_count
        else 0.0
    )
    checkpoint_recall = (
        true_positives / matched_reference_count
        if matched_reference_count
        else 0.0
    )
    checkpoint_f1 = (
        2
        * checkpoint_precision
        * checkpoint_recall
        / (checkpoint_precision + checkpoint_recall)
        if checkpoint_precision + checkpoint_recall
        else 0.0
    )
    qualification_precision = (
        len(matches) / len(predictions) if predictions else 0.0
    )
    qualification_recall = (
        len(matches) / len(references) if references else 0.0
    )
    qualification_f1 = (
        2
        * qualification_precision
        * qualification_recall
        / (qualification_precision + qualification_recall)
        if qualification_precision + qualification_recall
        else 0.0
    )
    reward = qualification_f1 * checkpoint_f1

    return {
        "reward": round(reward, 6),
        "true_positives": true_positives,
        "predicted_checkpoints": predicted_count,
        "reference_checkpoints": reference_count,
        "predicted_rallies": len(predictions),
        "reference_rallies": len(references),
        "matched_rallies": len(matches),
        "qualification": {
            "precision": round(qualification_precision, 6),
            "recall": round(qualification_recall, 6),
            "f1": round(qualification_f1, 6),
        },
        "checkpoint_reconstruction_on_matched_rallies": {
            "true_positives": true_positives,
            "predicted_checkpoints": matched_predicted_count,
            "reference_checkpoints": matched_reference_count,
            "precision": round(checkpoint_precision, 6),
            "recall": round(checkpoint_recall, 6),
            "f1": round(checkpoint_f1, 6),
            "matched_parent_metadata_exact": parent_exact_rallies,
        },
        "field_accuracy_on_matched_checkpoint_kinds": {
            field: round(field_hits[field] / total, 6) if total else 0.0
            for field, total in sorted(field_total.items())
        },
        "composite_accuracy_on_matched_checkpoint_kinds": {
            field: round(composite_hits[field] / total, 6) if total else 0.0
            for field, total in sorted(composite_total.items())
        },
        "matches": matched_details,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--reward-json", required=True, type=Path)
    parser.add_argument("--reward-txt", required=True, type=Path)
    args = parser.parse_args()

    try:
        solution = json.loads(args.solution.read_text(encoding="utf-8-sig"))
        reason = "ok"
    except Exception as exc:
        solution = {"rallies": []}
        reason = f"unreadable solution.json: {exc}"

    references = json.loads(
        args.reference.read_text(encoding="utf-8-sig")
    )["rallies"]
    report = score(solution, references)
    report["reason"] = reason

    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_txt.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    args.reward_txt.write_text(f"{report['reward']}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
