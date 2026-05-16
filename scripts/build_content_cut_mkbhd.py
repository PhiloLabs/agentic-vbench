#!/usr/bin/env python3
"""Generate `exp-content-cut-mkbhd-task01`.

Source: MKBHD Pixel 9 Pro camera review, 90 s clip starting at 0 s.

Target removal: a short 5 s aside (29.0-34.0 s clip-local) where the
reviewer claims the phone can stand up by itself (the case helps it
stand up), with the qualifier "well, some of the time" -- i.e., a
misleading reliability claim that the user wants removed.
Transcript over that window: "And in the case of my ability to film
it, easier to stand up to. Well, some of the time."
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _cut_task_core import build_cut_task, SOURCES_DIR  # noqa: E402


USER_PROMPT = (
    "The video makes a claim about the phone's case helping it stand "
    "up reliably, but we've found this isn't always true. Please "
    "remove that specific segment from the video while keeping the "
    "rest of the content intact."
)


def main():
    build_cut_task(
        task_name="exp-content-cut-mkbhd-task01",
        source_mp4=SOURCES_DIR / "09-mkbhd-pixel9pro-camera.mp4",
        clip_start_s=0.0,
        clip_duration_s=90.0,
        kind="content_cut",
        category="video-content-cut",
        tags=["content-cut", "video-cut", "whisper", "experiment"],
        gt_segment_window_s=(29.0, 34.0),  # clip-local
        user_prompt=USER_PROMPT,
        model_size="base.en",
        # Precise tier: single 5s editorial cut on sentence boundary.
        tolerance_each_side_s=0.10,
    )


if __name__ == "__main__":
    main()
