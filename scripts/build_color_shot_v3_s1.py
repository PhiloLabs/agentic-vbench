#!/usr/bin/env python3
"""Build experiment/tasks/exp-color-shot-v3-s1-task01/.

CDL-based color-restoration task imported from review.html task71 / cell
v3/s1 / subtask "v3_cold_desat". The 216 s v3_source clip has had a
cold-desaturated colour shift applied to 152.12-156.96s (the target
scene at frames 3803-3924 of the 25 fps clip). The agent must remove
the bad grade and restore the original look.

Grade params (from ground_truth/v3/s1/profile.json):
    saturation = 0.78   (drop ~22%)
    contrast   = 1.13   (+13%)
    R × 0.91, G × 0.98, B × 1.09   (push cyan/blue, kill warmth)

Source: v3_source.mp4 (216.494 s, 25 fps, 960×720, has audio).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _color_restore_core import (  # noqa: E402
    SOURCES_DIR, ColorRestoreTaskSpec, build_task,
)

TASK_NAME = "exp-color-shot-v3-s1-task01"
SOURCE = SOURCES_DIR / "26-color-restore-v3-s1-cold-desat.mp4"


def main() -> int:
    if not SOURCE.exists():
        print(f"missing source: {SOURCE}", file=sys.stderr)
        return 1
    spec = ColorRestoreTaskSpec(
        task_name=TASK_NAME,
        source_mp4=SOURCE,
        # Full 216 s clip (user explicitly asked for the whole source).
        clip_start_sec=0.0,
        clip_duration_sec=216.0,
        fps=25,
        # Injection range from ground_truth/v3/s1/profile.json.
        grade_window_sec=(152.12, 156.96),
        grade_hint=(
            "a cold-desaturated colour shift — saturation dropped, "
            "contrast bumped, faintly cyan/blue cast (the warmth lifted) "
            "— has been applied to one short stretch of frames inside "
            "this clip. Every other frame is in its original colour"
        ),
        grade_cdl={
            "saturation": 0.78,
            "contrast":   1.13,
            "rr":         0.91,
            "gg":         0.98,
            "bb":         1.09,
        },
        tags=["color-restore", "cdl", "cold-desat", "v3-source",
              "video-color", "video-restoration", "windowed"],
    )
    build_task(spec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
