#!/usr/bin/env python3
"""Score a v4 standing-census submission.

One point per (checkpoint, block type) cell whose count is exactly right;
the reward is the fraction of cells earned. There is no gate. An earlier
draft gated the primary on the running total being within two, which turned
the metric into a cliff: perfect tracking with the clock five seconds out
scored the same zero as an empty file, and a metric that cannot tell 95 per
cent from 0 per cent measures nothing. The primary separates on its own --
an even split of a rate-extrapolated total earns 0.03 -- so nothing is
bolted on top of it.
"""
import json, sys

CHECKPOINTS = [60 * k for k in range(1, 31)]
TYPES = ["birchwood", "bookshelf", "brick_block", "gravel",
         "hardened_clay_orange", "mossycobble"]


def load(path):
    d = json.load(open(path))
    if isinstance(d, dict):
        for k in ("census", "checkpoints", "standing", "counts"):
            if k in d:
                d = d[k]
                break
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            try:
                out[int(round(float(k)))] = {str(a).strip().lower(): int(b) for a, b in v.items()}
            except Exception:
                continue
    else:
        for e in d:
            try:
                t = int(round(float(e.get("t", e.get("time")))))
                c = e.get("counts", e.get("blocks", e))
                out[t] = {str(a).strip().lower(): int(b)
                          for a, b in c.items() if str(a).strip().lower() in TYPES}
            except Exception:
                continue
    return out


def score(gt, pred):
    ok = 0
    per_ck = []
    for t in CHECKPOINTS:
        g = gt.get(t, {})
        p = pred.get(t, {})
        hit = sum(1 for v in TYPES if int(g.get(v, 0)) == int(p.get(v, 0)))
        ok += hit
        per_ck.append(hit)
    n = len(CHECKPOINTS) * len(TYPES)
    return {"reward": round(ok / n, 4), "cells_exact": ok, "cells_total": n,
            "per_checkpoint": per_ck}


if __name__ == "__main__":
    G = load(sys.argv[1])
    P = load(sys.argv[2])
    print(json.dumps(score(G, P), indent=1))
