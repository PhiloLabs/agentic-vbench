#!/usr/bin/env python3
"""Rescore every retained ledger with the shipped judge.

Every number in `scores.md` comes from here. Run it from the task directory:

    python3 calibration/rescore_ledgers.py

Nothing is downloaded and no model is called; the ledgers are the agents' own
submitted answers, kept next to the judge so the table can be checked without
replaying a rollout.

The `pruned` column is a self-audit, not a score. Per-clearance credit is
measured against what a transcript alone could have said, and an answer that
falls short of that subtracts -- so an agent that could tell which of its own
readings were weak could raise its score by withholding them. This column
reports how far that goes on each real ledger, by repeatedly dropping every
clearance whose credit lands below the transcript-only floor. The gap between
`reward` and `pruned` is the size of the incentive the metric still carries.

A ledger the judge refuses to parse is reported as reward 0 with `--` in the
remaining columns, and the judge's own rejection message is printed underneath.
That is the row's real result: `claude-opus-4.8-native` submitted a bare JSON
array instead of `{"clearances": [...]}`, and the score reflects it.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
JUDGE_PATH = TASK / "steps/solve/tests/judge.py"
GROUND_TRUTH = TASK / "steps/solve/tests/ground_truth.json"

SPEC = importlib.util.spec_from_file_location("flightgear_judge", JUDGE_PATH)
assert SPEC and SPEC.loader
judge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(judge)


def truth() -> dict:
    return json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))


def rescore(document: dict) -> dict:
    usable, submitted, dropped = judge.accept_predictions(document)
    return judge.score(usable, truth(), submitted=submitted, dropped=dropped)


def rejected(document: object) -> str | None:
    """The judge's own reason for refusing a submission, or None if it accepts.

    A ledger the judge rejects scores 0 -- that is the row's real result, not a
    harness failure -- so this reports the reason instead of raising.
    """
    try:
        judge.accept_predictions(document)
    except (ValueError, TypeError, AttributeError) as error:
        return str(error)
    return None


def entry_count(document: object) -> int:
    if isinstance(document, dict):
        entries = document.get("clearances")
        return len(entries) if isinstance(entries, list) else 0
    return len(document) if isinstance(document, list) else 0


def best_pruned(document: dict) -> tuple[float, int]:
    """Reward after repeatedly dropping every below-floor clearance."""
    expected = truth()["clearances"]
    ceiling = judge.shortcut_ceiling(expected)
    kept, _, _ = judge.accept_predictions(document)
    while kept:
        drop = set()
        for predicted_position, expected_position, units in judge.align(kept, expected):
            headroom = judge.FULL_CREDIT_UNITS - ceiling[expected_position]
            if headroom <= 0:
                continue
            if (units - ceiling[expected_position]) / headroom < 0:
                drop.add(predicted_position)
        if not drop:
            break
        kept = [event for index, event in enumerate(kept) if index not in drop]
    result = judge.score(kept, truth(), submitted=len(kept), dropped=0)
    return result["reward"], len(kept)


def rows() -> list[tuple[str, dict]]:
    found: list[tuple[str, dict]] = [("oracle", truth())]
    for directory, prefix in (
        (TASK / "calibration/rollouts/ledgers", "agent"),
        (TASK / "calibration/ablations/ledgers", "ablation"),
    ):
        for path in sorted(directory.glob("*.json")):
            found.append(
                (f"{prefix}: {path.stem}", json.loads(path.read_text(encoding="utf-8")))
            )
    found.append(("empty", {"clearances": []}))
    return found


def main() -> None:
    expected = truth()["clearances"]
    ceiling = judge.shortcut_ceiling(expected)
    gradable = sum(1 for units in ceiling if judge.FULL_CREDIT_UNITS - units > 0)
    print(
        f"transcript-only ceiling: {sum(ceiling)}/{judge.FULL_CREDIT_UNITS * len(expected)} units, "
        f"{gradable}/{len(expected)} clearances still gradable"
    )
    anchor = rescore({"clearances": judge.shortcut_reference(expected)})
    print(f"transcript-only anchor reward: {anchor['reward']:.4f}\n")

    width = max(len(name) for name, _ in rows())
    header = (
        f"{'run':<{width}}  {'n':>3}  {'reward':>7}  {'matched':>7}  {'full':>4}"
        f"  {'pruned':>7}  {'kept':>4}"
    )
    print(header)
    notes: list[str] = []
    for name, document in rows():
        reason = rejected(document)
        if reason is not None:
            notes.append(f"{name}: rejected by the judge -- {reason}")
            print(
                f"{name:<{width}}  {entry_count(document):>3}  "
                f"{0.0:>7.4f}  {'--':>7}  {'--':>4}  {'--':>7}  {'--':>4}"
            )
            continue
        result = rescore(document)
        details = result["details"]
        pruned, kept = best_pruned(document)
        print(
            f"{name:<{width}}  {entry_count(document):>3}  "
            f"{result['reward']:>7.4f}  {details['identity_matches']:>7}  "
            f"{details['full_credit_matches']:>4}  {pruned:>7.4f}  {kept:>4}"
        )
    for note in notes:
        print(f"\n{note}")


if __name__ == "__main__":
    main()
