#!/usr/bin/env python3
"""Derive the three degraded-input prompts from the shipped one, and prove the derivation.

    python3 provenance/ablations/make_ablation_prompt.py --mode no_media     --out p.md
    python3 provenance/ablations/make_ablation_prompt.py --mode single_frame --out p.md
    python3 provenance/ablations/make_ablation_prompt.py --mode frame_dump   --out p.md

The family's ablation gate asks what a strong model scores when the video is taken away
and replaced by nothing, by one still, or by a fixed set of frames with no tools to ask
for more. Those runs are only evidence if the model was asked the same question, so the
question, the schema, the tolerance rule and the closed vocabulary are taken from
steps/solve/instruction.md rather than rewritten here. Three things change: the opening
paragraph about the media, the sentence offering tools, and the file target, since a run
with no tools has nothing to write with. The script asserts that the rest is carried over
byte for byte.
"""
from __future__ import annotations

import argparse
import re
import textwrap
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent.parent
SHIPPED = TASK / "steps" / "solve" / "instruction.md"

CLIP_SEC = "6426.5"
SINGLE_FRAME_T = 1786          # the midpoint of the first half's clip span, [350, 3223]
SHEETS, PER_SHEET = 8, 16      # 128 frames, one every ~50 s across the whole clip

# Every degraded run is forced to answer. A refusal scores 0.0 too, but a 0.0 from a model
# that declined to guess says nothing about whether the degraded input was enough, which is
# the whole question.
FORCE = (" You must still produce a complete answer in the schema below: an empty sequence "
         "is not an acceptable response, so give your best guess.")
CLIP = (f"The video is the full broadcast of one Bundesliga match as a single clip, "
        f"{CLIP_SEC} seconds long.")

MEDIA = {
    "no_media": (
        f"You are given NO video and NO images, and you have NO tools. {CLIP} Answer from "
        "what you already know." + FORCE),
    "single_frame": (
        f"You are given ONE still image from the video, taken at `t = {SINGLE_FRAME_T}`. {CLIP} "
        "You have NO video, NO tools, and no way to ask for another frame. Answer from the "
        "still alone." + FORCE),
    "frame_dump": (
        f"You are given {SHEETS} contact sheets from the video, in time order. Each sheet is a "
        f"4x4 grid of {PER_SHEET} frames read left to right and top to bottom; together they "
        f"hold {SHEETS * PER_SHEET} frames sampled at even intervals across the whole clip, "
        f"with each frame's `t` in seconds burned into its corner. {CLIP} You have NO video, "
        "NO tools, and no way to ask for another frame. Answer from the sheets alone." + FORCE),
}

TOOLS = re.compile(r"\s*Use any tools in the image \(for example `ffmpeg` and `ffprobe`\) "
                   r"to seek through and sample the video\.")
TARGET = "Write `/workspace/output/solution.json` in exactly this shape:"
PRINT = "Print the JSON object and nothing else as your final message, in exactly this shape:"


def build(mode: str) -> str:
    ship = SHIPPED.read_text()
    title_end = ship.index("\n\n") + 2                     # the "# ..." title line
    media_end = ship.index("\n\n", title_end) + 2          # the paragraph about the clip
    time_end = ship.index("\n\n", media_end) + 2           # the paragraph about t and tools
    rest = ship[time_end:]

    time_para = " ".join(ship[media_end:time_end].split())
    time_para, n = TOOLS.subn("", time_para)
    assert n == 1, "the tools sentence was not found exactly once in the shipped prompt"

    assert rest.count(TARGET) == 1, "the file target was not found exactly once"
    out = (ship[:title_end]
           + textwrap.fill(MEDIA[mode], width=88) + "\n\n"
           + textwrap.fill(time_para, width=88) + "\n\n"
           + rest.replace(TARGET, PRINT))

    # The parts that carry the question must survive verbatim.
    assert out.split(PRINT, 1)[1] == rest.split(TARGET, 1)[1], (
        "everything after the file target must be byte-identical to the shipped prompt")
    assert rest.split(TARGET, 1)[0] in out, "the section before the file target changed"
    for must in ('"sequence"', "within 1 second", "`action`", "`team`", "`Clearance`", "`Ball out of play`"):
        assert must in out, f"the ablation prompt lost {must}, so it is not the same question"
    assert not re.search(r"ffmpeg|ffprobe|/workspace/output", out), "a tool affordance survived"
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=sorted(MEDIA))
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    text = build(args.mode)
    args.out.write_text(text)
    print(f"wrote {args.out}: {len(text)} bytes, the question carried over unchanged")


if __name__ == "__main__":
    main()
