#!/usr/bin/env python3
"""Generate experiment/tasks/exp-deblur-motion-f1-task01/.

Mask-region motion deblur. 30 s 480p/30fps clip from the F1 (2025)
official movie teaser trailer. The 60-90 s window of the trailer is
packed with onboard-camera POV shots (sharp track edges, kerb stripes,
helmet text, side-mirror reflections) — high-frequency horizontal
content that breaks visibly under a 15 px horizontal motion-blur
kernel. The previous source (Qatar GP race highlights) is preserved
elsewhere; this swap moves to a different SOURCE FILE (a film trailer
rather than live race footage) while keeping the motion-content type
that the corruption recipe was designed for.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _mask_region_core import (  # noqa: E402
    SOURCES_DIR, TaskSpec, build_task, motion_blur_corrupt,
)

TASK_NAME = "exp-deblur-motion-f1-task01"
SOURCE = SOURCES_DIR / "25-deblur-motion-f1-teaser.mp4"
# 60-90s window covers the onboard-cam sequence: tight helmet shots,
# track POV with sharp kerb stripes, mirror cuts. Strong horizontal
# edges (track lines, helmet text) are what horizontal motion blur
# visibly destroys.
CLIP_START_SEC = 60.0
# Full-frame corruption — no spatial mask. The challenge for the agent
# is identifying *when* the blur is happening (the in-window range) and
# leaving frames outside that range untouched.
BBOX_NORM = (0.0, 0.0, 1.0, 1.0)
# Time-limited: blur burst from 10s to 20s of the 30s clip (10 s of
# corrupted frames; 20 s of clean ones the agent must preserve).
CORRUPTION_WINDOW_SEC = (7.83, 17.36)  # non-round to avoid integer leak
MOTION_LEN = 15
MOTION_ANGLE_DEG = 0.0


INSTRUCTION_MD = """\
# Fix Motion-Blurred Frames

I have a short clip where, for a stretch in the middle, the whole
picture goes blurry — it looks like the camera lost focus or someone
shook it. Outside that stretch the picture is clean and sharp.

Please find when the blur happens and bring those frames back into focus
so the sharpness matches the rest of the clip. Leave the parts that are
already sharp alone.

## What to deliver

- `/workspace/output/output.mp4` — H.264 / yuv420p, same dimensions,
  frame rate, and number of frames as the input. Video-only is fine
  (no audio expected on this clip).

## Environment

- CPU only, ~30 min timeout. Internet available for `pip install`.
"""


def main() -> int:
    if not SOURCE.exists():
        print(f"missing source: {SOURCE}", file=sys.stderr)
        return 1
    spec = TaskSpec(
        task_name=TASK_NAME,
        source_mp4=SOURCE,
        clip_start_sec=CLIP_START_SEC,
        bbox_norm=BBOX_NORM,
        task_type="deblur",
        category="video-deblur",
        tags=["motion-blur", "deblur", "time-windowed", "video-restoration",
              "f1"],
        corruption_desc=(
            f"full-frame linear motion kernel length={MOTION_LEN}px "
            f"angle={MOTION_ANGLE_DEG}deg, window "
            f"{CORRUPTION_WINDOW_SEC[0]}s-{CORRUPTION_WINDOW_SEC[1]}s"
        ),
        instruction_md=INSTRUCTION_MD,
        corrupt_fn=motion_blur_corrupt(MOTION_LEN, MOTION_ANGLE_DEG),
        corruption_window_sec=CORRUPTION_WINDOW_SEC,
    )
    build_task(spec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
