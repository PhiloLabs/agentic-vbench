#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--answer", required=True, type=Path)
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    answer = {
        row["card_id"]: row["transcript_id"]
        for row in json.loads(args.answer.read_text())["matches"]
    }
    try:
        document = json.loads(args.solution.read_text())
        rows = (
            document["matches"]
            if isinstance(document, dict) and "matches" in document
            else [
                {"card_id": card_id, "transcript_id": transcript_id}
                for card_id, transcript_id in document.items()
            ]
        )
    except Exception as error:
        rows = []
        reason = f"invalid solution: {error}"
    else:
        reason = "ok"
    predictions = {}
    used_transcripts = set()
    invalid_rows = 0
    for row in rows:
        if (
            not isinstance(row, dict)
            or row.get("card_id") not in answer
            or not isinstance(row.get("transcript_id"), str)
            or row["card_id"] in predictions
            or row["transcript_id"] in used_transcripts
        ):
            invalid_rows += 1
            continue
        predictions[row["card_id"]] = row["transcript_id"]
        used_transcripts.add(row["transcript_id"])
    correct = sum(
        predictions.get(card_id) == transcript_id
        for card_id, transcript_id in answer.items()
    )
    result = {
        "accuracy": round(correct / len(answer), 6),
        "correct": correct,
        "total": len(answer),
        "predicted_rows": len(rows),
        "valid_unique_rows": len(predictions),
        "invalid_rows": invalid_rows,
        "reason": reason,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
