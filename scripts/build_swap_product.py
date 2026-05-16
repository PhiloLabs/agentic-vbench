#!/usr/bin/env python3
"""Build exp-swap-product-task01.

Source: 19-swap-product-lg-soundbars.mp4 (24000/1001 fps LG CES showcase).
Clip 75s from offset 5s to land in the multi-product showcase section
with clear discrete shots of distinct soundbar models / angles.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _swap_shot_core import SOURCES_DIR, build_task  # noqa: E402


def main():
    src = SOURCES_DIR / "19-swap-product-lg-soundbars.mp4"
    if not src.exists():
        raise SystemExit(f"missing source: {src}")
    build_task(
        task_name="exp-swap-product-task01",
        source_mp4=src,
        clip_offset_sec=5.0,
        clip_duration_sec=75.0,
        target_fps_rational="24000/1001",
        instruction_hint=(
            "Source is an LG CES soundbar showcase; shots cycle between "
            "distinct product hero shots, lifestyle inserts, and feature "
            "callouts. The two swapped shots are visually distinct from "
            "each other (different product / angle / lighting)."
        ),
    )


if __name__ == "__main__":
    main()
