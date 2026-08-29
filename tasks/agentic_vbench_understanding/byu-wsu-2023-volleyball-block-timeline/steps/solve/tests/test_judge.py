#!/usr/bin/env python3
"""Regression tests for judge.py. Pure stdlib; run: python3 test_judge.py

Pins the three-attribution rule (blockers, blocked hitter, setter: all three for
full credit, exactly one wrong for partial), the symmetry of the blocker rule
between solo and shared credit, the two-Bower lastname ambiguity, the
oracle/empty invariants, and every reward published in calibration/scores.md.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
JUDGE = HERE / "judge.py"
sys.path.insert(0, str(HERE))
import judge  # noqa: E402

GT = judge.GROUND_TRUTH
FAILS = []


def details(events):
    d = Path(tempfile.mkdtemp())
    sol = d / "s.json"
    sol.write_text(json.dumps({"events": events}))
    subprocess.run([sys.executable, str(JUDGE), "--solution", str(sol),
                    "--reward-json", str(d / "r.json"), "--reward-txt", str(d / "t.txt")],
                   check=True, capture_output=True)
    return json.loads((d / "r.json").read_text())["details"]


def check(name, cond):
    print(f"  [{'ok' if cond else 'FAIL'}] {name}")
    if not cond:
        FAILS.append(name)


def find(setno, score):
    return next(g for g in GT if g["set"] == setno and g["score_after"] == score)


print("== invariants ==")
check("18 block points, every one with a setter",
      len(GT) == 18 and all(g["type"] == "block" and g.get("setter") for g in GT))
check("oracle -> 1.0", details([dict(g) for g in GT])["full_matches"] == 18)
check("empty -> 0.0", details([])["f1"] == 0.0)

SOLO = find(3, "6-7")
PAIR = find(1, "18-14")

print("== the three attributions ==")
check("all three right -> full", details([dict(PAIR)])["full_matches"] == 1)
check("setter wrong -> partial",
      details([{**dict(PAIR), "setter": "Wrong Person"}])["partial_matches"] == 1)
check("setter omitted -> partial",
      details([{k: v for k, v in PAIR.items() if k != "setter"}])["partial_matches"] == 1)
check("hitter wrong -> partial",
      details([{**dict(PAIR), "blocked": "Wrong Person"}])["partial_matches"] == 1)
check("one blocker wrong -> partial",
      details([{**dict(PAIR), "players": [PAIR["players"][0], "Wrong Person"]}])["partial_matches"] == 1)
check("setter AND hitter wrong -> nothing",
      details([{**dict(PAIR), "setter": "Wrong A", "blocked": "Wrong B"}])["partial_matches"] == 0)
check("blocker AND setter wrong -> nothing",
      details([{**dict(PAIR), "players": [PAIR["players"][0], "Wrong A"],
                "setter": "Wrong B"}])["partial_matches"] == 0)

print("== blocker rule is symmetric for solo and shared credit ==")
check("solo-wrong -> partial",
      details([{**dict(SOLO), "players": ["Wrong Person"]}])["partial_matches"] == 1)
check("solo-missing -> partial", details([{**dict(SOLO), "players": []}])["partial_matches"] == 1)
check("solo-extra -> partial",
      details([{**dict(SOLO), "players": [SOLO["players"][0], "Extra Person"]}])["partial_matches"] == 1)
check("two wrong blockers -> nothing",
      details([{**dict(PAIR), "players": ["Wrong One", "Wrong Two"]}])["partial_matches"] == 0)

print("== names and anchors ==")
BOWER = find(4, "17-23")   # Eden Bower blocking; Whitney Bower also appears in the key
check("ambiguous lastname alone does not match",
      details([{**dict(BOWER), "players": ["Bower"]}])["full_matches"] == 0)
check("the full name does match", details([dict(BOWER)])["full_matches"] == 1)
check("wrong score_after -> nothing",
      details([{**dict(PAIR), "score_after": "99-99"}])["full_matches"] == 0)
check("duplicate prediction consumes one slot",
      details([dict(PAIR), dict(PAIR)])["full_matches"] == 1)

print("== the 19th block point costs nothing to report ==")
EXCLUDED = {"set": 2, "score_after": "1-2", "type": "block",
            "players": ["Magda Jehlarova"], "blocked": "Kate Prior",
            "setter": "Whitney Bower"}
base = details([dict(PAIR)])
withit = details([dict(PAIR), dict(EXCLUDED)])
check("reporting it does not change the reward", base["f1"] == withit["f1"])
check("it is set aside rather than scored", withit["set_aside_unscored_anchor"] == 1)
check("it leaves the scored denominator alone", withit["n_scored"] == base["n_scored"])
check("the raw submission count still reflects it", withit["n_predicted"] == 2)
check("an empty answer plus that point alone is still 0.0",
      details([dict(EXCLUDED)])["f1"] == 0.0)
check("a wrong-name report of it is equally free",
      details([dict(PAIR), {**dict(EXCLUDED), "players": ["Wrong Person"]}])["f1"]
      == base["f1"])

print("== published calibration rewards still reproduce ==")
CALIB = HERE.parents[2] / "calibration"
PUBLISHED = {
    "rollouts/codex-fresh.solution.json": 0.0213,
    "rollouts/opus-fresh.solution.json": 0.0,
    "ablations/no_media.solution.json": 0.0,
    "ablations/single_frame.solution.json": 0.0,
    "ablations/frame_dump.solution.json": 0.0,
    "ablations/all_frames.solution.json": 0.0,
}
for rel, expected in PUBLISHED.items():
    events = json.loads((CALIB / rel).read_text())["events"]
    got = details(events)["f1"]
    check(f"{rel} scores {expected}", got == expected)

print()
if FAILS:
    print(f"{len(FAILS)} FAILURES: {FAILS}")
    sys.exit(1)
print("all tests passed")
