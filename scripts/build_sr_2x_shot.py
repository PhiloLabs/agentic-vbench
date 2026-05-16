#!/usr/bin/env python3
"""Build exp-sr-2x-shot-task01: shot-scoped 2× super-resolution.

Source: 26-sr-2x-saving-private-ryan.mp4 (1280x720 @ 23.976 fps).
60s clip starting at 30s — the Sniper-in-the-Tower scene, which
contains many short shots packed with high-frequency texture
(rubble, helmet netting, cobblestones, foliage, weathered faces).
Target shot is auto-picked from PySceneDetect results, preferring a
sharp 100-200-frame mid-action shot.
"""
from __future__ import annotations

from pathlib import Path

from _sr_shot_core import SOURCES_DIR, SrShotSpec, build_task


def main():
    spec = SrShotSpec(
        task_name="exp-sr-2x-shot-task01",
        source_mp4=SOURCES_DIR / "26-sr-2x-saving-private-ryan.mp4",
        factor=2,
        clip_start_sec=30.0,
        clip_duration_sec=60.0,
        prompt=(
            "One shot in this multi-shot war-film clip has been downsampled "
            "2× and re-upsampled, leaving it visibly blurrier than the "
            "surrounding shots — rubble texture, helmet netting and face "
            "detail all soften noticeably. Identify the corrupted shot and "
            "restore it to match the source quality. The remaining shots "
            "should pass through unchanged."
        ),
    )
    summary = build_task(spec)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
