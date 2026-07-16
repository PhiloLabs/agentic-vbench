#!/usr/bin/env python3
"""Grade a soccer ball-restart-outcome timeline. Pure Python stdlib, deterministic.

The agent must list every visible ball restart in a full 90-minute broadcast as a
tuple (t, restart_type, team, outcome). A predicted restart is a true positive only
when it FULLY reconstructs the play: same restart_type, same taking team, same
outcome, and a clip time within TOL seconds of the true restart, under an
order-preserving one-to-one alignment. We score by F1 (misses and false positives
both hurt). reward = F1.

Why this task and metric: a full match has ~80 restarts scattered across 90 minutes.
No broadcast graphic lists them, none are memorizable, and judging each outcome means
watching the ensuing 15-30 s of play, so only genuinely reconstructing the match off
the video scores. The oracle (exact list) -> 1.0; an empty or guessed list -> ~0; a
strong agent that finds only a handful of the restarts and mostly mis-attributes
team/outcome -> well below 0.1.

Encodings (as stated to the agent in instruction.md):
  restart_type: 1=Throw-in, 2=Corner, 3=Direct free-kick, 4=Indirect free-kick
  team:         "home" | "away"   (home = the side defending the scoreboard's left)
  outcome:      2 if a goal follows within 30 s of the restart (either side), else 1
                if a shot (on or off target) follows within 15 s, else 0

Ground truth is a deterministic transform of SoccerNet-v2's published, multi-annotator
Labels-v2.json for this match (Mainz 05 vs Borussia Dortmund, 2016-17 Bundesliga):
per restart event, (position, label, team) give (t, restart_type, team); outcome is a
forward scan of the same log. It is the verified answer key, not an echo of the input,
and the agent never sees it.
"""
import argparse
import json
from pathlib import Path

TOL = 3  # seconds of clip-time tolerance for a restart to count as localized

# t is seconds into the concatenated broadcast (half 1 = [0, 2699], half 2 = [2700, ...]).
GROUND_TRUTH = [
  {"t": 36.171, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 255.898, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 314.496, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 455.242, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 478.831, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 572.604, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 678.191, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 800.305, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 827.71, "restart_type": 2, "team": "home", "outcome": 0},
  {"t": 907.559, "restart_type": 4, "team": "away", "outcome": 0},
  {"t": 994.675, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 1229.914, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 1265.495, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 1299.418, "restart_type": 4, "team": "away", "outcome": 0},
  {"t": 1361.803, "restart_type": 3, "team": "away", "outcome": 1},
  {"t": 1523.462, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 1550.744, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 1674.561, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 1697.925, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 1768.753, "restart_type": 2, "team": "away", "outcome": 0},
  {"t": 1789.38, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 1831.929, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 1852.939, "restart_type": 1, "team": "home", "outcome": 1},
  {"t": 2013.876, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 2058.524, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 2312.689, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 2323.566, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 2342.905, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 2518.78, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 2541.112, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 2587.209, "restart_type": 2, "team": "away", "outcome": 1},
  {"t": 2619.248, "restart_type": 2, "team": "away", "outcome": 1},
  {"t": 2679.026, "restart_type": 4, "team": "away", "outcome": 0},
  {"t": 2739.665, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 2746.51, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 2881.81, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 2911.357, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 2949.002, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 2964.613, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 2984.139, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3121.791, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 3169.752, "restart_type": 3, "team": "home", "outcome": 1},
  {"t": 3207.901, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3286.212, "restart_type": 4, "team": "away", "outcome": 0},
  {"t": 3331.83, "restart_type": 2, "team": "home", "outcome": 1},
  {"t": 3386.185, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 3403.086, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 3429.644, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3459.781, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3482.832, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 3512.341, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3569.955, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3578.975, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3594.814, "restart_type": 1, "team": "away", "outcome": 1},
  {"t": 3640.861, "restart_type": 2, "team": "away", "outcome": 1},
  {"t": 3701.565, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 3770.962, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 3984.571, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 4000.584, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 4063.635, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 4129.846, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 4147.889, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 4180.445, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 4186.105, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 4238.853, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 4299.588, "restart_type": 1, "team": "home", "outcome": 1},
  {"t": 4325.987, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 4467.823, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 4548.551, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 4615.747, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 4645.91, "restart_type": 1, "team": "away", "outcome": 1},
  {"t": 4698.201, "restart_type": 4, "team": "away", "outcome": 0},
  {"t": 4743.767, "restart_type": 4, "team": "away", "outcome": 0},
  {"t": 4757.489, "restart_type": 1, "team": "away", "outcome": 0},
  {"t": 4809.703, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 4920.136, "restart_type": 3, "team": "away", "outcome": 2},
  {"t": 5046.555, "restart_type": 4, "team": "away", "outcome": 0},
  {"t": 5187.961, "restart_type": 1, "team": "home", "outcome": 0},
  {"t": 5242.864, "restart_type": 3, "team": "away", "outcome": 0},
  {"t": 5307.401, "restart_type": 4, "team": "home", "outcome": 0},
  {"t": 5387.647, "restart_type": 1, "team": "home", "outcome": 0},
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
