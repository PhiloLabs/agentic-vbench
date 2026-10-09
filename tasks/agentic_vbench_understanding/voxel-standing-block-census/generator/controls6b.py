#!/usr/bin/env python3
"""Attacks on the v6 census, at whichever span the task ends up using."""
import os, sys
import numpy as np
from collections import Counter
sys.path.insert(0, os.environ.get("AVB_LUANTI_ROOT", os.path.dirname(os.path.abspath(__file__))))
from judge6 import TYPES
from gt6_fixed import build


def replay(ev, cks):
    alive, out, i = {}, {}, 0
    for ck in cks:
        while i < len(ev) and ev[i][0] <= ck:
            _, act, name, pos = ev[i]
            if act == "place":
                alive[pos] = name
            else:
                alive.pop(pos, None)
            i += 1
        c = Counter(alive.values())
        out[ck] = {v: c.get(v, 0) for v in TYPES}
    return out


def split(total, weights):
    raw = [total * w for w in weights]
    base = [int(x) for x in raw]
    rem = total - sum(base)
    for i in sorted(range(len(raw)), key=lambda i: raw[i] - base[i], reverse=True)[:max(0, rem)]:
        base[i] += 1
    return {v: base[i] for i, v in enumerate(TYPES)}


def run(logf, off, span, step):
    cks = [step * k for k in range(1, span // step + 1)]
    G, ev = build(logf, off, cks, TYPES)
    ev = [e for e in ev if e[0] <= span]
    tot = [sum(G[c].values()) for c in cks]
    ncell = len(cks) * len(TYPES)

    def ex(P):
        return sum(1 for c in cks for v in TYPES if G[c][v] == P.get(c, {}).get(v, 0)) / ncell

    def rep(tag, P):
        print("  %-46s %.4f" % (tag, ex(P)))

    print("\n=== %d s, %d checkpoints, %d cells, per-cell mean %.1f ==="
          % (span, len(cks), ncell,
             np.mean([G[c][v] for c in cks for v in TYPES])))
    print("  -- obtainable information only --")
    rep("all zero", {c: {v: 0 for v in TYPES} for c in cks})
    mc = int(round(np.mean([G[c][v] for c in cks for v in TYPES])))
    for g in (mc - 20, mc, mc + 20):
        rep("every cell = %d" % g, {c: {v: g for v in TYPES} for c in cks})
    even = [1 / len(TYPES)] * len(TYPES)
    rep("total linear in t to the true final, even split",
        {c: split(int(round(tot[-1] * (k + 1) / len(cks))), even) for k, c in enumerate(cks)})
    print("  -- handed part of the answer key --")
    rep("ORACLE per-checkpoint total, even split",
        {c: split(tot[k], even) for k, c in enumerate(cks)})
    freq = Counter(n for _, a, n, _ in ev if a == "place")
    sf = sum(freq.values())
    rep("ORACLE total + whole-video type mix",
        {c: split(tot[k], [freq[v] / sf for v in TYPES]) for k, c in enumerate(cks)})
    rng = np.random.default_rng(5)
    for miss in (0.02, 0.05, 0.10, 0.20, 0.35):
        rep("honest tracking, misses %d%%" % (miss * 100),
            replay([e for e in ev if rng.random() > miss], cks))
    rep("perfect tracking, clock off by 10s",
        replay([(t + 10, a, n, p) for t, a, n, p in ev], cks))
    rep("perfect tracking, removals ignored", replay([e for e in ev if e[1] == "place"], cks))
    rep("ORACLE truth", G)


if __name__ == "__main__":
    logf, off = sys.argv[1], float(sys.argv[2])
    run(logf, off, 1800, 60)
    run(logf, off, 900, 60)
