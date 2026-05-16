#!/usr/bin/env python3
"""Build exp-swap-car-task01.

Source: 18-swap-car-lambo-ferrari-porsche.mp4 (25 fps drag-race montage).
Clip 60s starting at offset 60s (skips the opening title sequence and
slow build-up) to land in the meaty fast-cut section with distinct car
shots.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _swap_shot_core import SOURCES_DIR, build_task  # noqa: E402


def main():
    src = SOURCES_DIR / "18-swap-car-lambo-ferrari-porsche.mp4"
    if not src.exists():
        raise SystemExit(f"missing source: {src}")
    build_task(
        task_name="exp-swap-car-task01",
        source_mp4=src,
        clip_offset_sec=60.0,
        clip_duration_sec=60.0,
        target_fps_rational="25/1",
        instruction_hint=(
            "Source is a multi-car drag-race montage; shots intercut "
            "between distinct vehicles. The two swapped shots feature "
            "different cars and/or angles."
        ),
    )


if __name__ == "__main__":
    main()
