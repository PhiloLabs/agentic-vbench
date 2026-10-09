#!/usr/bin/env python3
"""Deterministic scorer for voxel-standing-block-census.

One point per (checkpoint, block type) cell whose count is exactly right;
the reward is the fraction of the 180 cells earned. Nothing else: no partial
credit for being close, and no gate on top.

The gate question was settled by measurement. An earlier draft required the
running total at every checkpoint to be within two before any cell counted,
which scored perfect tracking with the clock five seconds out (0.94 of cells
exact) the same as an empty file. A metric that cannot separate 94 per cent
from nothing measures nothing. The primary separates on its own: the best
attack that uses only obtainable information earns 0.0222, and a solver that
tracks honestly but misses a twentieth of the events earns 0.1333.

A submission is read leniently in shape and strictly in content. Keys may be
strings or numbers, the census may be at the top level or under "census",
and unknown extra keys are ignored; but a count is right only when it is the
exact integer, and a checkpoint or type that is missing scores zero for those
cells rather than being skipped.
"""
import argparse, json, sys

CHECKPOINTS = [60 * k for k in range(1, 31)]
TYPES = ["birchwood", "bookshelf", "brick_block", "gravel",
         "hardened_clay_orange", "mossycobble"]


def read_census(path, key="census"):
    try:
        d = json.load(open(path))
    except Exception as e:
        return None, "could not parse %s: %s" % (path, e)
    if isinstance(d, dict) and key in d and isinstance(d[key], dict):
        d = d[key]
    if not isinstance(d, dict):
        return None, "expected an object mapping times to per-type counts"
    out = {}
    for k, v in d.items():
        try:
            t = int(round(float(str(k).strip())))
        except Exception:
            continue
        if not isinstance(v, dict):
            continue
        row = {}
        for name, n in v.items():
            name = str(name).strip().lower()
            if name not in TYPES:
                continue
            try:
                row[name] = int(n)
            except Exception:
                pass
        out[t] = row
    return out, None


def score(truth, pred):
    exact, per_ck = 0, []
    for t in CHECKPOINTS:
        g = truth.get(t, {})
        p = pred.get(t, {})
        hit = sum(1 for v in TYPES if int(g.get(v, 0)) == int(p.get(v, 0)))
        exact += hit
        per_ck.append(hit)
    n = len(CHECKPOINTS) * len(TYPES)
    return {
        "reward": round(exact / n, 6),
        "cells_exact": exact,
        "cells_total": n,
        "checkpoints_answered": sum(1 for t in CHECKPOINTS if pred.get(t)),
        "per_checkpoint_cells_exact": per_ck,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", required=True)
    ap.add_argument("--truth", required=True)
    ap.add_argument("--reward-json")
    ap.add_argument("--reward-txt")
    a = ap.parse_args()

    truth, err = read_census(a.truth)
    if err:
        sys.exit("ground truth unreadable: " + err)
    if sorted(truth) != CHECKPOINTS:
        sys.exit("ground truth does not cover exactly the thirty checkpoints")

    pred, err = read_census(a.solution)
    if pred is None:
        res = {"reward": 0.0, "cells_exact": 0,
               "cells_total": len(CHECKPOINTS) * len(TYPES),
               "checkpoints_answered": 0, "error": err}
    else:
        res = score(truth, pred)

    if a.reward_json:
        json.dump(res, open(a.reward_json, "w"), indent=1)
    if a.reward_txt:
        open(a.reward_txt, "w").write("%.6f\n" % res["reward"])
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
