#!/usr/bin/env python3
"""Scan downloaded Labels-v2.json files and rank matches by usable visible restarts
+ outcome variety, so we pick a good match. Prefer a less-famous one for extra safety
(our class restriction already blocks the text/scoreboard leak)."""
import argparse, glob, json, os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import build_gt
ap = argparse.ArgumentParser()
ap.add_argument("--root", required=True, help="dir containing */Labels-v2.json")
ap.add_argument("--top", type=int, default=15)
a = ap.parse_args()
rows = []
for p in glob.glob(os.path.join(a.root, "**", "Labels-v2.json"), recursive=True):
    try:
        gt = build_gt.build(p, None, 3.0)
    except Exception as e:
        continue
    inst = gt["instances"]
    from collections import Counter
    oc = Counter(i["outcome"] for i in inst)
    rows.append((len(inst), oc.get(1,0)+oc.get(2,0), os.path.dirname(p)))
rows.sort(reverse=True)
print(f"{'restarts':>8} {'w/outcome':>9}  match")
for n, o, m in rows[:a.top]:
    print(f"{n:>8} {o:>9}  {m}")
