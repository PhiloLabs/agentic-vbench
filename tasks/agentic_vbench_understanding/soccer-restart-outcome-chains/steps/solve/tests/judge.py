#!/usr/bin/env python3
"""Grade a soccer match action ledger. Pure Python stdlib, deterministic.

The agent lists every visible action in the full broadcast of one Bundesliga match, each as
(t, action, team), over the seventeen action classes SoccerNet-v2 annotates. A predicted
entry is a true positive when a key entry of the same action and the same team lies within
TOL seconds of it, under a one-to-one matching. Each action class gets its own F1 from its
true positives, its entries and its key entries, and reward = the mean of those F1s over the
classes the key contains, the way SoccerNet averages its spotting metric over classes. Misses
and false positives both cost, and a class with few actions counts as much as one with many.

Matching runs inside each (action, team) group. There, one greedy pass over both lists in
time order finds a largest one-to-one matching: two times match when they are at most TOL
apart, and pairing the earliest compatible pair first never blocks a larger matching.
provenance/build_gt.py checks that against brute force.

Encodings, as stated to the agent in instruction.md:
  action: one of ACTIONS, spelled as SoccerNet-v2 spells it
  team:   "home" or "away", the team that performs the action (for a foul, an offside or a
          card, the side of the player concerned); "none" for "Ball out of play".
          Home is the team named first in the on-screen score graphic.

Ground truth is every annotation SoccerNet-v2's published, multi-annotator Labels-v2.json
marks visible for this match (Borussia Dortmund vs Bayer 04 Leverkusen, 2016-17
Bundesliga), each placed on the clip by one measured offset per half. It is the verified
answer key, not an echo of the input, and the agent never sees it.
"""
import argparse
import json
from pathlib import Path

TOL = 1  # seconds of clip-time tolerance

ACTIONS = (
    "Ball out of play", "Throw-in", "Foul", "Direct free-kick", "Indirect free-kick",
    "Corner", "Penalty", "Clearance", "Shots on target", "Shots off target", "Goal",
    "Kick-off", "Offside", "Yellow card", "Red card", "Yellow->red card", "Substitution",
)
_CANON = {a.lower(): a for a in ACTIONS}
# Spellings a reader of the definitions could reasonably produce for the same class.
_ALIASES = {
    "shot on target": "Shots on target", "shot off target": "Shots off target",
    "kickoff": "Kick-off", "kick off": "Kick-off", "throw in": "Throw-in",
    "yellow to red card": "Yellow->red card", "yellow->red": "Yellow->red card",
}
_TEAMS = {"home": "home", "away": "away", "none": "none", "not applicable": "none"}

# t is seconds from the start of the clip (half 1 spans about [350, 3223], half 2 about [3399, 6209]).
GROUND_TRUTH = [
  {"t": 366.187, "action": "Foul", "team": "away"},
  {"t": 395.975, "action": "Foul", "team": "away"},
  {"t": 405.726, "action": "Indirect free-kick", "team": "home"},
  {"t": 446.339, "action": "Ball out of play", "team": "none"},
  {"t": 453.896, "action": "Throw-in", "team": "home"},
  {"t": 484.574, "action": "Ball out of play", "team": "none"},
  {"t": 515.746, "action": "Corner", "team": "home"},
  {"t": 625.943, "action": "Throw-in", "team": "home"},
  {"t": 693.953, "action": "Shots on target", "team": "home"},
  {"t": 694.763, "action": "Goal", "team": "home"},
  {"t": 757.165, "action": "Throw-in", "team": "away"},
  {"t": 763.677, "action": "Ball out of play", "team": "none"},
  {"t": 775.113, "action": "Throw-in", "team": "home"},
  {"t": 811.212, "action": "Foul", "team": "away"},
  {"t": 909.396, "action": "Shots on target", "team": "home"},
  {"t": 965.029, "action": "Foul", "team": "away"},
  {"t": 997.775, "action": "Ball out of play", "team": "none"},
  {"t": 1009.957, "action": "Throw-in", "team": "home"},
  {"t": 1048.734, "action": "Ball out of play", "team": "none"},
  {"t": 1058.491, "action": "Throw-in", "team": "away"},
  {"t": 1073.081, "action": "Foul", "team": "home"},
  {"t": 1112.436, "action": "Shots on target", "team": "away"},
  {"t": 1115.602, "action": "Shots on target", "team": "away"},
  {"t": 1167.111, "action": "Shots on target", "team": "away"},
  {"t": 1167.924, "action": "Ball out of play", "team": "none"},
  {"t": 1201.139, "action": "Corner", "team": "away"},
  {"t": 1203.129, "action": "Ball out of play", "team": "none"},
  {"t": 1265.123, "action": "Foul", "team": "away"},
  {"t": 1268.246, "action": "Yellow card", "team": "away"},
  {"t": 1310.044, "action": "Indirect free-kick", "team": "home"},
  {"t": 1327.149, "action": "Ball out of play", "team": "none"},
  {"t": 1339.997, "action": "Throw-in", "team": "home"},
  {"t": 1345.482, "action": "Ball out of play", "team": "none"},
  {"t": 1355.826, "action": "Throw-in", "team": "home"},
  {"t": 1361.091, "action": "Ball out of play", "team": "none"},
  {"t": 1430.569, "action": "Ball out of play", "team": "none"},
  {"t": 1450.05, "action": "Corner", "team": "away"},
  {"t": 1465.707, "action": "Ball out of play", "team": "none"},
  {"t": 1487.201, "action": "Throw-in", "team": "home"},
  {"t": 1494.782, "action": "Foul", "team": "away"},
  {"t": 1584.911, "action": "Indirect free-kick", "team": "home"},
  {"t": 1632.615, "action": "Ball out of play", "team": "none"},
  {"t": 1646.706, "action": "Throw-in", "team": "home"},
  {"t": 1651.972, "action": "Ball out of play", "team": "none"},
  {"t": 1678.63, "action": "Throw-in", "team": "home"},
  {"t": 1772.102, "action": "Ball out of play", "team": "none"},
  {"t": 1784.011, "action": "Throw-in", "team": "away"},
  {"t": 1814.224, "action": "Throw-in", "team": "home"},
  {"t": 1824.197, "action": "Ball out of play", "team": "none"},
  {"t": 1825.486, "action": "Throw-in", "team": "home"},
  {"t": 1830.751, "action": "Shots on target", "team": "home"},
  {"t": 1832.292, "action": "Shots off target", "team": "home"},
  {"t": 1832.554, "action": "Ball out of play", "team": "none"},
  {"t": 1864.224, "action": "Corner", "team": "home"},
  {"t": 1869.4, "action": "Ball out of play", "team": "none"},
  {"t": 1894.771, "action": "Corner", "team": "home"},
  {"t": 1896.094, "action": "Shots on target", "team": "home"},
  {"t": 1897.419, "action": "Shots on target", "team": "home"},
  {"t": 1897.692, "action": "Goal", "team": "home"},
  {"t": 1963.611, "action": "Foul", "team": "home"},
  {"t": 1996.414, "action": "Indirect free-kick", "team": "away"},
  {"t": 2006.425, "action": "Shots on target", "team": "away"},
  {"t": 2009.689, "action": "Ball out of play", "team": "none"},
  {"t": 2018.828, "action": "Throw-in", "team": "away"},
  {"t": 2079.164, "action": "Ball out of play", "team": "none"},
  {"t": 2095.874, "action": "Shots off target", "team": "away"},
  {"t": 2097.227, "action": "Ball out of play", "team": "none"},
  {"t": 2112.089, "action": "Corner", "team": "away"},
  {"t": 2115.961, "action": "Shots off target", "team": "away"},
  {"t": 2125.937, "action": "Ball out of play", "team": "none"},
  {"t": 2143.09, "action": "Throw-in", "team": "home"},
  {"t": 2159.748, "action": "Ball out of play", "team": "none"},
  {"t": 2187.796, "action": "Ball out of play", "team": "none"},
  {"t": 2200.978, "action": "Throw-in", "team": "home"},
  {"t": 2246.397, "action": "Foul", "team": "away"},
  {"t": 2288.049, "action": "Foul", "team": "away"},
  {"t": 2293.96, "action": "Indirect free-kick", "team": "home"},
  {"t": 2310.419, "action": "Ball out of play", "team": "none"},
  {"t": 2319.881, "action": "Throw-in", "team": "home"},
  {"t": 2325.8, "action": "Shots off target", "team": "home"},
  {"t": 2327.095, "action": "Ball out of play", "team": "none"},
  {"t": 2358.69, "action": "Corner", "team": "home"},
  {"t": 2401.163, "action": "Ball out of play", "team": "none"},
  {"t": 2439.967, "action": "Throw-in", "team": "away"},
  {"t": 2446.48, "action": "Foul", "team": "home"},
  {"t": 2473.459, "action": "Indirect free-kick", "team": "away"},
  {"t": 2482.239, "action": "Foul", "team": "away"},
  {"t": 2553.984, "action": "Foul", "team": "away"},
  {"t": 2558.446, "action": "Yellow card", "team": "away"},
  {"t": 2623.987, "action": "Substitution", "team": "away"},
  {"t": 2748.382, "action": "Ball out of play", "team": "none"},
  {"t": 2773.234, "action": "Throw-in", "team": "home"},
  {"t": 2790.735, "action": "Shots on target", "team": "home"},
  {"t": 2807.245, "action": "Foul", "team": "home"},
  {"t": 2817.521, "action": "Indirect free-kick", "team": "away"},
  {"t": 2832.428, "action": "Ball out of play", "team": "none"},
  {"t": 2848.438, "action": "Throw-in", "team": "away"},
  {"t": 2849.167, "action": "Foul", "team": "away"},
  {"t": 2957.006, "action": "Substitution", "team": "home"},
  {"t": 3009.071, "action": "Ball out of play", "team": "none"},
  {"t": 3014.277, "action": "Throw-in", "team": "away"},
  {"t": 3040.976, "action": "Foul", "team": "away"},
  {"t": 3057.023, "action": "Indirect free-kick", "team": "home"},
  {"t": 3071.206, "action": "Ball out of play", "team": "none"},
  {"t": 3074.818, "action": "Throw-in", "team": "away"},
  {"t": 3099.983, "action": "Foul", "team": "away"},
  {"t": 3162.07, "action": "Ball out of play", "team": "none"},
  {"t": 3187.405, "action": "Clearance", "team": "home"},
  {"t": 3195.487, "action": "Ball out of play", "team": "none"},
  {"t": 3201.248, "action": "Throw-in", "team": "away"},
  {"t": 3209.551, "action": "Foul", "team": "away"},
  {"t": 3222.646, "action": "Yellow card", "team": "away"},
  {"t": 3399.452, "action": "Kick-off", "team": "home"},
  {"t": 3434.002, "action": "Throw-in", "team": "home"},
  {"t": 3437.629, "action": "Ball out of play", "team": "none"},
  {"t": 3442.937, "action": "Throw-in", "team": "away"},
  {"t": 3445.347, "action": "Ball out of play", "team": "none"},
  {"t": 3453.286, "action": "Throw-in", "team": "away"},
  {"t": 3520.644, "action": "Shots on target", "team": "away"},
  {"t": 3521.147, "action": "Goal", "team": "away"},
  {"t": 3591.125, "action": "Shots on target", "team": "away"},
  {"t": 3670.738, "action": "Ball out of play", "team": "none"},
  {"t": 3678.193, "action": "Throw-in", "team": "home"},
  {"t": 3680.562, "action": "Ball out of play", "team": "none"},
  {"t": 3698.519, "action": "Throw-in", "team": "away"},
  {"t": 3701.271, "action": "Ball out of play", "team": "none"},
  {"t": 3712.084, "action": "Throw-in", "team": "away"},
  {"t": 3755.233, "action": "Foul", "team": "away"},
  {"t": 3770.049, "action": "Indirect free-kick", "team": "home"},
  {"t": 3795.287, "action": "Ball out of play", "team": "none"},
  {"t": 3820.11, "action": "Throw-in", "team": "away"},
  {"t": 3862.241, "action": "Shots on target", "team": "home"},
  {"t": 3870.192, "action": "Ball out of play", "team": "none"},
  {"t": 3998.912, "action": "Offside", "team": "away"},
  {"t": 4033.683, "action": "Indirect free-kick", "team": "home"},
  {"t": 4037.249, "action": "Foul", "team": "home"},
  {"t": 4056.35, "action": "Indirect free-kick", "team": "away"},
  {"t": 4079.806, "action": "Ball out of play", "team": "none"},
  {"t": 4093.585, "action": "Throw-in", "team": "away"},
  {"t": 4105.629, "action": "Ball out of play", "team": "none"},
  {"t": 4112.637, "action": "Throw-in", "team": "away"},
  {"t": 4140.55, "action": "Shots off target", "team": "home"},
  {"t": 4141.283, "action": "Ball out of play", "team": "none"},
  {"t": 4184.38, "action": "Clearance", "team": "away"},
  {"t": 4193.552, "action": "Foul", "team": "away"},
  {"t": 4297.714, "action": "Throw-in", "team": "home"},
  {"t": 4301.444, "action": "Ball out of play", "team": "none"},
  {"t": 4328.716, "action": "Ball out of play", "team": "none"},
  {"t": 4330.844, "action": "Throw-in", "team": "away"},
  {"t": 4397.502, "action": "Ball out of play", "team": "none"},
  {"t": 4427.845, "action": "Foul", "team": "home"},
  {"t": 4435.286, "action": "Indirect free-kick", "team": "away"},
  {"t": 4438.851, "action": "Foul", "team": "away"},
  {"t": 4444.262, "action": "Yellow card", "team": "away"},
  {"t": 4490.683, "action": "Ball out of play", "team": "none"},
  {"t": 4501.839, "action": "Throw-in", "team": "away"},
  {"t": 4512.557, "action": "Ball out of play", "team": "none"},
  {"t": 4541.585, "action": "Ball out of play", "team": "none"},
  {"t": 4555.612, "action": "Throw-in", "team": "home"},
  {"t": 4631.526, "action": "Shots on target", "team": "home"},
  {"t": 4632.615, "action": "Ball out of play", "team": "none"},
  {"t": 4649.585, "action": "Substitution", "team": "away"},
  {"t": 4667.503, "action": "Corner", "team": "home"},
  {"t": 4751.187, "action": "Shots off target", "team": "home"},
  {"t": 4778.666, "action": "Foul", "team": "away"},
  {"t": 4827.26, "action": "Indirect free-kick", "team": "home"},
  {"t": 4832.758, "action": "Shots on target", "team": "home"},
  {"t": 4832.834, "action": "Goal", "team": "home"},
  {"t": 4920.049, "action": "Ball out of play", "team": "none"},
  {"t": 4925.358, "action": "Throw-in", "team": "away"},
  {"t": 4935.87, "action": "Ball out of play", "team": "none"},
  {"t": 4938.348, "action": "Throw-in", "team": "away"},
  {"t": 4986.707, "action": "Ball out of play", "team": "none"},
  {"t": 5004.35, "action": "Throw-in", "team": "home"},
  {"t": 5021.396, "action": "Foul", "team": "away"},
  {"t": 5042.8, "action": "Substitution", "team": "home"},
  {"t": 5066.17, "action": "Foul", "team": "home"},
  {"t": 5121.285, "action": "Direct free-kick", "team": "away"},
  {"t": 5121.285, "action": "Shots on target", "team": "away"},
  {"t": 5122.177, "action": "Goal", "team": "away"},
  {"t": 5157.398, "action": "Ball out of play", "team": "none"},
  {"t": 5161.271, "action": "Throw-in", "team": "away"},
  {"t": 5173.355, "action": "Ball out of play", "team": "none"},
  {"t": 5193.195, "action": "Throw-in", "team": "home"},
  {"t": 5236.268, "action": "Shots off target", "team": "home"},
  {"t": 5237.466, "action": "Ball out of play", "team": "none"},
  {"t": 5254.512, "action": "Clearance", "team": "away"},
  {"t": 5258.588, "action": "Foul", "team": "away"},
  {"t": 5268.224, "action": "Indirect free-kick", "team": "home"},
  {"t": 5287.056, "action": "Shots on target", "team": "home"},
  {"t": 5287.822, "action": "Goal", "team": "home"},
  {"t": 5369.053, "action": "Throw-in", "team": "home"},
  {"t": 5392.451, "action": "Throw-in", "team": "home"},
  {"t": 5448.308, "action": "Ball out of play", "team": "none"},
  {"t": 5477.345, "action": "Corner", "team": "home"},
  {"t": 5501.778, "action": "Ball out of play", "team": "none"},
  {"t": 5520.705, "action": "Substitution", "team": "home"},
  {"t": 5531.407, "action": "Foul", "team": "home"},
  {"t": 5684.01, "action": "Ball out of play", "team": "none"},
  {"t": 5697.715, "action": "Throw-in", "team": "home"},
  {"t": 5704.385, "action": "Foul", "team": "away"},
  {"t": 5715.585, "action": "Yellow card", "team": "away"},
  {"t": 5753.137, "action": "Shots on target", "team": "home"},
  {"t": 5753.577, "action": "Goal", "team": "home"},
  {"t": 5818.438, "action": "Substitution", "team": "away"},
  {"t": 5832.101, "action": "Ball out of play", "team": "none"},
  {"t": 5836.329, "action": "Throw-in", "team": "away"},
  {"t": 5871.211, "action": "Shots off target", "team": "away"},
  {"t": 5923.776, "action": "Ball out of play", "team": "none"},
  {"t": 5943.758, "action": "Throw-in", "team": "away"},
  {"t": 5961.733, "action": "Ball out of play", "team": "none"},
  {"t": 5988.085, "action": "Clearance", "team": "home"},
  {"t": 6037.116, "action": "Offside", "team": "home"},
  {"t": 6136.752, "action": "Throw-in", "team": "home"},
  {"t": 6159.859, "action": "Shots on target", "team": "home"},
  {"t": 6160.417, "action": "Goal", "team": "home"},
]


def _num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x else None  # NaN is not a time


def _norm(e):
    """One entry as {"t", "action", "team"}, with None for any field that cannot be read."""
    if not isinstance(e, dict):
        return {"t": None, "action": None, "team": None}
    name = " ".join(str(e.get("action", "")).split()).lower().replace("→", "->")
    team = " ".join(str(e.get("team", "")).split()).lower()
    return {"t": _num(e.get("t")), "action": _CANON.get(name) or _ALIASES.get(name),
            "team": _TEAMS.get(team)}


def _groups(entries, with_team):
    out = {}
    for e in entries:
        if e["t"] is None or e["action"] is None or (with_team and e["team"] is None):
            continue
        out.setdefault((e["action"], e["team"]) if with_team else e["action"], []).append(e["t"])
    return {k: sorted(v) for k, v in out.items()}


def _matches(pred_times, key_times, tol=TOL):
    """Size of a largest one-to-one matching of two sorted time lists, |dt| <= tol."""
    i = j = n = 0
    while i < len(pred_times) and j < len(key_times):
        d = pred_times[i] - key_times[j]
        if abs(d) <= tol:
            n, i, j = n + 1, i + 1, j + 1
        elif d < 0:
            i += 1
        else:
            j += 1
    return n


def score(entries, key=None):
    """The mean over the key's classes of each class's F1, with the counts behind it."""
    key = GROUND_TRUTH if key is None else key
    preds = [_norm(e) for e in entries]
    gold = [_norm(e) for e in key]
    pg, kg = _groups(preds, True), _groups(gold, True)
    tp = sum(_matches(pg.get(k, []), v) for k, v in kg.items())
    pa, ka = _groups(preds, False), _groups(gold, False)
    action_time = sum(_matches(pa.get(k, []), v) for k, v in ka.items())
    n_pred, n_gt = len(preds), len(gold)
    per_action, class_f1 = {}, []
    for a in ACTIONS:
        n_key = sum(len(v) for (act, _), v in kg.items() if act == a)
        n_p = sum(1 for p in preds if p["action"] == a)
        if n_key or n_p:
            matched = sum(_matches(pg.get((act, team), []), v)
                          for (act, team), v in kg.items() if act == a)
            f = 2 * matched / (n_key + n_p)
            per_action[a] = {"key": n_key, "predicted": n_p, "matched": matched, "f1": round(f, 4)}
            if n_key:
                class_f1.append(f)
    f1 = sum(class_f1) / len(class_f1) if class_f1 else 0.0
    return {
        "f1": round(f1, 4), "classes_in_key": len(class_f1),
        "n_predicted": n_pred, "n_ground_truth": n_gt, "true_positives": tp,
        "action_time_matches": action_time,
        "unreadable_entries": sum(1 for p in preds if None in p.values()),
        "per_action": per_action,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", required=True, type=Path)
    ap.add_argument("--reward-json", required=True, type=Path)
    ap.add_argument("--reward-txt", required=True, type=Path)
    args = ap.parse_args()

    reason, raw = "ok", []
    try:
        sol = json.loads(args.solution.read_text())
        raw = sol.get("sequence", []) if isinstance(sol, dict) else sol
        if not isinstance(raw, list):
            raise ValueError("sequence is not a list")
    except Exception as exc:  # noqa: BLE001 - malformed output scores 0
        reason, raw = f"unreadable solution.json: {exc}", []

    details = {"reason": reason, **score(raw), "time_tolerance_s": TOL}
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps({"reward": details["f1"], "details": details}, indent=2))
    args.reward_txt.write_text(f"{details['f1']}\n")


if __name__ == "__main__":
    main()
