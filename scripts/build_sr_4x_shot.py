#!/usr/bin/env python3
"""Build exp-sr-4x-shot-task01: shot-scoped 4× super-resolution.

Source: 27-sr-4x-wrights-law.mp4 (1280x720 @ 23.976 fps, documentary).
60s clip starting at 60s — the classroom segment with chalkboards,
posters, science-experiment apparatus and student close-ups. The
posters and chalk text are exactly the kind of high-frequency detail
that disintegrates under 4× bicubic downsampling. Target shot
auto-picked.
"""
from __future__ import annotations

from pathlib import Path

from _sr_shot_core import SOURCES_DIR, SrShotSpec, build_task


def main():
    spec = SrShotSpec(
        task_name="exp-sr-4x-shot-task01",
        source_mp4=SOURCES_DIR / "27-sr-4x-wrights-law.mp4",
        factor=4,
        clip_start_sec=60.0,
        clip_duration_sec=60.0,
        prompt=(
            "One shot in this documentary-style classroom video has been "
            "downsampled 4× and re-upsampled, destroying the fine detail "
            "(chalkboard writing, poster text, faces) that distinguishes "
            "it from the surrounding shots. Identify the corrupted shot "
            "and restore its sharpness; leave the other shots untouched."
        ),
    )
    summary = build_task(spec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
