#!/usr/bin/env python3
"""Prove the deterministic core before any real annotation exists.

Hand-authors a synthetic command ledger and checks the calibration anchors the family
enforces: oracle == 1.0, empty == 0.0, a same-size wrong guess ~ 0, a formatting-only
variant still matches (normalization works), and each single-field corruption breaks
its match (the scorer is genuinely strict on every scored field).
"""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "steps" / "solve" / "tests"))
import judge

# Synthetic 4-command ledger covering all outcome types and a never-executed command.
GROUND_TRUTH = [
    {"command_time_s": 620.0, "speaker": "nio", "target": "elea", "action": "bring",
     "object": "iron_blocks", "executor": "elea", "outcome": "completed",
     "execution_start_s": 655.0, "evidence_start_s": 650.0, "evidence_end_s": 675.0},
    {"command_time_s": 1400.0, "speaker": "elea", "target": "nio", "action": "place",
     "object": "lantern", "executor": "nio", "outcome": "corrected",
     "execution_start_s": 1410.0, "evidence_start_s": 1405.0, "evidence_end_s": 1460.0},
    {"command_time_s": 2500.0, "speaker": "nio", "target": "group", "action": "clear",
     "object": "scaffolding", "executor": "kara", "outcome": "partial",
     "execution_start_s": 2540.0, "evidence_start_s": 2535.0, "evidence_end_s": 2600.0},
    {"command_time_s": 4100.0, "speaker": "kara", "target": "nio", "action": "move",
     "object": "chest", "executor": "none", "outcome": "not_done",
     "execution_start_s": None, "evidence_start_s": None, "evidence_end_s": None},
]


def f1(preds):
    return judge.score(preds, GROUND_TRUTH)["reward"]


def main() -> None:
    # oracle
    assert f1(copy.deepcopy(GROUND_TRUTH)) == 1.0, "oracle must score 1.0"
    print("[ok] oracle             -> 1.0")

    # empty
    assert f1([]) == 0.0, "empty must score 0.0"
    print("[ok] empty              -> 0.0")

    # same-size wrong guess
    guess = [{"command_time_s": 1000.0 * i, "speaker": "nio", "target": "elea",
              "action": "build", "object": "wall", "executor": "elea",
              "outcome": "completed", "execution_start_s": 1000.0 * i + 5,
              "evidence_start_s": 1000.0 * i, "evidence_end_s": 1000.0 * i + 30}
             for i in range(1, 5)]
    assert f1(guess) == 0.0, "a wrong-content guess must score ~0"
    print("[ok] wrong guess (x4)   -> 0.0")

    # formatting-only variant
    fmt = copy.deepcopy(GROUND_TRUTH)
    for c in fmt:
        c["object"] = c["object"].upper().replace("_", " ")
        c["speaker"] = c["speaker"].capitalize()
        c["outcome"] = c["outcome"].replace("_", " ").title()
    assert f1(fmt) == 1.0, "normalization must accept formatting variants"
    print("[ok] formatting variant -> 1.0 (normalization works)")

    # strictness: corrupting ANY one scored field must drop that match
    corruptions = [("action", "zzz"), ("object", "zzz"), ("executor", "none"),
                   ("outcome", "partial"),
                   ("command_time_s", GROUND_TRUTH[0]["command_time_s"] + 999),
                   ("execution_start_s", GROUND_TRUTH[0]["execution_start_s"] + 999)]
    for field, bad in corruptions:
        one = copy.deepcopy(GROUND_TRUTH)
        if one[0][field] == bad:
            bad = bad + "x" if isinstance(bad, str) else bad + 1
        one[0][field] = bad
        tp = judge.score(one, GROUND_TRUTH)["details"]["true_positives"]
        assert tp == 3, f"corrupting {field} should yield 3 TP, got {tp}"
    print("[ok] every scored field is load-bearing "
          "(action, object, executor, outcome, both times)")

    # speaker/target are reported but deliberately NOT scored
    for field in ("speaker", "target"):
        one = copy.deepcopy(GROUND_TRUTH)
        one[0][field] = "somebody_else"
        assert f1(one) == 1.0, f"{field} must not affect the reward"
        acc = judge.score(one, GROUND_TRUTH)["details"]["diagnostics"][
            "field_accuracy_among_detected"][field]
        assert acc < 1.0, f"{field} must still be reported in diagnostics"
    print("[ok] speaker/target are unscored but still reported in diagnostics")

    # evidence IoU enforced for executed commands
    bad_ev = copy.deepcopy(GROUND_TRUTH)
    bad_ev[0]["evidence_start_s"] = 9000.0
    bad_ev[0]["evidence_end_s"] = 9030.0
    assert judge.score(bad_ev, GROUND_TRUTH)["details"]["true_positives"] == 3, \
        "evidence-window IoU must be enforced"
    print("[ok] evidence-window IoU is enforced")

    # a not_done command needs no evidence window, and adding one must not crash
    nd = copy.deepcopy(GROUND_TRUTH)
    nd[3]["evidence_start_s"] = None
    assert f1(nd) == 1.0
    print("[ok] not_done commands need no evidence window")

    # non-finite timestamps are rejected. A comparison against NaN is always False,
    # so "reject if outside tolerance" never fired and an all-NaN ledger scored 1.0.
    for bad in (float("nan"), float("inf"), float("-inf")):
        for field in ("command_time_s", "execution_start_s",
                      "evidence_start_s", "evidence_end_s"):
            nf = copy.deepcopy(GROUND_TRUTH)
            for row in nf:
                row[field] = bad
            assert f1(nf) < 1.0, f"{field}={bad!r} must not score as a full match"
    all_nan = copy.deepcopy(GROUND_TRUTH)
    for row in all_nan:
        row["command_time_s"] = row["execution_start_s"] = float("nan")
    assert f1(all_nan) == 0.0, "all-NaN timestamps must score 0.0, not 1.0"
    assert judge.to_float(float("nan")) is None and judge.to_float("inf") is None
    print("[ok] non-finite timestamps (NaN/inf) are rejected — no numeric bypass")

    print("\nALL CHECKS PASSED — deterministic core (v2 command ledger) is sound.")


if __name__ == "__main__":
    main()
