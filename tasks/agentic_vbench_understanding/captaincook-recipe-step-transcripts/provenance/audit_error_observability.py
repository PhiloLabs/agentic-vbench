#!/usr/bin/env python3
"""Recompute the structural half of the error-field observability audit.

    python3 provenance/audit_error_observability.py

The audit has two halves. The half that needs eyes is written up in
provenance/observability/README.md with the frames it rests on. This file holds the half
a machine can check, so those claims cannot rot: which tags actually decide a row, whether
any row is scored against a visually identical twin, and whether anything the agent can
read hands it the answer.

Every check states what would make it fail, and the ones that scan a corpus assert that
they read something first, because a scan that cannot see its target reports clean.
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
import re
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / "steps" / "solve" / "tests"))
import judge  # noqa: E402

NO_ERROR = "none"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cc4d", type=Path, help="raw annotation dir, for the leak check")
    args = ap.parse_args()

    gt = judge.GROUND_TRUTH
    rows = [(letter, g) for letter, v in gt.items() for g in v]
    assert rows, "the key holds no rows"
    tagged = [(letter, g) for letter, g in rows if g["error"] != [NO_ERROR]]
    print(f"key: {len(rows)} instances, {len(tagged)} carry at least one tag, "
          f"{len(rows) - len(tagged)} carry '{NO_ERROR}'")

    # ---- which tags actually decide a row -------------------------------------
    # Any tag the annotators named counts, so a tag only decides a row when it is the
    # only one that row carries. A tag that is never alone can always be answered by
    # naming a co-tag instead, and so never has to be recognised on its own.
    sole = collections.Counter()
    for _, g in tagged:
        if len(g["error"]) == 1:
            sole[g["error"][0]] += 1
    universe = {t for _, g in rows for t in g["error"] if t != NO_ERROR}
    never_alone = sorted(universe - set(sole))
    print("\nrows a tag has to be recognised on, because it is the row's only tag:")
    for tag, n in sole.most_common():
        print(f"  {tag:20s} {n:4d}")
    for tag in never_alone:
        print(f"  {tag:20s}    0   never load-bearing")
    assert set(sole) | set(never_alone) == universe, "a tag fell out of the census"
    assert sum(sole.values()) + sum(
        1 for _, g in tagged if len(g["error"]) > 1) == len(tagged), "census does not add up"

    # ---- is any row scored against a twin it cannot be told apart from? -------
    # Two rows in the same recording whose starts and ends both sit inside the smaller
    # tolerance are the same 9 frames as far as the agent is concerned. If such a pair
    # disagreed on the error tag, one of them would be unanswerable by construction.
    clash = disagree = 0
    for letter, v in gt.items():
        for a, b in itertools.combinations(v, 2):
            tau = min(a["tau"], b["tau"])
            if abs(a["t_start"] - b["t_start"]) <= tau and abs(a["t_end"] - b["t_end"]) <= tau:
                clash += 1
                if set(a["error"]) != set(b["error"]):
                    disagree += 1
                    print(f"  UNANSWERABLE PAIR {letter}: {a['t_start']:.2f}-{a['t_end']:.2f} "
                          f"{a['error']} vs {b['t_start']:.2f}-{b['t_end']:.2f} {b['error']}")
    print(f"\nrow pairs indistinguishable under the scorer's own tolerance: {clash}; "
          f"pairs among them that disagree on the tag: {disagree}")
    assert disagree == 0, "a row is scored against a twin the agent cannot tell it from"

    # ---- does the numbering hand over the recipe's order? ---------------------
    # Order Error is judged against the recipe's intended order. That order is on the
    # tablet in shot; it must not also be sitting in the label ids, or the agent would get
    # it without looking.
    inc = tot = 0
    for _, v in gt.items():
        for a, b in zip(v, v[1:]):
            tot += 1
            inc += b["id"] > a["id"]
    frac = inc / tot
    print(f"consecutive steps whose label id increases: {inc}/{tot} = {frac:.1%} "
          f"(chance is 50%; near 100% would mean the numbering leaks the recipe order)")
    assert frac < 0.60, "the label numbering tracks the recipe order closely enough to leak it"

    # ---- can the agent read a tag off anything we ship? ----------------------
    prompt = (TASK / "steps" / "solve" / "instruction.md").read_text()
    shipped = [p for p in (TASK / "steps").rglob("*")
               if p.is_file() and "tests" not in p.parts and "solution" not in p.parts]
    assert shipped, "found no agent-visible files to scan"
    named = {p: sorted(t for t in judge.ERROR_TAGS if t in p.read_text(errors="ignore"))
             for p in shipped}
    offenders = {p: t for p, t in named.items() if t and p.name != "instruction.md"}
    print(f"\nagent-visible files scanned: {len(shipped)}; files naming a tag outside the "
          f"prompt's own vocabulary list: {len(offenders)}")
    assert not offenders, f"a shipped file names error tags: {offenders}"
    assert sorted(named[TASK / 'steps' / 'solve' / 'instruction.md']) == sorted(judge.ERROR_TAGS), \
        "the prompt does not list the taxonomy, so this scan proves nothing"

    # ---- does the release's own wording carry the error into the step text? --
    if args.cc4d:
        ann = json.loads((args.cc4d / "complete_step_annotations.json").read_text())
        descs = {s["description"].strip() for r in ann.values() for s in r["steps"]}
        assert descs, "read no step descriptions"
        pat = re.compile(r"instead of|rather than|by mistake|incorrectly|wrong", re.I)
        hits = sorted(t for t in descs if pat.search(t))
        print(f"released step descriptions: {len(descs)} distinct, {len(hits)} phrased as an "
              f"error instruction")
        for t in hits[:5]:
            print(f"    {t}")
        assert not hits, "a step description tells the cook which error to make"
        # positive control: the pattern must be able to fire
        assert pat.search("did it incorrectly"), "the leak pattern cannot match anything"

    print("\nstructural half of the observability audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
