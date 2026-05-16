#!/usr/bin/env python3
"""Build experiment/tasks/exp-color-shot-visit-korea-task01/.

Flipped color-restoration variant: the agent receives a clip whose
target shot has been graded with the Bourbon 64 "Warm" creative LUT
(RocketStock 35 Free LUTs, bake-only license). The agent must remove
that warm grade and restore the original Rec.709 look. The verifier
compares the agent's output to the un-graded original with the
windowed (85% / 15%) LAB-ΔE judge.

Source clip: 90-120s of Pacific Rim Uprising "Inspirational Speech"
trailer (24 fps, two-pilot cockpit two-shot at clip frames 150-287).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _color_restore_core import (  # noqa: E402
    SOURCES_DIR, ColorRestoreTaskSpec, build_task,
)

TASK_NAME = "exp-color-shot-visit-korea-task01"
SOURCE = SOURCES_DIR / "23-color-shot-pacific-rim-uprising.mp4"
GRADE_LUT = SOURCES_DIR / "luts" / "Bourbon_64.CUBE"


def main() -> int:
    if not SOURCE.exists():
        print(f"missing source: {SOURCE}", file=sys.stderr)
        return 1
    if not GRADE_LUT.exists():
        print(f"missing LUT: {GRADE_LUT}", file=sys.stderr)
        return 1
    # 30 s clip, 24 fps, cockpit two-shot is clip frames 150-287 (6.25s
    # to 12.00s in clip-relative time, inclusive of end frame).
    spec = ColorRestoreTaskSpec(
        task_name=TASK_NAME,
        source_mp4=SOURCE,
        clip_start_sec=90.0,
        clip_duration_sec=30.0,
        fps=24,
        # Window inclusive of end frame → end_s = (287+1)/24
        grade_window_sec=(150 / 24, 288 / 24),  # 6.25s → 12.00s
        grade_hint=(
            "a warm \"blockbuster\" cinematic look — amber/peach "
            "highlights, lifted midtones, deeper shadows with a faint "
            "cool tilt — has been mistakenly applied to one shot inside "
            "this clip (a cockpit two-shot of two pilots). All other "
            "shots are unmodified"
        ),
        grade_lut_path=GRADE_LUT,
        tags=["color-restore", "lut", "pacific-rim", "video-color",
              "video-restoration", "windowed"],
    )
    build_task(spec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
