#!/usr/bin/env python3
"""Grade a soccer ball-restart-outcome timeline. Pure Python stdlib, deterministic.

The agent must list every visible ball restart in a full 90-minute broadcast as a
tuple (t, restart_type, team, outcome). A predicted restart is a true positive only
when it FULLY reconstructs the play: same restart_type, same taking team, same
outcome, and a clip time within TOL seconds of the true restart, under an
order-preserving one-to-one alignment. We score by F1 (misses and false positives
both hurt). reward = F1.

Why this task and metric: a full match has ~70 restarts scattered across 90 minutes.
No broadcast graphic lists them, none are memorizable, and judging each outcome means
watching the ensuing 15-30 s of play, so only genuinely reconstructing the match off
the video scores. The oracle (exact list) -> 1.0; an empty or guessed list -> ~0; a
strong agent that finds only a handful of the restarts and mostly mis-attributes
team/outcome -> well below 0.1.

Encodings (as stated to the agent in instruction.md):
  restart_type: 1=Throw-in, 2=Corner, 3=Direct free-kick, 4=Indirect free-kick
  team:         "home" | "away"   (home = the team named first in the score graphic)
  outcome:      2 if a goal follows within 30 s of the restart (either side), else 1
                if a shot (on or off target) follows within 15 s, else 0

Ground truth is a deterministic transform of SoccerNet-v2's published, multi-annotator
Labels-v2.json for this match (Borussia Dortmund vs Bayer 04 Leverkusen, 2016-17
Bundesliga): per restart event, (position, label, team) give (t, restart_type, team),
with position placed on the clip by one measured offset per half; outcome is a forward
scan of the same log. It is the verified answer key, not an echo of the input, and the
agent never sees it.
"""
import argparse
import json
from pathlib import Path

TOL = 3  # seconds of clip-time tolerance for a restart to count as localized

# t is seconds from the start of the clip (half 1 spans about [350, 3223], half 2 about [3399, 6209]).
GROUND_TRUTH = [
  {"t": 405.726, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 453.896, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 515.746, "restart_type": 2, "team": "home", "outcome": 0},
  {"t": 625.943, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 757.165, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 775.113, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 1009.957, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 1058.491, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 1201.139, "restart_type": 2, "team": "away", "outcome": 0},
  {"t": 1310.044, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 1339.997, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 1355.826, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 1450.05, "restart_type": 2, "team": "away", "outcome": 0},
  {"t": 1487.201, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 1584.911, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 1646.706, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 1678.63, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 1784.011, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 1814.224, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 1825.486, "restart_type": 1, "team": "home", "outcome": 1},
  {"t": 1864.224, "restart_type": 2, "team": "home", "outcome": 0},
  {"t": 1894.771, "restart_type": 2, "team": "home", "outcome": 2},
  {"t": 1996.414, "restart_type": 4, "team": "away", "outcome": 1},
  {"t": 2018.828, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 2112.089, "restart_type": 2, "team": "away", "outcome": 1},
  {"t": 2143.09, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 2200.978, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 2293.96, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 2319.881, "restart_type": 1, "team": "home", "outcome": 1},
  {"t": 2358.69, "restart_type": 2, "team": "home", "outcome": 0},
  {"t": 2439.967, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 2473.459, "restart_type": 4, "team": "away", "outcome": 0},
  {"t": 2773.234, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 2817.521, "restart_type": 4, "team": "away", "outcome": 0},
  {"t": 2848.438, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3014.277, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3057.023, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 3074.818, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3201.248, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3434.002, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 3442.937, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3453.286, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3678.193, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 3698.519, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3712.084, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3770.049, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 3820.11, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 4033.683, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 4056.35, "restart_type": 4, "team": "away", "outcome": 0},
  {"t": 4093.585, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 4112.637, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 4297.714, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 4330.844, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 4435.286, "restart_type": 4, "team": "away", "outcome": 0},
  {"t": 4501.839, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 4555.612, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 4667.503, "restart_type": 2, "team": "home", "outcome": 0},
  {"t": 4827.26, "restart_type": 4, "team": "home", "outcome": 2},
  {"t": 4925.358, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 4938.348, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 5004.35, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 5121.285, "restart_type": 3, "team": "away", "outcome": 2},
  {"t": 5161.271, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 5193.195, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 5268.224, "restart_type": 4, "team": "home", "outcome": 2},
  {"t": 5369.053, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 5392.451, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 5477.345, "restart_type": 2, "team": "home", "outcome": 0},
  {"t": 5697.715, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 5836.329, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 5943.758, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 6136.752, "restart_type": 1, "team": "home", "outcome": 2},
]


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _norm(e):
    """Normalize one predicted entry to (t, restart_type, team, outcome) or None."""
    if not isinstance(e, dict):
        return None
    t = _num(e.get("t", e.get("t_start")))
    rt = e.get("restart_type")
    oc = e.get("outcome")
    team = e.get("team")
    try:
        rt = None if rt is None else int(rt)
        oc = None if oc is None else int(oc)
    except (TypeError, ValueError):
        return None
    return {
        "t": t,
        "restart_type": rt,
        "team": None if team is None else str(team).strip().lower(),
        "outcome": oc,
    }


def _match(p, g):
    if p is None or p["t"] is None:
        return False
    return (
        p["restart_type"] == g["restart_type"]
        and p["team"] == g["team"]
        and p["outcome"] == g["outcome"]
        and abs(p["t"] - g["t"]) <= TOL
    )


def _match_loose(p, g):
    # diagnostic: right restart_type + team + time, ignoring outcome
    if p is None or p["t"] is None:
        return False
    return (
        p["restart_type"] == g["restart_type"]
        and p["team"] == g["team"]
        and abs(p["t"] - g["t"]) <= TOL
    )


def _max_monotonic(preds, matcher):
    """Largest order-preserving one-to-one matching (LCS-style DP). preds is scored
    in the order given, so ordering errors are penalized; GT is chronological."""
    n, m = len(preds), len(GROUND_TRUTH)
    if n == 0 or m == 0:
        return 0
    prev = [0] * (m + 1)
    for i in range(1, n + 1):
        cur = [0] * (m + 1)
        pi = preds[i - 1]
        for j in range(1, m + 1):
            best = cur[j - 1] if cur[j - 1] > prev[j] else prev[j]
            if matcher(pi, GROUND_TRUTH[j - 1]):
                cand = prev[j - 1] + 1
                if cand > best:
                    best = cand
            cur[j] = best
        prev = cur
    return prev[m]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", required=True, type=Path)
    ap.add_argument("--reward-json", required=True, type=Path)
    ap.add_argument("--reward-txt", required=True, type=Path)
    args = ap.parse_args()

    reason = "ok"
    raw = []
    try:
        sol = json.loads(args.solution.read_text())
        raw = sol.get("sequence", sol.get("instances", sol.get("restarts", [])))
        if not isinstance(raw, list):
            raise ValueError("sequence is not a list")
    except Exception as exc:  # noqa: BLE001 - malformed output scores 0
        reason, raw = f"unreadable solution.json: {exc}", []

    preds = [_norm(e) for e in raw]

    tp = _max_monotonic(preds, _match)
    tp_loose = _max_monotonic(preds, _match_loose)

    n_pred, n_gt = len(preds), len(GROUND_TRUTH)
    precision = tp / n_pred if n_pred else 0.0
    recall = tp / n_gt if n_gt else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    details = {
        "reason": reason,
        "n_ground_truth": n_gt,
        "n_predicted": n_pred,
        "true_positives_full_play": tp,
        "type_team_time_only_matches": tp_loose,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "time_tolerance_s": TOL,
    }
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps({"reward": round(f1, 4), "details": details}, indent=2))
    args.reward_txt.write_text(f"{round(f1, 4)}\n")


if __name__ == "__main__":
    main()
