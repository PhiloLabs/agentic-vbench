#!/usr/bin/env python3
"""Regression tests for the two task-contract bugs found in review of PR #115.

    python3 provenance/test_judge_contract.py

Both were the same shape: something the prompt does not ask the agent for, and cannot be
inferred from watching the video, silently changed the score.

  1. The prompt's schema examples were selected out of the key, so submitting nothing but
     the examples scored 3 true positives and 0.0189.
  2. The judge's alignment is order-preserving, so the key's arbitrary order among steps
     that share an onset was a hidden requirement. Swapping U's two 455.647-second rows
     dropped a perfect oracle to 0.9968.

Each test carries a control that must FAIL, because a test that cannot fail is not
evidence: an assertion that only ever sees the good case would pass just as happily on a
judge that ignored order entirely.
"""
from __future__ import annotations

import collections
import itertools
import json
import re
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / "steps" / "solve" / "tests"))
import judge  # noqa: E402

GT = judge.GROUND_TRUTH
ORACLE = [{"video": L, "id": g["id"], "t_start": g["t_start"], "t_end": g["t_end"]}
          for L, v in GT.items() for g in v]


def test_prompt_examples_cannot_score() -> None:
    """The prompt's own schema examples must be worth nothing."""
    txt = (TASK / "steps" / "solve" / "instruction.md").read_text()
    rows = re.findall(
        r'\{"video":\s*"([A-Z])",\s*"id":\s*(\d+),\s*"t_start":\s*([\d.]+),'
        r'\s*"t_end":\s*([\d.]+)\}', txt)
    assert rows, "the prompt has no schema examples, so this test is checking nothing"
    sub = [{"video": v, "id": int(i), "t_start": float(a), "t_end": float(b)}
           for v, i, a, b in rows]
    r = judge.grade(sub)
    assert r["true_positives"] == 0, (
        f"the prompt's {len(sub)} schema examples score {r['true_positives']} true "
        f"positives, F1 {r['f1']}; they are leaking answers")
    assert r["label_and_order_only_matches"] == 0, (
        "a schema example names a label that occurs in the video it is filed under")

    # Control: the same check, handed real key rows, must fail.
    real = ORACLE[:len(sub)]
    assert judge.grade(real)["true_positives"] > 0, (
        "CONTROL FAILED: real key rows also score zero, so this test cannot detect a leak")
    print(f"  ok  {len(sub)} schema examples score 0 "
          f"(control: {len(real)} real rows score {judge.grade(real)['true_positives']})")


def test_equal_start_order_does_not_matter() -> None:
    """Every ordering of an equal-onset group must score the same."""
    groups = []
    for L, v in GT.items():
        by = collections.defaultdict(list)
        for g in v:
            by[round(g["t_start"], 3)].append(g)
        groups += [(L, t, gs) for t, gs in by.items() if len(gs) > 1]
    assert groups, "no equal-onset group in the key, so this test is checking nothing"

    base = judge.grade(ORACLE)["f1"]
    assert base == 1.0, f"the oracle no longer scores 1.0, it scores {base}"
    n = 0
    for L, t, gs in groups:
        idx = [i for i, e in enumerate(ORACLE)
               if e["video"] == L and round(e["t_start"], 3) == t]
        for perm in itertools.permutations(idx):
            sub = list(ORACLE)
            for dst, src in zip(idx, perm):
                sub[dst] = ORACLE[src]
            f1 = judge.grade(sub)["f1"]
            assert f1 == 1.0, (
                f"reordering {L}'s steps at t={t} drops the oracle to {f1}; the key's "
                f"arbitrary order among equal onsets is a hidden requirement")
            n += 1

    # Control. The judge canonicalises a submission to (onset, label) before aligning, so
    # the position of a row in the submitted LIST carries no information: that is what
    # makes the loop above pass, and on its own it would also pass on a judge that had
    # stopped checking order altogether. What must still cost is getting the order of
    # events in TIME wrong, so the control swaps two steps' timestamps rather than their
    # list positions.
    L = groups[0][0]
    far = [i for i, e in enumerate(ORACLE) if e["video"] == L]
    a, b = far[0], far[-1]
    sub = list(ORACLE)
    sub[a] = {**ORACLE[a], "t_start": ORACLE[b]["t_start"], "t_end": ORACLE[b]["t_end"]}
    sub[b] = {**ORACLE[b], "t_start": ORACLE[a]["t_start"], "t_end": ORACLE[a]["t_end"]}
    f1 = judge.grade(sub)["f1"]
    assert f1 < 1.0, (
        f"CONTROL FAILED: swapping two steps' timestamps still scores {f1}, so the "
        f"alignment is not order-preserving in time and this test proves nothing")
    print(f"  ok  {n} orderings of {len(groups)} equal-onset group(s) all score 1.0 "
          f"(control: swapping two steps' times drops it to {f1})")


def main() -> int:
    test_prompt_examples_cannot_score()
    test_equal_start_order_does_not_matter()
    print("both contract regressions covered, both controls fired as required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
