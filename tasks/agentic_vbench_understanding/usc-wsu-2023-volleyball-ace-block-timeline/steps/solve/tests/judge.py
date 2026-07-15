#!/usr/bin/env python3
"""Grade an ace-and-block-timeline reconstruction. Pure Python stdlib, deterministic.

The agent must list every point that ended as a service ace or a block. For an ace it
reports the set, the score after the point, and the server. For a block it reports the
set, the score after the point, the credited blocker(s), AND the opposing hitter who
was blocked. Scoring is two-tier:

  * full credit (1.0)    — set, score_after, type, and every credited name match
    (for a block: the exact blocker multiset AND the blocked hitter);
  * partial credit (0.5) — set, score_after, and type match and the credited names
    are off by exactly one (a blocker missing/extra/wrong, or the blocked hitter
    wrong) while everything else is correct.

The partial tier exists because block credit (solo vs shared, who gets the assist)
and reading a stuffed hitter's number in the sub-second window at the net are things
a perfect visual agent can legitimately miss. reward = F1 over summed credit (misses
and false positives both hurt). Exact matches are assigned in a first pass so a
partial match can never steal a slot from an exact one.

Why the blocked hitter: a block point requires identifying not just the blocker(s)
but the opposing attacker who was stuffed — a second jersey read at the net, from a
different team, at the terminal moment. The score bug says a point was scored, never
why or by whom; scores increase monotonically within a set, so the exact score-after
string anchors each event uniquely (this task's game clock). Duplicates are handled
by greedy one-to-one multiset matching.
"""
import argparse
import json
import re
from pathlib import Path

# Official record: 28 events (5 aces — USC 1 / WSU 4 — and 23 block points,
# USC 10 / WSU 13), 2023-11-12, #25 Southern California at #9 Washington State, a
# five-set match WSU won 3-2 (15-25, 16-25, 25-16, 27-25, 15-11). Extracted from the
# official NCAA rally-by-rally log (stats.ncaa.org contest 3252428) and reconciled
# per player against the official box score: every SA, block-solo, and block-assist
# column matches this list exactly — aces USC 1 / WSU 4, Block Solos 3 / 3, Block
# Assists 14 / 20, so team block points BS + BA/2 = 10 (USC) and 13 (WSU). Each
# block also carries `blocked`, the opposing hitter who was stuffed (the "Attack by
# X" immediately preceding the terminal "Block by ..." rally line, direction-verified:
# the hitter is always on the team opposite the blockers). "Kill by X, Block by Y"
# rally lines are attacker kills through a block touch, not block points, and are
# excluded. Scores are written USC-WSU (visitor-home) as on the broadcast graphic.
# Unlike the sister BYU match, no rally line here is corrupted, so every block has a
# recoverable blocked hitter (the None branch below is retained but unused).
GROUND_TRUTH = [
  {"set": 1, "score_after": "4-2",       "type": "block", "players": ["Mia Tuaniga", "Lindsey Miller"],                         "blocked": "Iman Isanovic"},
  {"set": 1, "score_after": "14-10",     "type": "block", "players": ["Lindsey Miller"],                                        "blocked": "Magda Jehlarova"},
  {"set": 1, "score_after": "23-15",     "type": "block", "players": ["Tyrah Ariail", "Kalyah Williams"],                       "blocked": "Katy Ryan"},
  {"set": 1, "score_after": "25-15",     "type": "block", "players": ["Kalyah Williams", "Tyrah Ariail"],                       "blocked": "Iman Isanovic"},
  {"set": 2, "score_after": "2-1",       "type": "block", "players": ["Lindsey Miller", "Skylar Fields"],                       "blocked": "Pia Timmer"},
  {"set": 2, "score_after": "10-7",      "type": "block", "players": ["Tyrah Ariail"],                                          "blocked": "Katy Ryan"},
  {"set": 2, "score_after": "16-10",     "type": "block", "players": ["Magda Jehlarova", "Argentina Ung"],                      "blocked": "Skylar Fields"},
  {"set": 3, "score_after": "0-1",       "type": "ace",   "players": ["Lana Radakovic"]},
  {"set": 3, "score_after": "1-6",       "type": "block", "players": ["Magda Jehlarova", "Argentina Ung"],                      "blocked": "Skylar Fields"},
  {"set": 3, "score_after": "4-7",       "type": "block", "players": ["London Wijay", "Lindsey Miller"],                        "blocked": "Magda Jehlarova"},
  {"set": 3, "score_after": "7-10",      "type": "block", "players": ["Tyrah Ariail"],                                          "blocked": "Iman Isanovic"},
  {"set": 3, "score_after": "11-13",     "type": "ace",   "players": ["Tyrah Ariail"]},
  {"set": 3, "score_after": "13-17",     "type": "block", "players": ["Magda Jehlarova", "Argentina Ung"],                      "blocked": "London Wijay"},
  {"set": 3, "score_after": "16-24",     "type": "ace",   "players": ["Lana Radakovic"]},
  {"set": 3, "score_after": "16-25",     "type": "block", "players": ["Magda Jehlarova"],                                       "blocked": "Tyrah Ariail"},
  {"set": 4, "score_after": "1-1",       "type": "block", "players": ["Katy Ryan", "Magda Jehlarova"],                          "blocked": "Skylar Fields"},
  {"set": 4, "score_after": "3-3",       "type": "block", "players": ["Magda Jehlarova", "Argentina Ung"],                      "blocked": "Skylar Fields"},
  {"set": 4, "score_after": "7-5",       "type": "block", "players": ["Lana Radakovic", "Argentina Ung"],                       "blocked": "London Wijay"},
  {"set": 4, "score_after": "10-8",      "type": "block", "players": ["Katy Ryan", "Lana Radakovic"],                           "blocked": "London Wijay"},
  {"set": 4, "score_after": "16-17",     "type": "block", "players": ["Pia Timmer"],                                            "blocked": "Skylar Fields"},
  {"set": 4, "score_after": "19-20",     "type": "block", "players": ["Katy Ryan", "Magda Jehlarova"],                          "blocked": "Kalyah Williams"},
  {"set": 5, "score_after": "3-3",       "type": "block", "players": ["Magda Jehlarova", "Iman Isanovic"],                      "blocked": "Kalyah Williams"},
  {"set": 5, "score_after": "3-4",       "type": "ace",   "players": ["Julia Norville"]},
  {"set": 5, "score_after": "3-7",       "type": "block", "players": ["Magda Jehlarova", "Argentina Ung"],                      "blocked": "Skylar Fields"},
  {"set": 5, "score_after": "5-8",       "type": "block", "players": ["Mia Tuaniga", "Rylie McGinest"],                         "blocked": "Pia Timmer"},
  {"set": 5, "score_after": "5-11",      "type": "block", "players": ["Argentina Ung"],                                         "blocked": "London Wijay"},
  {"set": 5, "score_after": "5-12",      "type": "ace",   "players": ["Karly Basham"]},
  {"set": 5, "score_after": "10-14",     "type": "block", "players": ["Tyrah Ariail", "London Wijay"],                          "blocked": "Iman Isanovic"},
]

PARTIAL_CREDIT = 0.5  # right rally and type, credited names off by exactly one

TYPE_ALIASES = {"service_ace": "ace", "service ace": "ace", "stuff": "block",
                "block_point": "block", "block point": "block"}


def norm(s):
    return re.sub(r"[^a-z]", "", str(s).lower())


def norm_type(s):
    key = str(s).strip().lower()
    return TYPE_ALIASES.get(key, key)


def norm_score(s):
    digits = re.findall(r"\d+", str(s))
    return "-".join(digits) if len(digits) == 2 else None


# Lastnames that are unique among GT players can be matched on lastname alone. In
# this match every GT lastname is unique (no two credited players share one), so a
# correct lastname alone resolves a name; the guard still fires automatically if a
# future edit introduces a collision.
def _lastname(name):
    return norm(name.split()[-1]) if str(name).split() else norm(name)


_GT_NAMES = sorted({n for g in GROUND_TRUTH
                    for n in (g["players"] + ([g["blocked"]] if g.get("blocked") else []))})
_GT_LASTS = [_lastname(n) for n in _GT_NAMES]
_UNIQUE_LASTS = {ln for ln in _GT_LASTS if _GT_LASTS.count(ln) == 1}


def name_match(pred, gt_full):
    p, g = norm(pred), norm(gt_full)
    if not p:
        return False
    if p == g:
        return True
    gl = _lastname(gt_full)
    return gl in _UNIQUE_LASTS and p == gl  # lastname only if unambiguous


def matched_names(pred_list, gt_list):
    """Greedy one-to-one count of predicted names that match ground-truth names."""
    if not isinstance(pred_list, list):
        return -1
    remaining = list(gt_list)
    m = 0
    for p in pred_list:
        for g in remaining:
            if name_match(p, g):
                remaining.remove(g)
                m += 1
                break
    return m


def players_exact(pred_list, gt_list):
    return isinstance(pred_list, list) and len(pred_list) == len(gt_list) \
        and matched_names(pred_list, gt_list) == len(gt_list)


def players_off_by_one(pred_list, gt_list):
    """One name missing, one extra, or one wrong — everything else matched."""
    if not isinstance(pred_list, list) or not pred_list:
        return False
    m = matched_names(pred_list, gt_list)
    if m < 1 or m < len(gt_list) - 1:
        return False
    if abs(len(pred_list) - len(gt_list)) > 1:
        return False
    return not players_exact(pred_list, gt_list)


def blocked_ok(pred_blocked, gt_blocked):
    # The one corrupted-PBP event has gt_blocked None -> not required.
    return gt_blocked is None or name_match(pred_blocked, gt_blocked)


def event_grade(p, gt):
    """Return 'full', 'partial', or None for a prediction p against GT event gt
    (anchor set+score+type already matched by the caller)."""
    if gt["type"] == "ace":
        if players_exact(p["players"], gt["players"]):
            return "full"
        if players_off_by_one(p["players"], gt["players"]):
            return "partial"
        return None
    # block: blockers (players) + blocked hitter
    blk_exact = players_exact(p["players"], gt["players"])
    hit_ok = blocked_ok(p.get("blocked"), gt.get("blocked"))
    if blk_exact and hit_ok:
        return "full"
    # exactly one thing off: blockers off-by-one (hitter right), or hitter wrong
    # (blockers exact). gt_blocked None can't be "wrong", so that branch needs a
    # real blocker error to be partial.
    if players_off_by_one(p["players"], gt["players"]) and hit_ok:
        return "partial"
    if blk_exact and gt.get("blocked") is not None and not hit_ok:
        return "partial"
    return None


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
        preds = sol.get("events", [])
        if not isinstance(preds, list):
            raise ValueError("events is not a list")
    except Exception as exc:  # noqa: BLE001 - malformed output scores 0
        reason, preds = f"unreadable solution.json: {exc}", []

    def parse(pr):
        if not isinstance(pr, dict):
            return None
        try:
            st = int(pr.get("set"))
        except (TypeError, ValueError):
            return None
        sc = norm_score(pr.get("score_after", ""))
        if sc is None:
            return None
        return {"set": st, "score": sc, "type": norm_type(pr.get("type", "")),
                "players": pr.get("players"), "blocked": pr.get("blocked")}

    parsed = [parse(pr) for pr in preds]

    def anchor_match(p, gt):
        return p["set"] == gt["set"] and p["score"] == gt["score_after"] \
            and p["type"] == gt["type"]

    used = [False] * len(GROUND_TRUTH)
    consumed = [False] * len(parsed)
    full = 0
    # pass 1: exact matches so partials never steal an exact slot
    for j, p in enumerate(parsed):
        if p is None:
            continue
        for i, gt in enumerate(GROUND_TRUTH):
            if not used[i] and anchor_match(p, gt) and event_grade(p, gt) == "full":
                used[i] = True
                consumed[j] = True
                full += 1
                break
    # pass 2: partial matches
    partial = 0
    for j, p in enumerate(parsed):
        if p is None or consumed[j]:
            continue
        for i, gt in enumerate(GROUND_TRUTH):
            if not used[i] and anchor_match(p, gt) and event_grade(p, gt) == "partial":
                used[i] = True
                consumed[j] = True
                partial += 1
                break

    # diagnostic: right rally found (set + score + type), attribution aside
    used_loose = [False] * len(GROUND_TRUTH)
    anchor_only = 0
    for p in parsed:
        if p is None:
            continue
        for i, gt in enumerate(GROUND_TRUTH):
            if not used_loose[i] and anchor_match(p, gt):
                used_loose[i] = True
                anchor_only += 1
                break

    credit = full + PARTIAL_CREDIT * partial
    n_pred, n_gt = len(preds), len(GROUND_TRUTH)
    precision = credit / n_pred if n_pred else 0.0
    recall = credit / n_gt if n_gt else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    details = {
        "reason": reason,
        "n_ground_truth": n_gt,
        "n_predicted": n_pred,
        "full_matches": full,
        "partial_matches": partial,
        "credit": round(credit, 4),
        "set_score_type_only_matches": anchor_only,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "partial_credit": PARTIAL_CREDIT,
    }
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps({"reward": round(f1, 4), "details": details}, indent=2))
    args.reward_txt.write_text(f"{round(f1, 4)}\n")


if __name__ == "__main__":
    main()
