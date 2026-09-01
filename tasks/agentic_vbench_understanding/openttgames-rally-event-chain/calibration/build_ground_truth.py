#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


FPS = 120.0

ENDING_SUFFIXES = (
    "_out",
    "_winner",
    "_double_bounce",
    "_not_hitting_ball",
    "_miss_on_own_side",
)

SOURCE_VIDEO_GAP_TRUNCATIONS = {
    # One serve-defined window spans two distinct points: the scoreboard moves
    # from 4:3 to 4:4 inside the gap that follows the first point. The second
    # point's serve is visible in the video but its racket-ball contact frame is
    # not resolvable, so that point is excluded rather than given an inferred
    # serve. Only the fully annotated first point is kept, terminated at the
    # frame where the net arrests the ball's forward motion, per the net anchor
    # rule in steps/solve/instruction.md. See calibration/source-exception-audit.md.
    8: {
        "keep_through_frame": 12325,
        "ending_frame": 12325,
        "ending": "left_net",
    },
}

SOURCE_TERMINAL_EXCEPTIONS = {
    # These six serve-defined windows contain live play in the video but
    # have no terminal label in the pinned source annotation. The terminal
    # events below were filled by a bounded video audit requested during
    # benchmark review. All other event-chain labels remain source-derived.
    13: {
        "frame": 23710,
        "ending": "left_winner",
    },
    16: {
        "frame": 26492,
        "ending": "right_winner",
    },
    18: {
        "frame": 28780,
        "ending": "left_net",
    },
    24: {
        "frame": 39864,
        "ending": "right_net",
    },
    55: {
        "frame": 92752,
        "ending": "right_net",
    },
    73: {
        "frame": 127124,
        "ending": "left_winner",
    },
}


STROKE_TYPES = (
    "_serve",
    "_loop",
    "_block",
    "_push",
    "_flick",
    "_lob",
    "_smash",
    "_chop",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def frame_to_time(frame: int) -> float:
    return round(frame / FPS, 3)


def is_stroke(label: str) -> bool:
    first = label.split()[0]
    return any(x in first for x in STROKE_TYPES)


def is_serve(label: str) -> bool:
    return is_stroke(label) and "_serve" in label.split()[0]


def is_ending(label: str) -> bool:
    if label in ("left_net", "right_net"):
        return True
    return any(label.endswith(x) for x in ENDING_SUFFIXES)


def parse_stroke(frame: int, label: str) -> dict:
    first = label.split()[0]
    parts = first.split("_")

    player = parts[0]
    hand = parts[1]
    stroke = "_".join(parts[2:])

    return {
        "frame": frame,
        "time_sec": frame_to_time(frame),
        "player": player,
        "hand": hand,
        "stroke": stroke,
    }


def dedup_endings(
    endings: list[tuple[int, str]],
    max_gap: int = 2,
) -> list[tuple[int, str]]:
    if not endings:
        return []

    result = [endings[0]]

    for frame, label in endings[1:]:
        prev_frame, prev_label = result[-1]

        if label == prev_label and frame - prev_frame <= max_gap:
            continue

        result.append((frame, label))

    return result


def build_reference(input_path: Path) -> tuple[dict, dict]:
    with input_path.open() as f:
        raw = json.load(f)

    data = {int(k): v for k, v in raw.items()}
    events = sorted(data.items())

    serves = [(f, l) for f, l in events if is_serve(l)]

    valid = []
    excluded = []

    for i, (serve_frame, _) in enumerate(serves):
        next_serve = (
            serves[i + 1][0]
            if i + 1 < len(serves)
            else float("inf")
        )

        window = [
            (f, l)
            for f, l in events
            if serve_frame <= f < next_serve
        ]

        rally_id = i + 1
        truncation = SOURCE_VIDEO_GAP_TRUNCATIONS.get(rally_id)
        dropped = []

        if truncation:
            cut = truncation["keep_through_frame"]

            dropped = [
                parse_stroke(f, l)
                for f, l in window
                if f > cut and is_stroke(l)
            ]

            window = [(f, l) for f, l in window if f <= cut]

        strokes = [
            parse_stroke(f, l)
            for f, l in window
            if is_stroke(l)
        ]

        endings_raw = [
            (f, l)
            for f, l in window
            if is_ending(l)
        ]

        endings = dedup_endings(endings_raw)

        if truncation:
            ending_frame = truncation["ending_frame"]
            ending_label = truncation["ending"]

            if not (serve_frame <= ending_frame < next_serve):
                raise ValueError(
                    f"Truncated ending for rally {rally_id} "
                    "falls outside its serve window"
                )

            if not is_ending(ending_label):
                raise ValueError(
                    f"Unsupported truncated ending for rally {rally_id}: "
                    f"{ending_label}"
                )

            excluded.append({
                "rally_id": rally_id,
                "kind": "video-gap",
                "kept_through_frame": truncation["keep_through_frame"],
                "kept_through_time_sec": frame_to_time(
                    truncation["keep_through_frame"]
                ),
                "excluded_strokes": len(dropped),
                "excluded_from_frame": (
                    dropped[0]["frame"] if dropped else None
                ),
                "excluded_to_frame": (
                    dropped[-1]["frame"] if dropped else None
                ),
                "reason": (
                    "second point in the same serve-defined window; its serve "
                    "is visible but the racket-ball contact frame is not "
                    "resolvable in the source video"
                ),
            })

        elif len(endings) == 1:
            ending_frame, ending_label = endings[0]

        elif (
            len(endings) == 0
            and rally_id in SOURCE_TERMINAL_EXCEPTIONS
        ):
            override = SOURCE_TERMINAL_EXCEPTIONS[rally_id]
            ending_frame = override["frame"]
            ending_label = override["ending"]
            if not (serve_frame <= ending_frame < next_serve):
                raise ValueError(
                    f"Audited ending for rally {rally_id} "
                    "falls outside its serve window"
                )

            if not is_ending(ending_label):
                raise ValueError(
                    f"Unsupported audited ending for rally {rally_id}: "
                    f"{ending_label}"
                )

        else:
            excluded.append({
                "rally_id": rally_id,
                "serve_frame": serve_frame,
                "serve_time_sec": frame_to_time(serve_frame),
                "reason": f"{len(endings)} endings after dedup",
                "raw_endings": endings_raw,
            })
            continue

        valid.append({
            "rally_id": rally_id,
            "serve_frame": serve_frame,
            "serve_time_sec": frame_to_time(serve_frame),
            "server": strokes[0]["player"],
            "strokes": strokes,
            "ending_frame": ending_frame,
            "ending_time_sec": frame_to_time(ending_frame),
            "ending": ending_label,
        })

    reference = {
        "source": "Extended OpenTTGames annotations",
        "video": {
            "filename": "game_2.mp4",
            "fps": FPS,
            "width": 1920,
            "height": 1080,
            "duration_sec": 1435.0,
            "frame_count": 172200,
        },
        "valid_rallies": len(valid),
        "excluded_rallies": len(excluded),
        "rallies": valid,
        "excluded": excluded,
    }

    audit = {
        "annotation_sha256": sha256_file(input_path),
        "total_annotation_events": len(events),
        "total_serves": len(serves),
        "valid_rallies": len(valid),
        "excluded_rallies": len(excluded),
        "excluded_rally_ids": [
            item["rally_id"] for item in excluded
        ],
        "video_gap_truncation_ids": sorted(
            SOURCE_VIDEO_GAP_TRUNCATIONS
        ),
        "video_gap_truncations": {
            str(rally_id): {
                **value,
                "keep_through_time_sec": frame_to_time(
                    value["keep_through_frame"]
                ),
                "ending_time_sec": frame_to_time(value["ending_frame"]),
            }
            for rally_id, value
            in SOURCE_VIDEO_GAP_TRUNCATIONS.items()
        },
        "video_gap_excluded_strokes": sum(
            item.get("excluded_strokes", 0)
            for item in excluded
            if item.get("kind") == "video-gap"
        ),
        "source_terminal_exception_ids": sorted(
            SOURCE_TERMINAL_EXCEPTIONS
        ),
        "source_terminal_exceptions": {
            str(rally_id): {
                **value,
                "ending_time_sec": frame_to_time(value["frame"]),
            }
            for rally_id, value
            in SOURCE_TERMINAL_EXCEPTIONS.items()
        },
        "benchmark_strokes": sum(
            len(rally["strokes"]) for rally in valid
        ),
        "dedup_rule": {
            "type": "adjacent identical ending labels",
            "max_gap_frames": 2,
        },
        "ground_truth_construction_rule": (
            "Use the single deduplicated source ending within each "
            "serve-defined rally window; for the six explicitly listed "
            "source-terminal gaps, use the bounded video-audit terminal; for "
            "the listed video-gap truncation, keep only the events up to the "
            "audited cut frame and record the remainder as excluded."
        ),
    }

    return reference, audit


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--audit",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    reference, audit = build_reference(args.input)

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.audit.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.output.write_text(
        json.dumps(reference, indent=2) + "\n"
    )

    args.audit.write_text(
        json.dumps(audit, indent=2) + "\n"
    )

    print("Wrote reference:", args.output)
    print("Wrote audit:", args.audit)


if __name__ == "__main__":
    main()
