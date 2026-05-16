#!/usr/bin/env python3
"""Generate `exp-content-cut-wsj-task01`.

Source: WSJ China shipbuilding explainer, 90 s clip starting at 60 s.
Per the clean transcript:
  - 0–~50 s in clip: China shipbuilding capacity, $100B injected, 370+ ships.
  - ~55–~67 s in clip: "The US has more active aircraft carriers too, 11
    compared to China's two. This means the US Navy can more easily
    project power in multiple areas and launch attacks over vast
    distances."
  - ~67–90 s in clip: back to China catching up, satellite imagery.

Target removal: the aircraft-carrier comparison segment (clip-time
55-67s) — a single semantically-clear claim about US active aircraft
carriers.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _cut_task_core import (  # noqa: E402
    SOURCES_DIR,
    TASKS_DIR,
    _STOPWORDS,
    build_cut_task,
)


USER_PROMPT = (
    "The video contains an incorrect statistic about the US having more "
    "active aircraft carriers. Please remove that specific segment from "
    "the video while keeping the rest of the content intact."
)


TASK_NAME = "exp-content-cut-wsj-task01"
GT_WINDOW = (55.0, 67.0)


def _filter_keywords_to_window_unique() -> None:
    """Tighten GT keywords to ones that occur only INSIDE the cut window.

    The clip discusses overlapping topics on both sides of the cut, so
    many keywords from the GT window also occur naturally in the kept
    content (e.g., "navy", "carriers", "aircraft"). The default
    extractor's distinctiveness threshold (`out_n <= max(2, 2*n)`)
    keeps those; the judge then sees them in the agent's transcript
    after a clean cut and counts them as "survived". Filter to
    keywords with out_n == 0 so a perfect cut scores 1.0.
    """
    cuts_path = TASKS_DIR / TASK_NAME / "steps" / "solve" / "tests" / "cuts.json"
    clip_path = (TASKS_DIR / TASK_NAME / "steps" / "solve"
                 / "workdir" / "source.mp4")
    data = json.loads(cuts_path.read_text())

    import whisper_timestamped as wt
    audio = wt.load_audio(str(clip_path))
    model = wt.load_model("base.en", device="cpu")
    res = wt.transcribe(model, audio, detect_disfluencies=True,
                        language="en", vad=False)

    start_s, end_s = GT_WINDOW
    outside = Counter()
    for seg in res.get("segments", []):
        for w in seg.get("words", []):
            ws, we = float(w["start"]), float(w["end"])
            t = re.sub(r"[^a-zA-Z']", "", w["text"]).lower()
            if not t or len(t) < 4 or t in _STOPWORDS:
                continue
            # outside if no overlap with window
            if we < start_s or ws > end_s:
                outside[t] += 1

    cut = data["cuts"][0]
    keep = [kw for kw in cut["forbidden_keywords"] if outside.get(kw, 0) == 0]
    print(f"keyword filter: kept {len(keep)} / {len(cut['forbidden_keywords'])} "
          f"window-unique keywords")
    print(f"  kept: {keep}")
    dropped = [kw for kw in cut["forbidden_keywords"] if outside.get(kw, 0) > 0]
    print(f"  dropped (also appear outside cut): {dropped}")
    cut["forbidden_keywords"] = keep
    cuts_path.write_text(json.dumps(data, indent=2))


def main():
    build_cut_task(
        task_name=TASK_NAME,
        source_mp4=SOURCES_DIR / "08-content-cut-wsj-china-shipbuilding.mp4",
        clip_start_s=60.0,
        clip_duration_s=90.0,
        kind="content_cut",
        category="video-content-cut",
        tags=["content-cut", "video-cut", "whisper", "experiment"],
        gt_segment_window_s=GT_WINDOW,  # in clip-local time
        user_prompt=USER_PROMPT,
        model_size="base.en",
        # Precise tier: single editorial sentence-boundary cut.
        tolerance_each_side_s=0.10,
    )
    _filter_keywords_to_window_unique()


if __name__ == "__main__":
    main()
