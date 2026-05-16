#!/usr/bin/env python3
"""Generate `exp-disfluency-interview-4-task01`.

Source: an internship interview clip. The 30 s clip 2:13-2:43 of the
source contains TWO visible "emm/umm" filler tokens — both are held
non-content sounds that whisper-timestamped (base.en) misreads as
adjacent content words ("public." instead of "umm" near 5.2 s,
extends "extra" through the held vowel near 22.5-23.3 s).

Per user: any other small pauses in this clip are organized interview
pace, NOT disfluencies. The GT has exactly 2 filler-type cuts, no
pause-type entries.

Because faster-whisper (the judge model) does not emit "um"/"em" tokens
for either filler region, the standard judge-view filter would drop
both picks. We side-step that by poisoning the `_judge_view` import so
`_cut_task_core` falls back to the no-filter / wt_result path. The
judge then earns full credit via the duration-based fallback when the
agent removes the cut windows.

YouTube source: https://www.youtube.com/watch?v=v3g-t5SSmhM
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Block _judge_view so build_cut_task uses the no-filter path. Both
# fillers in this clip are held vowels that faster-whisper (tiny.en)
# does not emit as "um" tokens, so the judge-view position filter would
# otherwise drop our picks.
sys.modules["_judge_view"] = None  # type: ignore[assignment]

from _cut_task_core import build_cut_task, SOURCES_DIR  # noqa: E402


# Hand-picked windows in clip-relative seconds.
# Filler 1 ~ source 2:19 (= clip 6 s). Whisper-timestamped (base.en)
# misreads it as a low-confidence "public." at 5.04-5.22, then ~0.8 s
# of silence/hum before "I first got interested..." resumes at 6.06.
# We cut [5.15, 5.95] (800 ms).
FILLER1_START_S = 5.15
FILLER1_END_S = 5.95

# Filler 2 ~ source 2:36 (= clip 23 s). The speaker holds the vowel at
# the end of "extra" then resets into "technical". Whisper-timestamped
# (base.en) marks 22.50-23.34 with a `[*]` disfluency token; tiny.en
# extends the word "extra" through the same region. We cut
# [22.55, 23.25] (700 ms) to remove the umm without clipping
# "technical".
FILLER2_START_S = 22.55
FILLER2_END_S = 23.25


def filler_picker(_wt_result):
    return [
        {
            "start_s": FILLER1_START_S,
            "end_s": FILLER1_END_S,
            "forbidden_tokens": ["um"],
            "reason": "filler 'um/emm'",
        },
        {
            "start_s": FILLER2_START_S,
            "end_s": FILLER2_END_S,
            "forbidden_tokens": ["um"],
            "reason": "filler 'um/emm'",
        },
    ]


def main():
    build_cut_task(
        task_name="exp-disfluency-interview-4-task01",
        source_mp4=SOURCES_DIR / "22-disfluency-interview-4-v3g-t5ssmhm.mp4",
        clip_start_s=133.0,
        clip_duration_s=30.0,
        kind="disfluency",
        category="video-disfluency-cut",
        tags=["disfluency", "video-cut", "whisper", "interview",
              "stuck-um", "experiment"],
        filler_window_picker=filler_picker,
        model_size="base.en",
        # Loose tier: 2 held-vowel fillers; tiny.en boundaries jitter ~150ms.
        tolerance_each_side_s=0.20,
    )


if __name__ == "__main__":
    main()
