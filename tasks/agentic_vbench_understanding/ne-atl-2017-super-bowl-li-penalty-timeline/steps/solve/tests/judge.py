#!/usr/bin/env python3
"""Grade a Super Bowl LI referee-announced player-foul timeline. Pure stdlib, deterministic.

The agent lists every referee-announced player foul with quarter, game clock, infraction
type, penalised player's jersey number, and team. A prediction is a true positive only
when it FULLY reconstructs the foul: same type, same jersey number, same team, same
quarter, and a game clock within CLOCK_TOL seconds. reward = F-beta with BETA=2
(recall-weighted), so misses and hallucinations both hurt, but a single lucky true
positive no longer clears the anti-shortcut gate the way it did under plain F1 (one
exact row out of 13: F1 = 0.1429 > 0.10 gate, F2 = 0.0943 < 0.10 gate).

Why cross-modal: the jersey number is stated only by the referee's microphone (audio),
and the game clock is shown only in the on-screen score bug (video). The infraction type
and team leak to OCR from the broadcast's penalty banner and carry no difficulty; the
compound match rests on number + clock, which live in different channels. Neither channel
alone yields a true positive.

Ground truth: the NFL official Game Book (nflgsis.com), cross-checked against
nflpenalties.com. Team fouls with no announced jersey number (delay of game, illegal
formation, etc.) are excluded by the task's scope rule.

GROUND_TRUTH below is the full set of referee-announced player fouls, parsed from the
official NFL Game Book play-by-play, with jersey numbers taken from the Game Book
lineups/substitutions. Scope rule and the three documented exclusions (delay of game,
illegal formation, illegal touching — announced without a player number) are recorded
in PROVENANCE.md. Four of the numbers (#23 Alford, #34 Poole, #70 Matthews, #59
Campbell) were independently confirmed by transcribing the broadcast audio; all match
the official lineup.
"""
import argparse
import json
import re
from pathlib import Path

CLOCK_TOL = 5  # seconds of game-clock tolerance
BETA = 2  # F-beta weight: recall counted BETA^2x precision, per issue #60 review

# Closed vocabulary of scored infraction types (normalised form).
VALID_TYPES = {
    "offensive holding", "defensive holding", "offensive pass interference",
    "defensive pass interference", "defensive offside", "false start",
    "unnecessary roughness", "roughing the passer", "illegal use of hands",
    "defensive holding", "illegal contact",
}

# --- Full ground truth: referee-announced player fouls (official Game Book). ---
# quarter 5 = overtime. Both "accepted" and "declined" fouls are included (the referee
# announces the number either way); no-number fouls are excluded (see PROVENANCE.md).
GROUND_TRUTH = [
    {"quarter": 1, "clock": "13:47", "type": "offensive holding",           "player_number": 55, "team": "ATL"},  # Worrilow
    {"quarter": 2, "clock": "14:19", "type": "offensive holding",           "player_number": 88, "team": "NE"},   # Bennett (declined)
    {"quarter": 2, "clock": "8:55",  "type": "defensive pass interference", "player_number": 23, "team": "NE"},   # Chung (declined)
    {"quarter": 2, "clock": "8:02",  "type": "defensive holding",           "player_number": 23, "team": "ATL"},  # Alford
    {"quarter": 2, "clock": "6:10",  "type": "defensive holding",           "player_number": 34, "team": "ATL"},  # Poole
    {"quarter": 2, "clock": "5:16",  "type": "defensive holding",           "player_number": 34, "team": "ATL"},  # Poole
    {"quarter": 2, "clock": "0:18",  "type": "offensive holding",           "player_number": 88, "team": "NE"},   # Bennett
    {"quarter": 3, "clock": "13:02", "type": "offensive pass interference", "player_number": 15, "team": "NE"},   # Hogan (declined)
    {"quarter": 3, "clock": "8:43",  "type": "defensive pass interference", "player_number": 21, "team": "NE"},   # Butler
    {"quarter": 3, "clock": "1:30",  "type": "offensive holding",           "player_number": 70, "team": "ATL"},  # Matthews
    {"quarter": 4, "clock": "3:50",  "type": "offensive holding",           "player_number": 70, "team": "ATL"},  # Matthews
    {"quarter": 4, "clock": "0:57",  "type": "defensive offside",           "player_number": 93, "team": "ATL"},  # Freeney
    {"quarter": 5, "clock": "11:18", "type": "defensive pass interference", "player_number": 59, "team": "ATL"},  # Campbell
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
    beta_sq = BETA * BETA
    denom = beta_sq * precision + recall
    f_beta = ((1 + beta_sq) * precision * recall / denom) if denom else 0.0

    details = {
        "reason": reason,
        "n_ground_truth": n_gt,
        "n_predicted": n_pred,
        "true_positives": tp,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "beta": BETA,
        "f_beta": round(f_beta, 4),
        "clock_tolerance_s": CLOCK_TOL,
        "ground_truth_source": "official NFL Game Book",
    }
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps({"reward": round(f_beta, 4), "details": details}, indent=2))
    args.reward_txt.write_text(f"{round(f_beta, 4)}\n")


if __name__ == "__main__":
    main()
