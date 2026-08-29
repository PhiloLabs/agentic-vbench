#!/usr/bin/env python3
"""Grade a block-point-timeline reconstruction. Pure Python stdlib, deterministic.

The agent must list every point that ended as a block, and for each one report the
set, the score after the point, the credited blocker(s), the opposing hitter who was
blocked, and the setter who fed that attack. Scoring is two-tier:

  * full credit (1.0)    — set, score_after, the exact blocker multiset, the hitter
    who was blocked, AND the setter who fed that attack;
  * partial credit (0.5) — exactly one of those three attributions is wrong.

The partial tier exists because block credit (solo vs shared, who gets the assist)
and reading a stuffed hitter's number in the sub-second window at the net are things
a perfect visual agent can legitimately miss. reward = F1 over summed credit (misses
and false positives both hurt). Exact matches are assigned in a first pass so a
partial match can never steal a slot from an exact one.

Why three attributions: the blocker(s) and the stuffed hitter are two opposing jersey
reads at the terminal instant, and the setter is a third read that sits mid-rally,
before the attack — so it cannot be recovered from the post-point celebration and has
to be tracked back through the rally. The score bug says a point was scored, never
why or by whom; scores increase monotonically within a set, so the exact score-after
string anchors each event uniquely (this task's game clock). Duplicates are handled
by greedy one-to-one multiset matching.
"""
import argparse
import json
import re
from pathlib import Path

# Official record: 19 block points (BYU 8 / WSU 11), 2023-09-08, BYU at Washington
# State, a four-set match WSU won 3-1 (BYU took set 1, 25-18; WSU 25-19, 25-21,
# 25-19). Extracted from the official NCAA rally-by-rally log (stats.ncaa.org contest
# 3241315) and reconciled per player against the official box score: every block solo
# and block assist column matches, so team block points BS + BA/2 come out 8 and 11.
# Each block carries `blocked`, the opposing hitter who was stuffed (the "Attack by X"
# immediately preceding the "Block by ..." rally line, direction-verified: the hitter
# is always on the team opposite the blockers), and `setter`, the "Set by X" earlier
# in the same rally chain. Scores are written BYU-WSU as on the broadcast graphic.
#
# 18 of the 19 are in the key. One rally line (set 2 at 1-2, a WSU block point the box
# score resolves to a Jehlarova solo) is corrupted in the raw log — its name field
# credits a blocker on the scoring team's opponent, and neither the stuffed hitter nor
# the setter is recoverable from it — so that point carries no answerable attribution
# and is left out. The key is every block point whose three attributions the official
# record fixes unambiguously.
GROUND_TRUTH = [
  {"set": 1, "score_after": "18-14",     "type": "block", "players": ["Whitney McEwan-Llarenas", "Elyse Stowell"],              "blocked": "Katy Ryan", "setter": "Argentina Ung"},
  {"set": 1, "score_after": "18-17",     "type": "block", "players": ["Argentina Ung", "Magda Jehlarova"],                      "blocked": "Elyse Stowell", "setter": "Whitney Bower"},
  {"set": 2, "score_after": "9-6",       "type": "block", "players": ["Kate Prior", "Mia Lee"],                                 "blocked": "Iman Isanovic", "setter": "Argentina Ung"},
  {"set": 2, "score_after": "10-10",     "type": "block", "players": ["Pia Timmer", "Lana Radakovic"],                          "blocked": "Kate Prior", "setter": "Whitney Bower"},
  {"set": 2, "score_after": "10-11",     "type": "block", "players": ["Katy Ryan", "Lana Radakovic"],                           "blocked": "Elyse Stowell", "setter": "Whitney Bower"},
  {"set": 3, "score_after": "6-7",       "type": "block", "players": ["Lana Radakovic"],                                        "blocked": "Erin Livingston", "setter": "Whitney Bower"},
  {"set": 3, "score_after": "11-15",     "type": "block", "players": ["Magda Jehlarova"],                                       "blocked": "Mia Lee", "setter": "Whitney Bower"},
  {"set": 3, "score_after": "12-18",     "type": "block", "players": ["Iman Isanovic", "Magda Jehlarova"],                      "blocked": "Kate Prior", "setter": "Whitney Bower"},
  {"set": 3, "score_after": "14-18",     "type": "block", "players": ["Whitney Bower", "Whitney McEwan-Llarenas"],              "blocked": "Iman Isanovic", "setter": "Argentina Ung"},
  {"set": 3, "score_after": "18-22",     "type": "block", "players": ["Katy Ryan", "Lana Radakovic"],                           "blocked": "Erin Livingston", "setter": "Whitney Bower"},
  {"set": 4, "score_after": "2-0",       "type": "block", "players": ["Whitney McEwan-Llarenas", "Erin Livingston"],            "blocked": "Iman Isanovic", "setter": "Karly Basham"},
  {"set": 4, "score_after": "6-6",       "type": "block", "players": ["Kate Prior"],                                            "blocked": "Pia Timmer", "setter": "Karly Basham"},
  {"set": 4, "score_after": "6-9",       "type": "block", "players": ["Magda Jehlarova"],                                       "blocked": "Mia Lee", "setter": "Whitney Bower"},
  {"set": 4, "score_after": "11-18",     "type": "block", "players": ["Katy Ryan", "Magda Jehlarova"],                          "blocked": "Erin Livingston", "setter": "Whitney Bower"},
  {"set": 4, "score_after": "16-23",     "type": "block", "players": ["Eden Bower", "Whitney McEwan-Llarenas"],                 "blocked": "Magda Jehlarova", "setter": "Argentina Ung"},
  {"set": 4, "score_after": "17-23",     "type": "block", "players": ["Eden Bower"],                                            "blocked": "Magda Jehlarova", "setter": "Argentina Ung"},
  {"set": 4, "score_after": "18-23",     "type": "block", "players": ["Kate Prior", "Whitney McEwan-Llarenas"],                 "blocked": "Iman Isanovic", "setter": "Karly Basham"},
  {"set": 4, "score_after": "19-25",     "type": "block", "players": ["Argentina Ung", "Lana Radakovic"],                       "blocked": "Eden Bower", "setter": "Whitney Bower"},
]

PARTIAL_CREDIT = 0.5  # right rally and type, credited names off by exactly one

TYPE_ALIASES = {"stuff": "block", "block_point": "block", "block point": "block"}


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


# Every name the answer key can ask for — blockers, the blocked hitter and the
# setter — so a lastname is only treated as unambiguous against the whole key.
_GT_NAMES = sorted({n for g in GROUND_TRUTH
                    for n in (g["players"] + [g["blocked"], g["setter"]])})
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
    """Exactly one name-level error: one name missing, extra, or substituted.

    Errors are counted as max(unmatched-GT, unmatched-pred), so a substitution is
    ONE error rather than two. That makes the rule symmetric between solo and
    shared credit: a solo block with the wrong name, one left unattributed, one
    with a spurious extra name, and a two-player block with one name wrong are each
    a single error (partial); two or more earn nothing. An exact match has zero
    errors and is handled by players_exact.
    """
    if not isinstance(pred_list, list):
        return False
    m = matched_names(pred_list, gt_list)
    missing = len(gt_list) - m
    extra = len(pred_list) - m
    return max(missing, extra) == 1


def blocked_ok(pred_blocked, gt_blocked):
    return name_match(pred_blocked, gt_blocked)


def setter_ok(pred_setter, gt_setter):
    return name_match(pred_setter, gt_setter)


def event_grade(p, gt):
    """Return 'full', 'partial', or None for a prediction against GT block gt
    (anchor set+score+type already matched by the caller).

    A block point is credited to its blockers, but it is one link in a chain the
    official scorer records in full: a setter feeds a hitter, and the block stops
    that attack. Full credit asks for all three — the blocker multiset, the hitter
    who was stopped, and the setter who fed them. Partial credit (0.5) covers
    exactly one of the three being wrong, since each is an independent jersey read
    and a perfect visual agent can lose any one of them.
    """
    wrong = 0
    if not players_exact(p["players"], gt["players"]):
        if not players_off_by_one(p["players"], gt["players"]):
            return None          # two or more blocker errors: no credit
        wrong += 1
    if not blocked_ok(p.get("blocked"), gt.get("blocked")):
        wrong += 1
    if not setter_ok(p.get("setter"), gt.get("setter")):
        wrong += 1
    if wrong == 0:
        return "full"
    if wrong == 1:
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
                "players": pr.get("players"), "blocked": pr.get("blocked"),
                "setter": pr.get("setter")}

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
