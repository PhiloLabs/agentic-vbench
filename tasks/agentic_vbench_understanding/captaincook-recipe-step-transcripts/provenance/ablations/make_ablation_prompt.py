#!/usr/bin/env python3
"""Derive the two degraded-input prompts from the shipped one, and prove the derivation.

    python3 provenance/ablations/make_ablation_prompt.py --mode single_frame --out p.md
    python3 provenance/ablations/make_ablation_prompt.py --mode frame_dump  --out p.md

The family's ablation gate asks what a strong model scores when the video is taken away
and replaced by a still, or by a fixed set of frames with no tools to ask for more. Those
runs are only evidence if the model was asked the same question, so the question, the
schema, the tolerance rule and all 84 labels are taken from steps/solve/instruction.md
rather than rewritten here. What changes is the paragraph describing the media and the
tools, and the script asserts that the untouched remainder is still byte-identical to the
shipped prompt.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent.parent
SHIPPED = TASK / "steps" / "solve" / "instruction.md"

# Every degraded run is forced to answer. A refusal scores 0.0 too, but a 0.0 from a
# model that declined to guess says nothing about whether the degraded input is enough,
# which is the whole question. The first single-frame run returned an empty sequence.
FORCE = (" You must still produce a complete answer in the schema below: an empty "
         "sequence is not an acceptable response, so give your best guess for every "
         "recording.")

MEDIA = {
    "single_frame": (
        "You are given ONE still image from each of twenty-two videos, twenty-two images "
        "in all, in the order A through V. Each still is taken from the midpoint of its "
        "recording. You have NO video, NO tools, and no way to ask for another frame. "
        "Answer from the stills alone." + FORCE),
    "no_media": (
        "You are given NO video and NO images. You have NO tools. Answer from what you "
        "already know about these recordings and about how these dishes are usually "
        "prepared." + FORCE),
    "frame_dump": (
        "You are given ONE contact sheet for each of twenty-two videos, twenty-two images "
        "in all, in the order A through V. Each sheet is a 4x4 grid of sixteen frames "
        "sampled at even intervals across that whole recording, read left to right and "
        "top to bottom, with the timestamp in seconds burned into the corner of every "
        "frame. You have NO video, NO tools, and no way to ask for another frame. Answer "
        "from the sheets alone." + FORCE),
}


def build(mode: str) -> str:
    ship = SHIPPED.read_text()

    # The shipped prompt opens with a paragraph about the clips and a section about the
    # tools. Both are replaced; everything between and after them is left alone.
    head_end = ship.index("\n\n", ship.index("You are given twenty-two videos"))
    out = MEDIA[mode] + ship[head_end:]
    # Kill the tool affordances, which do not exist in an ablation, and the file target,
    # since a toolless run has nothing to write with.
    out = re.sub(r"^.*\b(ffmpeg|ffprobe|seek|extract frames?)\b.*$", "", out, flags=re.M | re.I)
    out = re.sub(r"^.*/workspace/output/solution\.json.*$",
                 "Print the JSON object and nothing else as your final message.",
                 out, flags=re.M)
    out = re.sub(r"\n{3,}", "\n\n", out)
    # The parts that carry the question must survive verbatim.
    for must in ('"sequence"', "t_start", "t_end", "tolerance"):
        assert must in out, f"the ablation prompt lost {must}, so it is not the same question"
    # The vocabulary is a bullet list of `N` label lines, not a table. An earlier draft
    # counted table rows, matched zero in both files, and the assertion fired rather than
    # passing a prompt that had lost its vocabulary.
    rows = lambda t: len(re.findall(r"^- `\d+` \S", t, re.M))
    n_ship, n_out = rows(ship), rows(out)
    assert n_ship == n_out == 84, f"vocabulary rows: shipped {n_ship}, ablation {n_out}"
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=sorted(MEDIA))
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    text = build(args.mode)
    args.out.write_text(text)
    print(f"wrote {args.out}: {len(text)} bytes, all 84 vocabulary rows carried over")


if __name__ == "__main__":
    main()
