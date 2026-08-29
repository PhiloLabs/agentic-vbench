#!/usr/bin/env python3
"""Regression tests for judge.py. Pure stdlib; run: python3 test_judge.py

Covers the partial-credit rule symmetry (solo-wrong / solo-missing / solo-extra /
one-wrong-pair all = exactly one name error = partial; two errors = nothing), the
blocked-hitter requirement, anchors, the oracle/empty invariants, and every reward
published in calibration/scores.md. These tests exercise the same judge.py the
verifier runs; they are not part of the grading path.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
JUDGE = HERE / "judge.py"

sys.path.insert(0, str(HERE))
import judge  # noqa: E402  (import for GROUND_TRUTH and unit-level checks)

GT = judge.GROUND_TRUTH


def run_judge(events):
    d = Path(tempfile.mkdtemp())
    sol = d / "s.json"
    sol.write_text(json.dumps({"events": events}))
    subprocess.run([sys.executable, str(JUDGE), "--solution", str(sol),
                    "--reward-json", str(d / "r.json"), "--reward-txt", str(d / "t.txt")],
                   check=True, capture_output=True)
    return json.loads((d / "r.json").read_text())


def details(events):
    return run_judge(events)["details"]


def find(setno, score):
    for g in GT:
        if g["set"] == setno and g["score_after"] == score:
            return g
    raise KeyError((setno, score))


FAILS = []


def check(name, cond, info=""):
    tag = "ok" if cond else "FAIL"
    print(f"  [{tag}] {name}" + (f"  ({info})" if info and not cond else ""))
    if not cond:
        FAILS.append(name)


print("== invariants ==")
check("GT is 23 block points", len(GT) == 23 and all(g["type"] == "block" for g in GT))
check("every GT block carries a blocked hitter", all(g.get("blocked") for g in GT))
oracle = details([dict(g) for g in GT])
check("oracle -> 1.0 (23 full)", oracle["full_matches"] == 23 and oracle["f1"] == 1.0)
check("empty -> 0.0", details([])["f1"] == 0.0)

print("== partial-credit symmetry ==")
solo = find(3, "16-25")           # solo block: Jehlarova, blocked Ariail
pair = find(1, "4-2")             # pair block: Tuaniga+Miller, blocked Isanovic
base = {"set": solo["set"], "score_after": solo["score_after"], "type": "block",
        "blocked": solo["blocked"]}
pbase = {"set": pair["set"], "score_after": pair["score_after"], "type": "block",
         "blocked": pair["blocked"]}

d = details([{**base, "players": ["Wrong Person"]}])
check("solo-wrong -> partial", d["partial_matches"] == 1 and d["full_matches"] == 0)
d = details([{**base, "players": []}])
check("solo-missing -> partial", d["partial_matches"] == 1)
d = details([{**base, "players": [solo["players"][0], "Extra Person"]}])
check("solo-extra -> partial", d["partial_matches"] == 1)
d = details([{**pbase, "players": [pair["players"][0], "Wrong Person"]}])
check("one-wrong-pair -> partial", d["partial_matches"] == 1)
d = details([{**pbase, "players": ["Wrong One", "Wrong Two"]}])
check("two-wrong-pair -> nothing", d["partial_matches"] == 0 and d["full_matches"] == 0)
d = details([{**base, "players": ["Wrong One", "Wrong Two"]}])
check("solo pred-two-wrong -> nothing", d["partial_matches"] == 0)

print("== blocked-hitter requirement ==")
d = details([{**pbase, "players": list(pair["players"]), "blocked": "Wrong Hitter"}])
check("blockers exact + hitter wrong -> partial", d["partial_matches"] == 1)
d = details([{"set": pair["set"], "score_after": pair["score_after"], "type": "block",
              "players": list(pair["players"])}])  # blocked omitted entirely
check("blockers exact + hitter omitted -> partial", d["partial_matches"] == 1)
d = details([{**pbase, "players": [pair["players"][0], "Wrong Person"], "blocked": "Wrong Hitter"}])
check("blockers off-by-one + hitter wrong -> nothing", d["partial_matches"] == 0)
full = details([dict(pair)])
check("exact block -> full", full["full_matches"] == 1)

print("== anchors ==")
d = details([{**dict(pair), "score_after": "5-2"}])
check("wrong score_after -> nothing", d["full_matches"] == 0 and d["partial_matches"] == 0)
d = details([{**dict(pair), "type": "ace"}])
check("type ace never matches (block-only GT)", d["full_matches"] == 0 and d["partial_matches"] == 0)
d = details([dict(pair), dict(pair)])
check("duplicate prediction consumes one GT slot", d["full_matches"] == 1 and d["n_predicted"] == 2)

print("== published calibration rewards still reproduce ==")
CALIB = HERE.parents[2] / "calibration"
PUBLISHED = {
    "rollouts/codex-fresh.solution.json": 0.0185,
    "rollouts/opus-fresh.solution.json": 0.0,
    "rollouts/hybrid-fable-then-opus.solution.json": 0.0,
    "ablations/no_media.solution.json": 0.0,
    "ablations/single_frame.solution.json": 0.0,
    "ablations/frame_dump.solution.json": 0.0,
}
for rel, expected in PUBLISHED.items():
    events = json.loads((CALIB / rel).read_text())["events"]
    check(f"{rel} scores {expected}", details(events)["f1"] == expected)

print()
if FAILS:
    print(f"{len(FAILS)} FAILURES: {FAILS}")
    sys.exit(1)
print("all tests passed")
