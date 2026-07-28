#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_ground_truth import (
    MINIMUM_DURATION_S,
    clock_seconds,
    parse_pdf,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--boundary-audit", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    records = parse_pdf(args.pdf)
    selected = [
        (record_index, record)
        for record_index, record in enumerate(records)
        if record.role != "Vice-President"
        and clock_seconds(record.duration) >= MINIMUM_DURATION_S
    ]
    boundary_rows = {
        row["turn_index"]: row
        for row in json.loads(args.boundary_audit.read_text())["turns"]
    }
    overlaps = []
    for turn_index, (record_index, record) in enumerate(selected, start=1):
        if record_index + 1 >= len(records):
            continue
        following = records[record_index + 1]
        overlap = clock_seconds(record.end) - clock_seconds(following.start)
        if overlap <= 0:
            continue
        overlaps.append(
            {
                "turn_index": turn_index,
                "official_record_index": record_index + 1,
                "following_role": following.role,
                "following_record_starts_before_scored_end_s": overlap,
                "nearest_end_audio_transition_error_s": abs(
                    boundary_rows[turn_index]["end_transition_error_s"]
                ),
            }
        )

    result = {
        "definition": (
            "Scored boundaries are the official intervention intervals. They "
            "may include overlapping chair or room audio and are not defined "
            "as voice-activity-only crops."
        ),
        "official_records": len(records),
        "scored_turns": len(selected),
        "scored_turns_with_any_following_record_overlap": len(overlaps),
        "scored_turns_with_overlap_over_tolerance": sum(
            row["following_record_starts_before_scored_end_s"] > 3.5
            for row in overlaps
        ),
        "maximum_end_audio_transition_error_for_overlaps_s": max(
            row["nearest_end_audio_transition_error_s"] for row in overlaps
        ),
        "maximum_end_audio_transition_error_for_over_tolerance_overlaps_s": max(
            row["nearest_end_audio_transition_error_s"]
            for row in overlaps
            if row["following_record_starts_before_scored_end_s"] > 3.5
        ),
        "overlaps": overlaps,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
