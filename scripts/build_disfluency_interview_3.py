#!/usr/bin/env python3
"""Generate `exp-disfluency-interview-3-task01`.

Source: same J.K. Rowling 1998 ITN interview as interview-2, but a
different clip and a different target.

The clip is 17.0-54.0 s of the source. Around source-time 42-44 s
(clip-relative ~25-27 s) Rowling says "Yeah in the [stuck ~1.6 s] right
after the book was published". The stuck region is mostly silence with a
brief held-vowel hum — what a human would describe as a long "um". Whisper
absorbs the silence into the start of the word "right" rather than emitting
a discrete "um" token, so we score this as a PAUSE cut: anchor on
"in the" before the gap and "after the" after it, plus a duration-credit
fallback.

YouTube source: https://www.youtube.com/watch?v=Mg3oCq_E8Os
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _cut_task_core import build_cut_task, SOURCES_DIR  # noqa: E402


# Hand-picked window covering the stuck moment (clip-relative seconds).
# Tuned from RMS energy + faster-whisper word boundaries:
#   - "Yeah in the" ends around 25.50
#   - "right" starts around 27.20
# We pad a touch on each side to bracket the held-vowel hum + silence.
STUCK_START_S = 25.55
STUCK_END_S = 27.15


def filler_picker(_wt_result):
    # No filler-word picks. Everything is in the single pause cut.
    return []


def pause_picker(_wt_result, _clip_path):
    # One hand-coded "stuck um" cut. The build core will rewrite the
    # anchor_before / anchor_after using the judge-view (faster-whisper
    # tiny.en) transcript so the judge can find them.
    return [{
        "start_s": STUCK_START_S,
        "end_s": STUCK_END_S,
        "type": "pause",
        "pause_duration_ms": int(round((STUCK_END_S - STUCK_START_S) * 1000)),
        "anchor_before": ["in", "the"],
        "anchor_after": ["after", "the"],
        "reason": "long stuck 'um' (~1.6s) between 'in the' and 'right'",
    }]


def main():
    build_cut_task(
        task_name="exp-disfluency-interview-3-task01",
        source_mp4=SOURCES_DIR / "21-disfluency-interview-2-mg3ocq_e8os.mp4",
        clip_start_s=17.0,
        clip_duration_s=37.0,
        kind="disfluency",
        category="video-disfluency-cut",
        tags=["disfluency", "video-cut", "whisper", "interview",
              "stuck-um", "experiment"],
        filler_window_picker=filler_picker,
        pause_window_picker=pause_picker,
        model_size="base.en",
        # Precise tier: single 1.6s stuck-um, frame-accurate cut expected.
        tolerance_each_side_s=0.10,
    )


if __name__ == "__main__":
    main()
