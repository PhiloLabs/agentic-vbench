#!/usr/bin/env python3
"""Generate experiment/tasks/exp-glitch-dup-long-task01/.

Injects 2 random 27-frame freeze stutters (seed 42) into a ~62.31 s 480p
clip of the Taylor Swift Anti-Hero MV source. Each stutter holds one
frame for 27 extra output positions. Non-round clip duration and dup_len
are deliberate (see short-task script for the rationale).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _glitch_dup_core import SOURCES_DIR, build_task  # noqa: E402


TASK_NAME = "exp-glitch-dup-long-task01"
SOURCE = SOURCES_DIR / "11-glitch-dup-long-anti-hero.mp4"
DUP_LEN = 27  # non-round to avoid leaking "exactly 30 frames"
CLIP_DURATION_SEC = 62.31  # non-round; ~ but not = 60 s


def main() -> int:
    if not SOURCE.exists():
        print(f"missing source: {SOURCE}", file=sys.stderr)
        return 1
    build_task(
        task_name=TASK_NAME,
        source_mp4=SOURCE,
        dup_len=DUP_LEN,
        clip_duration_sec=CLIP_DURATION_SEC,
        # Loose tier: 27-frame freeze, longer block of held content.
        tolerance_each_side_s=0.20,
        # Long freeze (~1.12 s @ 24fps): copy the same-length audio chunk
        # from just before the freeze into the freeze span — a single
        # video frame would loop too obviously over that long a window.
        audio_fill_mode="copy_prior_window",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
