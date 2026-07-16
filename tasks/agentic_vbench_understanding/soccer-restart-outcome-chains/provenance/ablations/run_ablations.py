#!/usr/bin/env python3
"""Shortcut ablations for soccer-restart-outcome-chains, scored on the OFFICIAL metric.

Self-contained: the only scoring code it uses is the shipped verifier,
`steps/solve/tests/judge.py`, loaded from this task folder. Pure stdlib.

    oracle               [deterministic] : the answer key itself -> must be 1.0
    empty                [deterministic] : {"sequence": []} -> must be ~0
    no_media / prior     [deterministic] : most-common tuple at guessed uniform times
    random               [deterministic] : random tuples, seeded
    single_frame         [needs a VLM]   : answer from one frame (pass --single-frame-answer)
    frame_dump_no_tools  [needs a VLM]   : uniform frames, no tools (pass --frame-dump-answer)

Usage:
    python3 run_ablations.py --gt ../mainz_dortmund.labels-derived.json
    python3 run_ablations.py --gt ../mainz_dortmund.labels-derived.json \
        --frame-dump-answer fd.json --single-frame-answer sf.json
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


def _load_judge():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(root, "steps", "solve", "tests", "judge.py")
    spec = importlib.util.spec_from_file_location("judge", path)
    judge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(judge)
    return judge


def load_gt(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        gt = json.load(f)
    if "instances" not in gt:
        raise ValueError("gt.json must contain `instances` built by build_gt.py")
    return gt


def make_scorer(judge, gt: dict):
    """Score any answer against this gt file, using the shipped judge's matcher."""
    judge.GROUND_TRUTH = [
        {"t": i["t"], "restart_type": i["restart_type"], "team": i["team"], "outcome": i["outcome"]}
        for i in gt["instances"]
    ]

    def score(ans: dict) -> float:
        raw = ans.get("sequence", ans.get("instances", []))
        preds = [judge._norm(e) for e in raw]
        tp = judge._max_monotonic(preds, judge._match)
        n_pred, n_gt = len(preds), len(judge.GROUND_TRUTH)
        p = tp / n_pred if n_pred else 0.0
        r = tp / n_gt if n_gt else 0.0
        return round((2 * p * r / (p + r)) if (p + r) else 0.0, 6)

    return score


def oracle_answer(gt: dict) -> dict:
    return {"sequence": [dict(t=i["t"], restart_type=i["restart_type"], team=i["team"], outcome=i["outcome"])
                         for i in gt["instances"]]}


def _random_answer(gt: dict, rng: random.Random) -> dict:
    types = list(gt.get("restart_types", {}).values()) or [1, 2, 3, 4]
    outs = list(gt.get("outcomes", {}).values()) or [0, 1, 2]
    dur = max((i["t"] for i in gt["instances"]), default=0.0) + 60.0
    n = len(gt["instances"])
    return {"sequence": [dict(t=round(rng.uniform(0, dur), 2), restart_type=rng.choice(types),
                              team=rng.choice(["home", "away"]), outcome=rng.choice(outs)) for _ in range(n)]}


def _prior_answer(gt: dict) -> dict:
    """No-media shortcut: the most common (type, team, outcome) at guessed uniform times."""
    inst = gt["instances"]
    common_type = Counter(i["restart_type"] for i in inst).most_common(1)[0][0]
    common_team = Counter(i["team"] for i in inst).most_common(1)[0][0]
    common_out = Counter(i["outcome"] for i in inst).most_common(1)[0][0]
    dur = max((i["t"] for i in inst), default=0.0) + 60.0
    n = len(inst)
    return {"sequence": [dict(t=(k + 0.5) * dur / max(n, 1), restart_type=common_type,
                              team=common_team, outcome=common_out) for k in range(n)]}


def run(gt_path: str, frame_dump_answer=None, single_frame_answer=None,
        n_random: int = 400, seed: int = 7) -> dict:
    judge = _load_judge()
    gt = load_gt(gt_path)
    score = make_scorer(judge, gt)

    rng = random.Random(seed)
    rand = [score(_random_answer(gt, rng)) for _ in range(n_random)]

    results = {
        "oracle": score(oracle_answer(gt)),
        "empty": score({"sequence": []}),
        "no_media": score(_prior_answer(gt)),
        "random_mean": round(sum(rand) / len(rand), 6),
        "random_max": round(max(rand), 6),
    }
    for name, path in (("frame_dump_no_tools", frame_dump_answer),
                       ("single_frame", single_frame_answer)):
        if path:
            with open(path, "r", encoding="utf-8") as f:
                results[name] = score(json.load(f))

    deterministic = {"no_media": results["no_media"], "random_mean": results["random_mean"]}
    optional = {k: results[k] for k in ("frame_dump_no_tools", "single_frame") if k in results}
    results["PASS_deterministic"] = all(v < THRESH for v in deterministic.values())
    results["PASS_optional"] = all(v < THRESH for v in optional.values()) if optional else None
    results["oracle_ok"] = results["oracle"] == 1.0
    results["empty_ok"] = results["empty"] == 0.0
    results["threshold"] = THRESH
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", required=True)
    ap.add_argument("--frame-dump-answer", default=None)
    ap.add_argument("--single-frame-answer", default=None)
    args = ap.parse_args(argv)
    res = run(args.gt, args.frame_dump_answer, args.single_frame_answer)
    json.dump(res, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    ok = res["oracle_ok"] and res["empty_ok"] and res["PASS_deterministic"] \
        and res["PASS_optional"] in (True, None)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
