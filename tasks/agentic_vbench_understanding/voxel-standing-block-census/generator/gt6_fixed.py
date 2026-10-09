#!/usr/bin/env python3
"""v6 ground truth with an explicitly supplied clock offset.

The three sync flashes rendered only once in this take, so the offset comes
from the capture script's own epoch files instead: ffmpeg's start and the
moment the GO file was dropped, plus up to one 0.25 s poll before the mod
sees it. Seven earlier captures of the same script measured the offset from
the flashes at +3.99 to +4.22 s, which brackets the 4.13 s this arithmetic
gives, and the placements project a median 52.7 px from the frame centre,
which they could not do if the clock were out by even a second.
"""
import json, os, sys
from collections import Counter
sys.path.insert(0, os.environ.get("AVB_LUANTI_ROOT", os.path.dirname(os.path.abspath(__file__))))
from make_gt3 import read_log, label


def build(logf, off, checkpoints, types, out=None):
    rows = read_log(logf)
    ev = sorted((t + off, a, label(n), p) for t, a, n, p, _ in rows
                if a in ("place", "redig"))
    alive, i, gt = {}, 0, {}
    for ck in checkpoints:
        while i < len(ev) and ev[i][0] <= ck:
            _, act, name, pos = ev[i]
            if act == "place":
                alive[pos] = name
            else:
                alive.pop(pos, None)
            i += 1
        c = Counter(alive.values())
        gt[ck] = {v: c.get(v, 0) for v in types}
    extra = {n for _, _, n, _ in ev} - set(types)
    if extra:
        sys.exit("log holds types outside the vocabulary: %s" % extra)
    if out:
        json.dump({"offset": off, "census": gt}, open(out, "w"), indent=1)
    return gt, ev


if __name__ == "__main__":
    import numpy as np
    from judge6 import TYPES
    logf, off = sys.argv[1], float(sys.argv[2])
    for span, step, tag in ((1800, 60, "full 30 min"), (900, 60, "first 15 min")):
        cks = [step * k for k in range(1, span // step + 1)]
        gt, ev = build(logf, off, cks, TYPES,
                       "gt_v6_%d.json" % span if len(sys.argv) > 3 else None)
        allc = [gt[c][v] for c in cks for v in TYPES]
        print("%-12s  %2d checkpoints x %d types = %3d cells   per-cell mean %.1f "
              "median %.0f max %d   final total %d"
              % (tag, len(cks), len(TYPES), len(cks) * len(TYPES),
                 np.mean(allc), np.median(allc), max(allc), sum(gt[cks[-1]].values())))
