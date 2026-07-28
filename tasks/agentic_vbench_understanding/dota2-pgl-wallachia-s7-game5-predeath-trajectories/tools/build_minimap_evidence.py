#!/usr/bin/env python3
"""Build the reviewer-facing 720p minimap calibration crops."""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


TASK_ROOT = Path(__file__).resolve().parents[1]
POSITIONS_PATH = TASK_ROOT / "tools" / "replay_positions.json"
BUILDER_PATH = TASK_ROOT / "tools" / "build_ground_truth.py"
DEFAULT_OUTPUT = TASK_ROOT / "calibration" / "minimap-evidence"
MINIMAP_CROP = "crop=182:182:6:537"
SCALE = 4

CASES = (
    {
        "slug": "m1cke-05-26",
        "victim": "m1CKe",
        "clock_s": 326,
        "video_s": (369.7, 374.7, 379.7),
    },
    {
        "slug": "nisha-44-56",
        "victim": "Nisha",
        "clock_s": 2696,
        "video_s": (2742.7, 2747.7, 2752.4),
    },
)
POSITION_KEYS = ("minus_10s", "minus_5s", "death")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def load_builder() -> Any:
    spec = importlib.util.spec_from_file_location("dota_gt_builder", BUILDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {BUILDER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def icon_pixel(raw_x: float, raw_y: float) -> tuple[float, float]:
    x = (raw_x - 64.0) / 127.0 * 182.0
    y = (1.0 - (raw_y - 64.0) / 127.0) * 182.0
    return x, y


def cell_box(cell: str) -> tuple[int, int]:
    column = ord(cell[0]) - ord("A")
    row = int(cell[1:])
    return column * 13 * SCALE, (14 - row) * 13 * SCALE


def main() -> None:
    args = parse_args()
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required")
    positions = json.loads(POSITIONS_PATH.read_text(encoding="utf-8"))["events"]
    by_key = {(event["victim"], event["time"]): event for event in positions}
    builder = load_builder()
    args.output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="dota-minimap-evidence-") as directory:
        temporary = Path(directory)
        for case in CASES:
            event = by_key[(case["victim"], case["clock_s"])]
            raw_frames = []
            grid_frames = []
            for index, (position_key, video_s) in enumerate(
                zip(POSITION_KEYS, case["video_s"], strict=True)
            ):
                position = event["positions"][position_key]
                raw_x = float(position["raw_x"])
                raw_y = float(position["raw_y"])
                cell = builder.grid_cell(raw_x, raw_y)
                center_x, center_y = icon_pixel(raw_x, raw_y)
                cell_x, cell_y = cell_box(cell)
                raw_path = temporary / f"{case['slug']}-{index}-raw.png"
                grid_path = temporary / f"{case['slug']}-{index}-grid.png"
                run(
                    [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-y",
                        "-ss",
                        str(video_s),
                        "-i",
                        str(args.input),
                        "-frames:v",
                        "1",
                        "-vf",
                        MINIMAP_CROP,
                        str(raw_path),
                    ]
                )
                marker_x = round(center_x * SCALE - 13)
                marker_y = round(center_y * SCALE - 13)
                filters = (
                    f"scale=728:728:flags=neighbor,"
                    f"drawgrid=width=52:height=52:thickness=1:color=yellow@0.70,"
                    f"drawbox=x={cell_x}:y={cell_y}:w=52:h=52:"
                    "color=white@0.95:t=3,"
                    f"drawbox=x={marker_x}:y={marker_y}:w=26:h=26:"
                    "color=magenta@0.95:t=4"
                )
                run(
                    [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-y",
                        "-i",
                        str(raw_path),
                        "-vf",
                        filters,
                        str(grid_path),
                    ]
                )
                raw_frames.append(raw_path)
                grid_frames.append(grid_path)

            for label, frames in (("source", raw_frames), ("grid", grid_frames)):
                run(
                    [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-y",
                        *sum((["-i", str(frame)] for frame in frames), []),
                        "-filter_complex",
                        "[0:v][1:v][2:v]hstack=inputs=3",
                        str(args.output / f"{case['slug']}-{label}.png"),
                    ]
                )


if __name__ == "__main__":
    main()
