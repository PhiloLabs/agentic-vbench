#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = Path(__file__).resolve().parent / "source"
RECORDINGS = {
    "05_assy_0_1": "A",
    "05_assy_2_2": "B",
    "05_main_0_1": "C",
    "14_assy_0_1": "D",
    "14_main_0_1": "E",
    "14_main_2_2": "F",
    "14_main_2_3": "G",
}
STEP_NAMES = {
    0: "Install base",
    1: "Incorrectly installed base",
    2: "Remove base",
    3: "Install front chassis",
    4: "Incorrectly installed front chassis",
    5: "Remove front chassis",
    6: "Install front chassis pin",
    7: "Incorrectly installed front chassis pin",
    8: "Remove front chassis pin",
    9: "Install rear chassis",
    10: "Incorrectly installed rear chassis",
    11: "Remove rear chassis",
    12: "Install short rear chassis",
    13: "Incorrectly installed short rear chassis",
    14: "Remove short rear chassis",
    15: "Install front rear chassis pin",
    16: "Incorrectly installed front rear chassis pin",
    17: "Remove front rear chassis pin",
    18: "Install rear rear chassis pin",
    19: "Incorrectly installed rear rear chassis pin",
    20: "Remove rear rear chassis pin",
    21: "Install front bracket",
    22: "Incorrectly installed front bracket",
    23: "Remove front bracket",
    24: "Install front bracket screw",
    25: "Incorrectly installed front bracket screw",
    26: "Remove front bracket screw",
    27: "Install front wheel assy",
    28: "Incorrectly installed front wheel assy",
    29: "Remove front wheel assy",
    30: "Install rear wheel assy",
    31: "Incorrectly installed rear wheel assy",
    32: "Remove rear wheel assy",
}


def _frame_number(filename: str) -> int:
    path = Path(filename)
    if path.suffix != ".jpg" or not path.stem.isdigit():
        raise ValueError(f"invalid frame filename: {filename}")
    return int(path.stem)


def _transitions(rows: list[list[str]]) -> tuple[list[dict], list[tuple[str, int]]]:
    if not rows:
        raise ValueError("empty raw state table")
    previous_frame = -1
    for row in rows:
        if len(row) != 12:
            raise ValueError(f"raw row has {len(row)} fields, expected 12: {row}")
        frame = _frame_number(row[0])
        if frame <= previous_frame:
            raise ValueError(f"raw frames are not strictly increasing at {row[0]}")
        previous_frame = frame
        states = [int(value) for value in row[1:]]
        if any(state not in {-1, 0, 1} for state in states):
            raise ValueError(f"invalid state value at {row[0]}")

    checkpoints = []
    published_events = []
    for previous, current in zip(rows, rows[1:]):
        frame = current[0]
        before = [int(value) for value in previous[1:]]
        after = [int(value) for value in current[1:]]
        assert len(before) == len(after) == 11
        changes = []
        for state_index, (old, new) in enumerate(zip(before, after)):
            if old == new:
                continue
            if new == -1:
                step_id = state_index * 3 + 1
            elif new == 1:
                step_id = state_index * 3
            elif new == 0 and old in {-1, 1}:
                step_id = state_index * 3 + 2
            else:
                raise ValueError(f"unsupported transition {old}->{new} at {frame}")
            changes.append(step_id)
            if (old, new) != (-1, 0):
                published_events.append((frame, step_id))
        assert changes, f"state row without a transition at {frame}"
        checkpoints.append({
            "frame": frame,
            "changes": changes,
            "state_after": after,
        })
    return checkpoints, published_events


def build() -> dict:
    answer = []
    for source_name, public_name in RECORDINGS.items():
        with (SOURCE_DIR / f"{source_name}.raw.csv").open(newline="") as handle:
            raw_rows = list(csv.reader(handle))
        checkpoints, derived_published = _transitions(raw_rows)
        with (SOURCE_DIR / f"{source_name}.events.csv").open(newline="") as handle:
            published_rows = list(csv.reader(handle))
        if any(len(row) != 3 for row in published_rows):
            raise ValueError(f"malformed published event row for {source_name}")
        published_frames = [_frame_number(row[0]) for row in published_rows]
        if published_frames != sorted(published_frames):
            raise ValueError(f"published events are out of order for {source_name}")
        published = [(row[0], int(row[1])) for row in published_rows]
        assert derived_published == published, f"raw states and event labels disagree for {source_name}"
        for frame, step_id, description in published_rows:
            step_id = int(step_id)
            assert STEP_NAMES[step_id] == description
        for checkpoint in checkpoints:
            frame = checkpoint["frame"]
            answer.append({
                "video": public_name,
                "time_s": int(Path(frame).stem) / 10.0,
                "changes": checkpoint["changes"],
                "state_after": checkpoint["state_after"],
            })
    assert len(answer) == 47
    return {"checkpoints": answer}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    answer = build()
    payload = json.dumps(answer, indent=2) + "\n"
    targets = [
        TASK_DIR / "steps/solve/tests/ground_truth.json",
        TASK_DIR / "steps/solve/solution/ground_truth.json",
    ]
    if args.check:
        for target in targets:
            assert target.read_text() == payload, f"stale generated file: {target}"
        print("ground truth is current and source-consistent")
        return
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload)
    print(f"wrote {len(answer['checkpoints'])} checkpoints to {len(targets)} generated files")


if __name__ == "__main__":
    main()
