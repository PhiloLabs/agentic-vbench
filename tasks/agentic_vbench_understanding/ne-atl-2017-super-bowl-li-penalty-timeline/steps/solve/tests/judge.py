#!/usr/bin/env python3
"""Grade a Super Bowl LI referee-announced player-foul timeline. Pure stdlib, deterministic.

The agent lists every referee-announced player foul with quarter, game clock, infraction
type, penalised player's jersey number, and team. A prediction is a true positive only
when it FULLY reconstructs the foul: same type, same jersey number, same team, same
quarter, and a game clock within CLOCK_TOL seconds. reward = F1, so misses and
hallucinations both hurt.

Why cross-modal: the jersey number is stated only by the referee's microphone (audio),
and the game clock is shown only in the on-screen score bug (video). The infraction type
and team leak to OCR from the broadcast's penalty banner and carry no difficulty; the
compound match rests on number + clock, which live in different channels. Neither channel
alone yields a true positive.

Ground truth: the NFL official Game Book (nflgsis.com), cross-checked against
nflpenalties.com. Team fouls with no announced jersey number (delay of game, illegal
formation, etc.) are excluded by the task's scope rule.

NOTE: GROUND_TRUTH below is the PILOT subset — the four fouls whose announced jersey
numbers were verified by transcribing the broadcast audio. The full-game ground truth
(every referee announcement, per the maintainer's guidance) is pending an official Game
Book parse and will replace this list before calibration.
"""
import argparse
import json
import re
from pathlib import Path

CLOCK_TOL = 5  # seconds of game-clock tolerance

# Closed vocabulary of scored infraction types (normalised form).
VALID_TYPES = {
    "offensive holding", "defensive holding", "offensive pass interference",
    "defensive pass interference", "defensive offside", "false start",
    "unnecessary roughness", "roughing the passer", "illegal use of hands",
    "defensive holding", "illegal contact",
}

# --- PILOT ground truth: the 4 audio-verified fouls (see NOTE above). ---
GROUND_TRUTH = [
    {"quarter": 2, "clock": "8:02", "type": "defensive holding",           "player_number": 23, "team": "ATL"},
    {"quarter": 2, "clock": "5:16", "type": "defensive holding",           "player_number": 34, "team": "ATL"},
    {"quarter": 3, "clock": "1:30", "type": "offensive holding",           "player_number": 70, "team": "ATL"},
    {"quarter": 5, "clock": "11:18","type": "defensive pass interference", "player_number": 59, "team": "ATL"},
]


def norm_type(s):
    return re.sub(r"\s+", " ", str(s).strip().lower())


def clock_secs(cv):
    cv = str(cv).strip()
    try:
        if ":" in cv:
            m, s = cv.split(":")
            return int(m) * 60 + int(float(s))
        return int(float(cv))
    except (ValueError, AttributeError):
        return None


def as_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def matches(pred, gt):
    if norm_type(pred.get("type", "")) != norm_type(gt["type"]):
        return False
    if as_int(pred.get("player_number")) != gt["player_number"]:
        return False
    if str(pred.get("team", "")).strip().upper() != gt["team"]:
        return False
    if as_int(pred.get("quarter")) != gt["quarter"]:
        return False
    ps = clock_secs(pred.get("clock"))
    gs = clock_secs(gt["clock"])
    if ps is None or gs is None or abs(ps - gs) > CLOCK_TOL:
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", required=True, type=Path)
    ap.add_argument("--reward-json", required=True, type=Path)
    ap.add_argument("--reward-txt", required=True, type=Path)
    args = ap.parse_args()

    reason = "ok"
    preds = []
    try:
        sol = json.loads(args.solution.read_text())
        preds = sol.get("penalties", [])
        if not isinstance(preds, list):
            raise ValueError("penalties is not a list")
    except Exception as exc:  # noqa: BLE001 - malformed output scores 0
        reason, preds = f"unreadable solution.json: {exc}", []

    used = [False] * len(GROUND_TRUTH)
    tp = 0
    for pr in preds:
        if not isinstance(pr, dict):
            continue
        for i, gt in enumerate(GROUND_TRUTH):
            if not used[i] and matches(pr, gt):
                used[i] = True
                tp += 1
                break

    n_pred, n_gt = len(preds), len(GROUND_TRUTH)
    precision = tp / n_pred if n_pred else 0.0
    recall = tp / n_gt if n_gt else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    details = {
        "reason": reason,
        "n_ground_truth": n_gt,
        "n_predicted": n_pred,
        "true_positives": tp,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "clock_tolerance_s": CLOCK_TOL,
        "pilot_subset": True,
    }
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps({"reward": round(f1, 4), "details": details}, indent=2))
    args.reward_txt.write_text(f"{round(f1, 4)}\n")


if __name__ == "__main__":
    main()
