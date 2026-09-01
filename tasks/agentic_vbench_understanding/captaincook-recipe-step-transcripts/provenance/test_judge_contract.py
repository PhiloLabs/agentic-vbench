#!/usr/bin/env python3
"""Regression tests for the task-contract bugs found in review of PR #115.

    python3 provenance/test_judge_contract.py

Both were the same shape: something the prompt does not ask the agent for, and cannot be
inferred from watching the video, silently changed the score.

  1. The prompt's schema examples were selected out of the key, so submitting nothing but
     the examples scored 3 true positives and 0.0189.
  2. The judge's alignment is order-preserving, so the key's arbitrary order among steps
     that share an onset was a hidden requirement. Swapping U's two 455.647-second rows
     dropped a perfect oracle to 0.9968.

The second review round added two more of the same shape, both in what an entry is allowed
to say rather than in what the key holds:

  3. An empty or whitespace-only error value normalized to "none", so a submission that
     never judged how anything was performed collected the field on all 115 instances the
     release annotates as correct. On otherwise perfect timing that was worth 0.3662.
  4. The two interval boundaries are tested against the key independently, so on a row
     shorter than two seconds a single instant at its midpoint satisfied both. Six of the
     key's 314 rows are short enough.

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
ORACLE = [{"video": L, "id": g["id"], "t_start": g["t_start"], "t_end": g["t_end"],
           "error": g["error"][0]}
          for L, v in GT.items() for g in v]


def test_prompt_examples_cannot_score() -> None:
    """The prompt's own schema examples must be worth nothing."""
    txt = (TASK / "steps" / "solve" / "instruction.md").read_text()
    rows = re.findall(
        r'\{"video":\s*"([A-Z])",\s*"id":\s*(\d+),\s*"t_start":\s*([\d.]+),'
        r'\s*"t_end":\s*([\d.]+),\s*"error":\s*"([^"]*)"\}', txt)
    assert rows, "the prompt has no schema examples, so this test is checking nothing"
    sub = [{"video": v, "id": int(i), "t_start": float(a), "t_end": float(b), "error": e}
           for v, i, a, b, e in rows]
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


def test_error_field_is_required_and_any_annotated_tag_counts() -> None:
    """The third contract: an entry has to say how the step was performed.

    Three things are checked together because each is meaningless without the others. The
    field must be required, or a submission that ignores it would still score. Any tag the
    release annotates for that step must count, or the rule would secretly demand one
    particular tag out of the 59 instances that carry more than one. And a constant guess
    must be worth roughly the base rate rather than everything, or the field would be
    decoration.
    """
    perfect = judge.grade(ORACLE)
    assert perfect["f1"] == 1.0, f"the oracle no longer scores 1.0: {perfect['f1']}"

    stripped = [{k: v for k, v in e.items() if k != "error"} for e in ORACLE]
    r = judge.grade(stripped)
    assert r["true_positives"] == 0, (
        f"an otherwise perfect answer with no error field scored {r['true_positives']}; "
        f"the field is not actually required")

    # every multi-tag instance answered with its LAST tag rather than its first
    other = [{"video": L, "id": g["id"], "t_start": g["t_start"], "t_end": g["t_end"],
              "error": g["error"][-1]}
             for L, v in GT.items() for g in v]
    n_multi = sum(1 for v in GT.values() for g in v if len(g["error"]) > 1)
    assert n_multi, "no instance carries two tags, so this control checks nothing"
    r = judge.grade(other)
    assert r["f1"] == 1.0, (
        f"answering {n_multi} multi-tag instances with the other annotated tag scored "
        f"{r['f1']}; the rule is demanding one particular tag")

    guess = [dict(e, error="none") for e in ORACLE]
    r = judge.grade(guess)
    base = sum(1 for v in GT.values() for g in v if g["error"] == ["none"]) / \
           sum(len(v) for v in GT.values())
    assert abs(r["f1"] - base) < 0.01, (
        f"a constant 'none' on perfect timing scored {r['f1']}, base rate is {base:.4f}")
    print(f"  ok  error field required; either tag of {n_multi} multi-tag instances counts; "
          f"a constant guess scores {r['f1']} against a base rate of {base:.4f}")


def test_empty_error_value_is_not_a_claim_of_correctness() -> None:
    """Saying nothing about how a step went is not the same as saying it went right."""
    n_none = sum(1 for v in GT.values() for g in v if g["error"] == ["none"])
    assert n_none, "the key annotates no correct steps, so this test cannot fail"

    for blank in ("", "   ", "\t\n"):
        r = judge.grade([dict(e, error=blank) for e in ORACLE])
        assert r["true_positives"] == 0, (
            f"an oracle with error={blank!r} scored {r['true_positives']} true positives; "
            f"the {n_none} instances annotated 'none' are being handed out")
        # The entry still has to cost precision. Dropping it instead would grade the
        # submission as though it had made fewer claims than it did.
        assert r["n_predicted"] == len(ORACLE), (
            f"error={blank!r} removed entries from the denominator: "
            f"{r['n_predicted']} of {len(ORACLE)} counted")

    # Control: the same submission with the literal string the prompt does offer must
    # still collect exactly those instances, or the test above would pass on a judge that
    # had simply stopped scoring the field at all.
    r = judge.grade([dict(e, error="none") for e in ORACLE])
    assert r["true_positives"] == n_none, (
        f"the control scored {r['true_positives']} where the key has {n_none} 'none' "
        f"instances, so the blank cases prove nothing")
    print(f"  ok  blank error values score 0 and still cost precision, while the literal "
          f"\"none\" still collects all {n_none}")


def test_an_instant_is_not_an_interval() -> None:
    """A zero-length or reversed span cannot satisfy both boundaries of a short row."""
    short = [(L, g) for L, v in GT.items() for g in v
             if (g["t_end"] - g["t_start"]) / 2.0 <= g["tau"]]
    assert short, "no row is short enough for this attack, so the test cannot fail"

    # Control first: on exactly those rows, a point at the midpoint DOES land inside both
    # tolerance windows. If this ever stops being true the test below is vacuous.
    for L, g in short:
        mid = (g["t_start"] + g["t_end"]) / 2.0
        assert abs(mid - g["t_start"]) <= g["tau"] and abs(mid - g["t_end"]) <= g["tau"], \
            f"{L} {g['id']}: the midpoint is not inside both windows, control broken"

    for name, warp in (("zero-length", lambda e: dict(e, t_end=e["t_start"])),
                       ("midpoint",
                        lambda e: dict(e, t_start=(e["t_start"] + e["t_end"]) / 2.0,
                                       t_end=(e["t_start"] + e["t_end"]) / 2.0)),
                       ("reversed",
                        lambda e: dict(e, t_start=e["t_end"], t_end=e["t_start"]))):
        r = judge.grade([warp(e) for e in ORACLE])
        assert r["true_positives"] == 0, \
            f"a {name} oracle scored {r['true_positives']} true positives"
        assert r["unusable_entries"] == len(ORACLE), \
            f"a {name} oracle left {len(ORACLE) - r['unusable_entries']} entries usable"
    print(f"  ok  zero-length, collapsed and reversed spans are rejected on all "
          f"{len(ORACLE)} entries, including the {len(short)} rows short enough to "
          f"have been won by an instant")


def main() -> int:
    test_prompt_examples_cannot_score()
    test_error_field_is_required_and_any_annotated_tag_counts()
    test_empty_error_value_is_not_a_claim_of_correctness()
    test_an_instant_is_not_an_interval()
    test_equal_start_order_does_not_matter()
    print("all five contract regressions covered, every control fired as required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
