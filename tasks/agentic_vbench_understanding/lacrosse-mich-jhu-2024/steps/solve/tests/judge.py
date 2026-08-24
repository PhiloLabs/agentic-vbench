#!/usr/bin/env python3
"""Deterministic grader for the lacrosse scoring-ledger task.

Pure stdlib. No LLM/VLM. No network.

The agent reconstructs the ordered goal ledger of a lacrosse game from video
alone (score bug + all lower-third graphics masked). Each predicted goal:
(team, scorer #, assister # or null).

HEADLINE reward = F1 over the ordered goal ledger on the tuple
    (team, scorer #, assisted?, running-score-after)
matched by an order-preserving one-to-one alignment (LCS on the tuple
sequence), so one missed goal desyncs the running score from that point on
without cascade-zeroing the earlier matches.
  - `assisted?` is binary (assister null vs non-null). The passer's NUMBER is a
    diagnostic only: the observability audit found it unreadable for ~half the
    assisted goals, so requiring it would break oracle-1.0.
  - `running-score-after` is derived from the predicted team sequence, folding
    the whole-sequence count into each tuple (the volleyball score_after
    anchor), so over/under-counting cascades.

Diagnostics reported in `details` but NOT blended into the reward (LESSONS:
don't blend an easy sub-metric into the headline): with-assister-number F1,
lenient (team+scorer) F1, penalty F1.

Anchors: oracle 1.0 - empty 0.0 - constant-guess 0.0.

Usage: verify.py <prediction.json> [<ground_truth.json>]
Prints a JSON result {reward, details} and exits 0.
"""
import argparse
import json
import sys
from pathlib import Path

TEAMS = {"NAVY", "WHITE"}


def _norm_num(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip().lstrip("#")
    return int(s) if s.isdigit() else None


def _running_scores(goals):
    """Compute (navy, white) running score AFTER each goal from the team
    sequence. A miscounted/misordered goal shifts every later score → the
    reconstruction skill (as in the volleyball score_after anchor)."""
    n = w = 0
    out = []
    for g in goals:
        t = str(g.get("team", "")).upper().strip()
        if t == "NAVY":
            n += 1
        elif t == "WHITE":
            w += 1
        out.append((n, w))
    return out


def _goal_tuple(g, fields, score_after=None):
    team = str(g.get("team", "")).upper().strip()
    if team not in TEAMS:
        team = None
    out = [team, _norm_num(g.get("scorer"))]
    if "assisted" in fields:
        # binary: was the goal assisted? Derived from assister null-ness.
        # The passer's NUMBER is a diagnostic only — the observability audit
        # found it unreadable for ~half the assisted goals (pass visible,
        # number not), so it cannot be required at oracle-1.0 standard.
        out.append(g.get("assister") is not None)
    if "assister" in fields:
        out.append(_norm_num(g.get("assister")))
    if "score" in fields:
        out.append(score_after)
    return tuple(out)


def _lcs_len(a, b):
    """Length of the longest common subsequence of two equal-able lists.
    Order-preserving one-to-one matching; duplicates handled naturally."""
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            if a[i] == b[j] and a[i][0] is not None and a[i][1] is not None:
                dp[i][j] = 1 + dp[i + 1][j + 1]
            else:
                dp[i][j] = max(dp[i + 1][j], dp[i][j + 1])
    return dp[0][0]


def _f1(tp, n_pred, n_gt):
    if n_pred == 0 or n_gt == 0:
        return 0.0
    prec, rec = tp / n_pred, tp / n_gt
    return 0.0 if (prec + rec) == 0 else 2 * prec * rec / (prec + rec)


def _penalty_tuple(p):
    team = str(p.get("team", "")).upper().strip()
    return (team if team in TEAMS else None,
            _norm_num(p.get("offender")),
            str(p.get("type", "")).lower().strip())


def score(pred, gt):
    pg = pred.get("goals", []) if isinstance(pred, dict) else []
    gg = gt["goals"]
    if not isinstance(pg, list):
        pg = []

    pred_scores = _running_scores(pg)
    gt_scores = _running_scores(gg)
    # HEADLINE reward: (team, scorer, running-score) reconstructed in order.
    # Running score folds in the whole-sequence count; assister is a harder
    # diagnostic (kept out of the headline so oracle-1.0 doesn't hinge on every
    # assisting pass being visible).
    head_pred = [_goal_tuple(g, ("team", "scorer", "assisted", "score"), s)
                 for g, s in zip(pg, pred_scores)]
    head_gt = [_goal_tuple(g, ("team", "scorer", "assisted", "score"), s)
               for g, s in zip(gg, gt_scores)]
    strict_tp = _lcs_len(head_pred, head_gt)
    reward = _f1(strict_tp, len(head_pred), len(head_gt))

    # diagnostic: also require assister (harder)
    wa_pred = [_goal_tuple(g, ("team", "scorer", "assister", "score"), s)
               for g, s in zip(pg, pred_scores)]
    wa_gt = [_goal_tuple(g, ("team", "scorer", "assister", "score"), s)
             for g, s in zip(gg, gt_scores)]
    with_assist_f1 = _f1(_lcs_len(wa_pred, wa_gt), len(wa_pred), len(wa_gt))

    len_pred = [_goal_tuple(g, ("team", "scorer")) for g in pg]
    len_gt = [_goal_tuple(g, ("team", "scorer")) for g in gg]
    lenient_tp = _lcs_len(len_pred, len_gt)
    lenient_f1 = _f1(lenient_tp, len(len_pred), len(len_gt))

    pp = pred.get("penalties", []) if isinstance(pred, dict) else []
    pp = pp if isinstance(pp, list) else []
    pen_pred = [_penalty_tuple(p) for p in pp]
    pen_gt = [_penalty_tuple(p) for p in gt.get("penalties", [])]
    # penalty match: greedy multiset on (team, offender, type)
    gt_pool = list(pen_gt)
    pen_tp = 0
    for t in pen_pred:
        if t in gt_pool:
            gt_pool.remove(t)
            pen_tp += 1
    penalty_f1 = _f1(pen_tp, len(pen_pred), len(pen_gt))

    return {
        "reward": round(reward, 4),
        "details": {
            "headline_team_scorer_runscore_f1": round(reward, 4),
            "headline_tp": strict_tp,
            "n_pred_goals": len(pg),
            "n_gt_goals": len(gg),
            "diag_with_assister_f1": round(with_assist_f1, 4),
            "diag_lenient_team_scorer_f1": round(lenient_f1, 4),
            "penalty_f1": round(penalty_f1, 4),
            "penalty_tp": pen_tp,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Grade the lacrosse goal ledger.")
    ap.add_argument("--solution", default="/workspace/output/solution.json")
    ap.add_argument("--answer-key", default=str(Path(__file__).parent / "answer_key.json"))
    ap.add_argument("--reward-json", default="/logs/verifier/reward.json")
    ap.add_argument("--reward-txt", default="/logs/verifier/reward.txt")
    args = ap.parse_args()

    try:
        pred = json.loads(Path(args.solution).read_text())
    except Exception as exc:
        result = {"reward": 0.0, "details": {"error": f"unreadable prediction: {exc.__class__.__name__}"}}
    else:
        gt = json.loads(Path(args.answer_key).read_text())
        result = score(pred, gt)

    for p in (args.reward_json, args.reward_txt):
        try:
            Path(p).parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
    try:
        Path(args.reward_json).write_text(json.dumps(result, indent=2))
        Path(args.reward_txt).write_text(f"{result['reward']:.4f}\n")
    except Exception:
        pass

    print(json.dumps(result))


if __name__ == "__main__":
    main()
