#!/usr/bin/env python3
"""Deterministic shortcut baselines for soccer-restart-outcome-chains, on the official metric.

    python3 provenance/ablations/run_ablations.py --gt provenance/dortmund_leverkusen.labels-derived.json

The only scoring code used is the shipped verifier, steps/solve/tests/judge.py, loaded from
this task folder. Pure stdlib. Every submission here is as long as the key, and every time
lies inside the two halves the prompt names, so the baselines get the count and the span
for free.

    oracle      the key itself, which must score 1.0
    empty       no entries, which must score 0.0
    no_media    the key's most common (action, team) pair, repeated as many times as the
                key has entries, spread evenly over the halves
    class_mix   the key's exact count of every (action, team) pair, each pair spread evenly
                over the halves: a prior that knows the whole distribution and nothing
                about when anything happened
    random      pairs drawn from the key's own distribution at uniform random times in the
                halves, 400 seeded draws, reported as the mean and the best

The degraded-input model runs live in run_measured.py.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import sys
from collections import Counter

THRESH = 0.10
# Where the two halves sit on the clip. The prompt does not give these away, so a blind
# guesser would have to spread its entries over more of the clip; handing it the true spans
# makes every baseline below stronger than a real blind guess, never weaker.
HALVES = ((350.0, 3225.0), (3400.0, 6210.0))


def _load_judge():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(root, "steps", "solve", "tests", "judge.py")
    spec = importlib.util.spec_from_file_location("judge", path)
    judge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(judge)
    return judge


def _place(x: float) -> float:
    """Map x in [0, total playing span) onto clip time inside the halves."""
    for a, b in HALVES:
        if x <= b - a:
            return round(a + x, 2)
        x -= b - a
    return HALVES[-1][1]


def _even_times(n: int) -> list[float]:
    total = sum(b - a for a, b in HALVES)
    return [_place((k + 0.5) * total / n) for k in range(n)]


def run(gt_path: str, n_random: int = 400, seed: int = 7) -> dict:
    judge = _load_judge()
    with open(gt_path, "r", encoding="utf-8") as f:
        gt = json.load(f)
    key = [{"t": i["t"], "action": i["action"], "team": i["team"]} for i in gt["instances"]]
    assert key == judge.GROUND_TRUTH, "this gt file is not the key judge.py ships"
    n = len(key)

    pairs = Counter((i["action"], i["team"]) for i in key)
    (top_action, top_team), _ = pairs.most_common(1)[0]
    no_media = [{"t": t, "action": top_action, "team": top_team} for t in _even_times(n)]
    class_mix = [{"t": t, "action": a, "team": team}
                 for (a, team), c in sorted(pairs.items()) for t in _even_times(c)]

    rng = random.Random(seed)
    population = [(i["action"], i["team"]) for i in key]
    total = sum(b - a for a, b in HALVES)
    rand = []
    for _ in range(n_random):
        entries = []
        for _ in range(n):
            a, team = rng.choice(population)
            entries.append({"t": _place(rng.uniform(0, total)), "action": a, "team": team})
        rand.append(judge.score(entries)["f1"])

    results = {
        "oracle": judge.score(key)["f1"],
        "empty": judge.score([])["f1"],
        "no_media": judge.score(no_media)["f1"],
        "most_common_pair": f"{top_action} / {top_team}",
        "class_mix": judge.score(class_mix)["f1"],
        "random_mean": round(sum(rand) / len(rand), 4),
        "random_max": max(rand),
        "n_key": n,
    }
    results["PASS_deterministic"] = all(results[k] < THRESH for k in ("no_media", "class_mix", "random_mean"))
    results["oracle_ok"] = results["oracle"] == 1.0
    results["empty_ok"] = results["empty"] == 0.0
    results["threshold"] = THRESH
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", required=True)
    args = ap.parse_args(argv)
    res = run(args.gt)
    json.dump(res, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if (res["oracle_ok"] and res["empty_ok"] and res["PASS_deterministic"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
