#!/usr/bin/env python3
"""Reproduce the corpus and re-check the rule that produced it.

    python3 provenance/take_selection.py --cc4d <dir> --derived provenance/step-derived.json

build_gt.py applies the rules; this file states them, re-derives the pool independently
of the shipped key, asserts the two agree, and runs the checks that a selection rule can
fail silently. Nothing here is descriptive: if the rule below no longer produces the
shipped corpus, this exits non-zero.

THE RULES, fixed before any recording was inspected and before any agent was run.

  R1  No recording under 10 minutes. That floor is the family README's own lower bound
      for a single-video task, so it belongs to the family rather than to this task and
      is not available here as a knob.
  R2  The recording must carry CaptainCook4D step annotations, and its activity must be
      one where the step text is a function of (activity_id, step_id). Four activities
      annotate one id with two different texts across recordings, which means the id
      does not identify the step there; those activities are excluded whole rather than
      patched, because patching would put us in the business of authoring labels.
  R2b The 4K GoPro stream must actually have been published. 18 otherwise-usable
      recordings are annotated but have no 4K link in the official download table. This
      is a property of the release, not a threshold.
  R3  The recording must clear the eligibility gate: at least MIN_ERROR_STEPS steps that
      the dataset annotates as performed with an error, and at least MIN_ORDER_INVERSIONS
      departures from the canonical order of its activity, so that reciting the recipe
      cannot answer it.

      The Ego-Exo4D version of this task asked for repeat instances instead of error
      steps, at the same threshold of 3. Both criteria exist for one purpose, to
      guarantee that replaying the activity's canonical script cannot score. Repeats do
      it by making the label alone insufficient. Annotated errors do it by making the
      script itself wrong for this particular recording. CaptainCook4D steps almost
      never repeat, its median recording repeats no step at all, so the repeat criterion
      would admit 3 of 384 recordings; it also ships an error annotation the other
      corpus does not have. The criterion was replaced rather than relaxed, and the
      number 3 was carried across rather than re-chosen.
  R4  Ascending recording_id, adding recordings until the next one would carry the total
      past the family's 300-minute ceiling, then stop. Adding until full and stopping is
      what makes this rule un-tunable. Skipping a recording that does not fit and
      continuing with smaller ones would quietly bias the corpus toward short
      recordings, which is a knob, so this loop breaks rather than continues.
  R5  Present in that same ascending recording_id order, which is arbitrary with respect
      to everything the task scores. Verified below rather than assumed.

WHAT WAS CONSIDERED AND NOT USED. Ascending recording_id walks the dataset activity by
activity, so the corpus lands on 6 dishes with several recordings each rather than on
many dishes with one each. A one-recording-per-activity rule was written and run during
exploration; it yields 17 recordings over 17 dishes and a 270-label vocabulary instead
of 85. It was dropped because it is a knob: nothing outside our own preference selects
it, and it was never scored against an agent, so it is recorded here rather than in a
drawer. Several recordings of one dish is also what the Ego-Exo4D version of this task
had, and it is the setting in which the recipe-order prior is most tempting and most
clearly fails.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_gt as bg  # noqa: E402


def pearson(xs, ys) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cc4d", required=True, type=Path)
    ap.add_argument("--derived", required=True, type=Path)
    args = ap.parse_args()
    ann, errs, dur, links = bg.load(args.cc4d)
    excluded = bg.conflicted_activities(ann)

    pool = []
    for rid, rec in sorted(ann.items(), key=lambda kv: bg.rid_key(kv[0])):
        if rec["activity_id"] in excluded:
            continue
        if "gopro_4k" not in links.get(rid, {}):
            continue
        if rid not in dur or dur[rid] < bg.MIN_TAKE_SEC:
            continue
        inst = bg.transcript(rec)
        elig = bg.eligibility(inst, bg.canonical_order(ann, rec["activity_id"], rid))
        if elig["eligible"]:
            pool.append({"rid": rid, "dur": dur[rid], "n": len(inst),
                         "act": rec["activity_name"], **elig})

    sel, total = [], 0.0
    for r in pool:
        if total + r["dur"] > bg.CORPUS_CAP_SEC:
            break
        sel.append(r)
        total += r["dur"]

    d = json.loads(args.derived.read_text())
    shipped = [v["recording_id"] for v in d["videos"]]
    assert [r["rid"] for r in sel] == shipped, \
        f"the rule no longer produces the shipped corpus\n  rule: {[r['rid'] for r in sel]}\n  ship: {shipped}"
    assert abs(total - d["total_duration_sec"]) < 0.01
    print(f"R1-R4 reproduce the shipped corpus exactly: {len(sel)} recordings, "
          f"{total/60:.1f} min")

    # R5. The presentation order must not carry information about anything scored. The
    # honest way to check is a permutation test rather than an eyeball: how often does a
    # random ordering of the eligible pool put a prefix correlation this large?
    ranks = list(range(len(pool)))
    durs = [r["dur"] for r in pool]
    full = pearson(ranks, durs)
    prefix = pearson(list(range(len(sel))), [r["dur"] for r in sel])
    rng = random.Random(20260827)
    trials = 10000
    hits = 0
    for _ in range(trials):
        shuf = durs[:]
        rng.shuffle(shuf)
        if abs(pearson(list(range(len(sel))), shuf[:len(sel)])) >= abs(prefix):
            hits += 1
    print(f"R5 rank-vs-duration correlation: {full:+.3f} over the {len(pool)} eligible, "
          f"{prefix:+.3f} over the {len(sel)}-recording prefix")
    print(f"   a prefix correlation that large arises by chance {100*hits/trials:.1f}% "
          f"of the time over {trials} permutations")

    n = sum(r["n"] for r in sel)
    sizes = sorted((r["n"] for r in sel), reverse=True)
    print(f"\nkey concentration: the largest five recordings hold "
          f"{100*sum(sizes[:5])/n:.1f}% of the {n} instances")
    print(f"eligible pool {len(pool)}, of which selected {len(sel)}; excluded activities "
          f"{excluded}")
    print(f"\n{'':4}{'recording':<10}{'min':>6}{'steps':>7}{'err':>5}{'inv':>5}  dish")
    for i, r in enumerate(sel):
        print(f"  {chr(65+i)} {r['rid']:<10}{r['dur']/60:6.1f}{r['n_instances']:7d}"
              f"{r['n_error_steps']:5d}{r['n_order_inversions']:5d}  {r['act']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
