"""Diagnostic: multi-granularity RELAXED accuracy, for reference only.

acc = matched / GT_total (recall over ground truth) — how much of the real timeline the model
recovers at each granularity. Over-prediction is NOT penalized here (unlike the shipped scorer's
F1). The shipped scorer (steps/solve/tests/judge.py) is STRICT G1 below and stays F1; this script
never runs in the harness, it only annotates the calibration report.

6 monotonically-looser granularities (each strictly relaxes the previous, so acc is
non-decreasing left→right):
  G1 strict  : |Dt|<=3  AND type AND entity AND minute_gain AND leader_before   (== judge.py)
  G2 -leader : |Dt|<=3  AND type AND entity AND minute_gain
  G3 -econ   : |Dt|<=3  AND type AND entity                                     (identity+time)
  G4 coarse  : |Dt|<=3  AND type AND entity_coarse   (tower=team+lane; drake/baron only)
  G5 type    : |Dt|<=3  AND type                                               (category+time)
  G6 detect  : |Dt|<=10 (any type)                                             (pure detection)

Usage: GT_PATH=steps/solve/tests/gt.json python calibration/relax_eval.py <ans1> <ans2> ...
"""
import json, os, sys

def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def n(s):
    return str(s if s is not None else "").strip().lower()

def canon(e):
    """Return (ct, entity_full, entity_coarse, minute_gain, leader_before). Handles old schema."""
    t = e.get("type", "")
    ent = e.get("entity")
    if ent is None:
        if t == "champion_kill":  ent = e.get("dead_champion")
        elif t == "tower_kill":   ent = f"{e.get('team')}_{e.get('tower')}"
        elif t == "dragon_kill":  ent = e.get("subtype")
        elif t == "baron_kill":   ent = "baron"
    ct = "epic_monster_kill" if t in ("dragon_kill", "baron_kill") else t
    ent = n(ent)
    # coarse entity
    if ct == "tower_kill":
        p = ent.split("_")
        coarse = f"{p[0]}_{p[1]}" if len(p) >= 2 else ent   # team_lane, drop tier
    elif ct == "epic_monster_kill":
        coarse = "baron" if "baron" in ent else "dragon"     # drop drake element (elder->dragon)
    else:
        coarse = ent                                         # champion unchanged
    return ct, ent, coarse, n(e.get("minute_gain")), n(e.get("leader_before"))

# each granularity: (time tolerance, key function over canon-tuple)
# FINE_TOL (default 3, matching the shipped scorer) sets the tight window for G1-G5;
# G6 keeps a fixed loose ±10s detection window.
FINE = float(os.environ.get("FINE_TOL", "3"))
LEVELS = [
    ("G1 strict",  FINE, lambda c: (c[0], c[1], c[3], c[4])),
    ("G2 -leader", FINE, lambda c: (c[0], c[1], c[3])),
    ("G3 -econ",   FINE, lambda c: (c[0], c[1])),
    ("G4 coarse",  FINE, lambda c: (c[0], c[2])),
    ("G5 type",    FINE, lambda c: (c[0],)),
    ("G6 detect", 10.0, lambda c: ("*",)),
]

def acc_at(gt_e, an_e, tol, keyf):
    used = [False] * len(gt_e)
    gk = [(keyf(canon(g)), float(g["game_clock_s"])) for g in gt_e]
    tp = 0
    for a in an_e:
        try:
            ak, at = keyf(canon(a)), float(a["game_clock_s"])
        except Exception:
            continue
        best, bdt = -1, tol + 1
        for i, (k, gt_t) in enumerate(gk):
            if used[i] or k != ak:
                continue
            dt = abs(gt_t - at)
            if dt <= tol and dt < bdt:
                best, bdt = i, dt
        if best >= 0:
            used[best] = True
            tp += 1
    acc = tp / len(gt_e) if gt_e else 0.0   # recall over GT; over-prediction not penalized
    return acc, tp

def main():
    gt = load(os.environ["GT_PATH"])["events"]
    print("model_answer\t" + "\t".join(name for name, _, _ in LEVELS))
    for path in sys.argv[1:]:
        try:
            ans = load(path)
            an_e = ans.get("events", []) if isinstance(ans, dict) else (ans if isinstance(ans, list) else [])
        except Exception as ex:
            print(f"{path}\tERROR {ex}"); continue
        cells = []
        for name, tol, keyf in LEVELS:
            acc, tp = acc_at(gt, an_e, tol, keyf)
            cells.append(f"{acc:.3f}({tp})")
        print(f"{os.path.basename(path)}\t" + "\t".join(cells))

if __name__ == "__main__":
    main()
