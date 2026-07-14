#!/usr/bin/env python3
"""Grade an ace-and-block-timeline reconstruction. Pure Python stdlib, deterministic.

The agent must list every point that ended as a service ace or a block, with set,
exact score after the point, event type, and the credited player(s). Scoring is
two-tier:

  * full credit (1.0)    — set, score_after, type, AND the exact credited-player
    multiset all match;
  * partial credit (0.5) — set, score_after, and type match and the credited
    players differ by exactly one name (one missing, one extra, or one wrong).

The partial tier exists because block credit (solo vs shared, and exactly who gets
the assist) is a stats-crew ruling a perfect visual agent can legitimately miss in
the sub-second window at the net. reward = F1 over summed credit (misses and false
positives both hurt). Exact matches are assigned in a first pass so a partial match
can never steal a slot from an exact one.

Why this task and metric: a four-set match has ~170 rallies and only 24 of them end
as an ace or a block. The score bug says a point was scored, never why or by whom —
classifying a rally ending and identifying blockers by jersey number inside a
sub-second window at the net is genuine volleyball understanding. Scores increase
monotonically within a set, so the exact score-after string anchors each event
uniquely (this task's game clock); duplicates are handled by greedy one-to-one
multiset matching.
"""
import argparse
import json
import re
from pathlib import Path

# Official record: 24 events (5 aces — all BYU — and 19 block points, BYU 8 / WSU 11),
# 2023-09-08, BYU at Washington State (18-25, 25-19, 25-21, 25-19 from WSU's side).
# Extracted from the official NCAA rally-by-rally log (stats.ncaa.org contest
# 3241315) and reconciled per player against the official box score: every SA, block
# solo, and block assist column matches this list exactly (team block points
# BS + BA/2 = 8 and 11). Scores are written BYU-WSU as on the broadcast graphic.
GROUND_TRUTH = [
  {"set": 1, "score_after": "7-7",   "type": "ace",   "players": ["Erin Livingston"]},
  {"set": 1, "score_after": "16-13", "type": "ace",   "players": ["Erin Livingston"]},
  {"set": 1, "score_after": "18-14", "type": "block", "players": ["Whitney McEwan-Llarenas", "Elyse Stowell"]},
  {"set": 1, "score_after": "18-17", "type": "block", "players": ["Argentina Ung", "Magda Jehlarova"]},
  {"set": 1, "score_after": "20-17", "type": "ace",   "players": ["Aria McComber"]},
  {"set": 2, "score_after": "1-2",   "type": "block", "players": ["Magda Jehlarova"]},
  {"set": 2, "score_after": "9-6",   "type": "block", "players": ["Kate Prior", "Mia Lee"]},
  {"set": 2, "score_after": "10-10", "type": "block", "players": ["Pia Timmer", "Lana Radakovic"]},
  {"set": 2, "score_after": "10-11", "type": "block", "players": ["Katy Ryan", "Lana Radakovic"]},
  {"set": 3, "score_after": "6-7",   "type": "block", "players": ["Lana Radakovic"]},
  {"set": 3, "score_after": "11-15", "type": "block", "players": ["Magda Jehlarova"]},
  {"set": 3, "score_after": "12-18", "type": "block", "players": ["Iman Isanovic", "Magda Jehlarova"]},
  {"set": 3, "score_after": "14-18", "type": "block", "players": ["Whitney Bower", "Whitney McEwan-Llarenas"]},
  {"set": 3, "score_after": "18-22", "type": "block", "players": ["Katy Ryan", "Lana Radakovic"]},
  {"set": 3, "score_after": "21-23", "type": "ace",   "players": ["Whitney Bower"]},
  {"set": 4, "score_after": "2-0",   "type": "block", "players": ["Whitney McEwan-Llarenas", "Erin Livingston"]},
  {"set": 4, "score_after": "6-6",   "type": "block", "players": ["Kate Prior"]},
  {"set": 4, "score_after": "6-9",   "type": "block", "players": ["Magda Jehlarova"]},
  {"set": 4, "score_after": "11-18", "type": "block", "players": ["Katy Ryan", "Magda Jehlarova"]},
  {"set": 4, "score_after": "13-18", "type": "ace",   "players": ["Whitney Bower"]},
  {"set": 4, "score_after": "16-23", "type": "block", "players": ["Eden Bower", "Whitney McEwan-Llarenas"]},
  {"set": 4, "score_after": "17-23", "type": "block", "players": ["Eden Bower"]},
  {"set": 4, "score_after": "18-23", "type": "block", "players": ["Kate Prior", "Whitney McEwan-Llarenas"]},
  {"set": 4, "score_after": "19-25", "type": "block", "players": ["Argentina Ung", "Lana Radakovic"]},
]

PARTIAL_CREDIT = 0.5  # right rally and type, credited players off by one

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


# Lastnames that are unique among GT players can be matched on lastname alone.
# Whitney Bower and Eden Bower share a lastname, so "Bower" alone never matches —
# the full name is required for either of them.
def _lastname(name):
    return norm(name.split()[-1]) if str(name).split() else norm(name)


_GT_NAMES = sorted({n for g in GROUND_TRUTH for n in g["players"]})
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
                "players": pr.get("players")}

    parsed = [parse(pr) for pr in preds]

    def anchor_match(p, gt):
        return p["set"] == gt["set"] and p["score"] == gt["score_after"] \
            and p["type"] == gt["type"]

    used = [False] * len(GROUND_TRUTH)
    consumed = [False] * len(parsed)
    full = 0
    # pass 1: exact matches (anchor + exact player multiset) so partials never
    # steal exact slots
    for j, p in enumerate(parsed):
        if p is None:
            continue
        for i, gt in enumerate(GROUND_TRUTH):
            if not used[i] and anchor_match(p, gt) \
                    and players_exact(p["players"], gt["players"]):
                used[i] = True
                consumed[j] = True
                full += 1
                break
    # pass 2: anchor match with credited players off by one, at partial credit
    partial = 0
    for j, p in enumerate(parsed):
        if p is None or consumed[j]:
            continue
        for i, gt in enumerate(GROUND_TRUTH):
            if not used[i] and anchor_match(p, gt) \
                    and players_off_by_one(p["players"], gt["players"]):
                used[i] = True
                consumed[j] = True
                partial += 1
                break

    # diagnostic: right rally found (set + score + type), players aside
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
        "partial_matches_players_off_by_one": partial,
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
