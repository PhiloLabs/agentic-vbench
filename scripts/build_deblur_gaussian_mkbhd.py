#!/usr/bin/env python3
"""Generate experiment/tasks/exp-deblur-gaussian-mkbhd-task01/.

Mask-region Gaussian deblur. 30 s 480p/30fps clip from the Wayne's World
"I Will Not Bow to Any Sponsor" Movieclip. The host holds branded
products (Pizza Hut box, Doritos bag, Reebok shirt/shoes, pill bottle)
centered in frame — perfect for a center bbox where sharp packaging
text/logos become Gaussian-blurred. Inside the bbox each frame is
convolved with a 15x15 Gaussian (sigma=3); agent must deblur the masked
region.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _mask_region_core import (  # noqa: E402
    SOURCES_DIR, TaskSpec, build_task, gaussian_blur_corrupt,
)

TASK_NAME = "exp-deblur-gaussian-mkbhd-task01"
SOURCE = SOURCES_DIR / "24-deblur-gaussian-waynes-world.mp4"
# 5-35s window: Pizza Hut box → host close-ups → Doritos bag (varied
# product close-ups, each centered in frame).
CLIP_START_SEC = 5.0
BBOX_NORM = (0.3, 0.25, 0.4, 0.5)
# Time-limited: blur burst from 10s to 20s of the 30s clip (10 s of
# corrupted frames inside the bbox; 20 s of clean frames the agent
# must preserve untouched).
CORRUPTION_WINDOW_SEC = (12.47, 21.94)  # non-round to avoid integer leak
KSIZE = 15
SIGMA = 3.0


INSTRUCTION_MD = """\
# Sharpen A Blurry Patch

I have a short clip where a certain area of the picture goes blurry for
a stretch of the clip — it's like there's a soft spot on
the lens that only shows up in some frames. Everything outside that
area, and everything outside that stretch, looks clean.

Please find when and where the blur happens and bring that area back
into focus, matching the sharpness of the rest of the picture. Don't
touch the rest of the frame, and don't touch the parts of the clip that
are already sharp.

## What to deliver

- `/workspace/output/output.mp4` — H.264 / yuv420p, same dimensions,
  frame rate, and number of frames as the input. Video-only is fine.

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
        tags=["gaussian-blur", "deblur", "mask-region", "time-windowed",
              "video-restoration"],
        corruption_desc=(
            f"per-frame cv2.GaussianBlur ksize={KSIZE}, sigma={SIGMA} inside "
            f"bbox {BBOX_NORM}, window {CORRUPTION_WINDOW_SEC[0]}s-"
            f"{CORRUPTION_WINDOW_SEC[1]}s"
        ),
        instruction_md=INSTRUCTION_MD,
        corrupt_fn=gaussian_blur_corrupt(KSIZE, SIGMA),
        corruption_window_sec=CORRUPTION_WINDOW_SEC,
    )
    build_task(spec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
