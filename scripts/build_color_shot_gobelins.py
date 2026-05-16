#!/usr/bin/env python3
"""Build experiment/tasks/exp-color-shot-gobelins-task01/.

Flipped color-restoration variant: the agent receives the GOBELINS
"DARE TO BE FABULOUS" short clip whose nightclub-singer beat has been
graded with the CINEMA_NOIR.cube LUT (FreshLUTs, CC0 — a full-desat
black-and-white noir look). The agent must remove the B&W grade and
restore the original colour Rec.709 look.

Source clip: 100-160s of the full short (60 s window) at 25 fps.
Graded sub-range: clip-relative 36.748s → 54.920s = clip frames
919-1373 = the entire spotlit-singer-plus-handkiss beat.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _color_restore_core import (  # noqa: E402
    SOURCES_DIR, ColorRestoreTaskSpec, build_task,
)

FULL_GOBELINS = Path(
    "/Users/zonghengcao/Downloads/vlm_benchmark/videos/07_animation/"
    "DARE_TO_BE_FABULOUS_-_Animation_Short_Film_2024_-_GOBELINS_"
    "23Mz2j2VQtw.mp4")
TASK_NAME = "exp-color-shot-gobelins-task01"
GRADE_LUT = SOURCES_DIR / "luts" / "CINEMA_NOIR.cube"


def main() -> int:
    if not FULL_GOBELINS.exists():
        print(f"missing source: {FULL_GOBELINS}", file=sys.stderr)
        return 1
    if not GRADE_LUT.exists():
        print(f"missing LUT: {GRADE_LUT}", file=sys.stderr)
        return 1
    # 60 s clip at 25 fps starting at 100s of full short. Grade window
    # is clip frames 919-1373 → 36.748s → 54.920s in clip time.
    spec = ColorRestoreTaskSpec(
        task_name=TASK_NAME,
        source_mp4=FULL_GOBELINS,
        clip_start_sec=100.0,
        clip_duration_sec=60.0,
        fps=25,
        grade_window_sec=(919 / 25, 1373 / 25),  # 36.76s → 54.92s
        grade_hint=(
            "a hard black-and-white film-noir grade has been mistakenly "
            "applied to one sequence of shots (a spotlit-nightclub-"
            "singer beat) inside this otherwise colour-graded short. "
            "All other shots stay in their original colour"
        ),
        grade_lut_path=GRADE_LUT,
        tags=["color-restore", "lut", "gobelins", "video-color",
              "video-restoration", "windowed"],
    )
    build_task(spec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
