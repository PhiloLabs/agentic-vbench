#!/usr/bin/env python3
"""Regression tests for judge.py. Pure stdlib; run: python3 test_judge.py

Pins the partial-credit rule's symmetry (a solo credit that is wrong, missing, or
padded is one error, exactly like one wrong name in a pair), the blocked-hitter
tiers, the two-Bower lastname ambiguity, and the oracle/empty invariants.
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
check("24 events, 5 aces and 19 blocks",
      len(GT) == 24 and sum(g["type"] == "ace" for g in GT) == 5)
oracle = details([{k: v for k, v in g.items() if v is not None} for g in GT])
check("oracle -> 1.0", oracle["full_matches"] == 24 and oracle["f1"] == 1.0)
check("empty -> 0.0", details([])["f1"] == 0.0)

print("== partial-credit symmetry ==")
solo = find(3, "11-15")     # Jehlarova solo, blocked Mia Lee
pair = find(2, "9-6")       # Prior + Lee, blocked Isanovic
sbase = {"set": solo["set"], "score_after": solo["score_after"], "type": "block",
         "blocked": solo["blocked"]}
pbase = {"set": pair["set"], "score_after": pair["score_after"], "type": "block",
         "blocked": pair["blocked"]}
check("solo-wrong -> partial", details([{**sbase, "players": ["Wrong Person"]}])["partial_matches"] == 1)
check("solo-missing -> partial", details([{**sbase, "players": []}])["partial_matches"] == 1)
check("solo-extra -> partial",
      details([{**sbase, "players": [solo["players"][0], "Extra Person"]}])["partial_matches"] == 1)
check("one-wrong-pair -> partial",
      details([{**pbase, "players": [pair["players"][0], "Wrong Person"]}])["partial_matches"] == 1)
check("two-wrong-pair -> nothing",
      details([{**pbase, "players": ["Wrong One", "Wrong Two"]}])["partial_matches"] == 0)

print("== blocked hitter ==")
check("blockers exact + hitter wrong -> partial",
      details([{**pbase, "players": list(pair["players"]), "blocked": "Wrong Hitter"}])["partial_matches"] == 1)
check("exact block -> full", details([dict(pair)])["full_matches"] == 1)
corrupt = find(2, "1-2")    # the one rally line whose hitter is unrecoverable
check("hitter not required where the source lost it",
      corrupt.get("blocked") is None and
      details([{"set": 2, "score_after": "1-2", "type": "block",
                "players": list(corrupt["players"])}])["full_matches"] == 1)

print("== names ==")
ace = find(3, "21-23")      # Whitney Bower
check("ambiguous lastname alone does not match",
      details([{**{k: v for k, v in ace.items()}, "players": ["Bower"]}])["full_matches"] == 0)
check("full name matches", details([dict(ace)])["full_matches"] == 1)

print()
if FAILS:
    print(f"{len(FAILS)} FAILURES: {FAILS}")
    sys.exit(1)
print("all tests passed")
