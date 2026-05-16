#!/usr/bin/env python3
"""Generate experiment/tasks/exp-glitch-dup-short-task01/.

Injects 2 random 17-frame freeze stutters (seed 42) into a ~58.74 s 480p
clip of the F1 2024 British GP highlights source. Each stutter holds one
frame for 17 extra output positions (~340 ms at 50 fps). Non-round clip
duration and dup_len are deliberate: they prevent the agent from
back-calculating the cut size by comparing "exactly 60 s − exactly 20
frames" against the produced output length.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a script: `python scripts/build_glitch_dup_short.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _glitch_dup_core import SOURCES_DIR, build_task  # noqa: E402


TASK_NAME = "exp-glitch-dup-short-task01"
SOURCE = SOURCES_DIR / "10-glitch-dup-short-f1-british-gp.mp4"
DUP_LEN = 17  # non-round to avoid leaking "exactly 20 frames"
CLIP_DURATION_SEC = 58.74  # non-round; ~ but not = 60 s


def main() -> int:
    if not SOURCE.exists():
        print(f"missing source: {SOURCE}", file=sys.stderr)
        return 1
    build_task(
        task_name=TASK_NAME,
        source_mp4=SOURCE,
        dup_len=DUP_LEN,
        clip_duration_sec=CLIP_DURATION_SEC,
        # Loose tier: agent must find a 17-frame freeze (~340ms @ 50fps).
        tolerance_each_side_s=0.20,
        # Default ssim_threshold (0.95) — see scripts/_glitch_dup_core.py.
        # Earlier we ran with 0.85 because the verifier's half-open-interval
        # bug made oracle SSIM crater on high-motion F1 content; that bug is
        # fixed in scripts/_cut_verifier_core.py:_parse_ranges (half-frame
        # end_s nudge), and oracle now achieves SSIM ≈ 0.99 on the rejudge.
        # Short freeze: tile the audio of the last video frame across the
        # freeze. Cheap and continuous-sounding.
        audio_fill_mode="loop_one_video_frame",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
