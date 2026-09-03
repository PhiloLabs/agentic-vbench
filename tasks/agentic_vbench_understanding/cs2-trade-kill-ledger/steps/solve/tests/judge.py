#!/usr/bin/env python3
"""Grade a CS2 trade-episode reconstruction. Pure Python stdlib, deterministic.

A trade episode is one initial kill A->B plus the earliest revenge kill of A by a
teammate of B within 5.0 s in the same round. Each scored item couples TWO kills
across three players' POVs - so an agent gets credit only after completing the
whole causal pair, which defeats the cherry-pick-easy-kills strategy that a flat
per-kill ledger allows.

A predicted episode matches a ground-truth episode iff, for BOTH the initial and
the trade kill: killer, victim, and weapon match exactly and the timestamp is
within TOL seconds; and the round matches. Predictions are matched one-to-one to
GT episodes by maximum-cardinality bipartite matching. reward = F1.
"""
import argparse
import json
import math
import re
from pathlib import Path

TOL = 2.0  # seconds; episodes are sparse, so this only guards read error
GT = json.loads((Path(__file__).resolve().parent / "gt_episodes.json").read_text())["trade_episodes"]


def canon_weapon(w):
    return re.sub(r"[^a-z0-9]", "", str(w).lower())


def norm_player(v):
    s = re.sub(r"[^a-z0-9]", "", str(v).lower())
    return s.upper() if re.fullmatch(r"p([1-9]|10)", s) else None


def as_float(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def norm_kill(k):
    if not isinstance(k, dict):
        return None
    t = as_float(k.get("t", k.get("time_s")))
    killer, victim = norm_player(k.get("killer")), norm_player(k.get("victim"))
    if t is None or killer is None or victim is None:
        return None
    return {"t": t, "killer": killer, "victim": victim,
            "weapon": canon_weapon(k.get("weapon"))}


def kill_matches(pred, gt):
    return (pred["killer"] == gt["killer"] and pred["victim"] == gt["victim"]
            and pred["weapon"] == canon_weapon(gt["weapon"]) and abs(pred["t"] - gt["t"]) <= TOL)


def as_int(v):
    try:
        f = float(v)
        return int(f) if math.isfinite(f) and f == int(f) else None
    except (TypeError, ValueError, OverflowError):
        return None


def episode_edge(pred, gt):
    if as_int(pred.get("round")) != gt["round"]:
        return False
    pi, pt = norm_kill(pred.get("initial_kill")), norm_kill(pred.get("trade_kill"))
    if pi is None or pt is None:
        return False
    return kill_matches(pi, gt["initial_kill"]) and kill_matches(pt, gt["trade_kill"])


def max_bipartite_matching(edges, n_pred, n_gt):
    """edges[p] = set of gt indices p can match. Returns match count."""
    match_gt = [-1] * n_gt

    def try_augment(p, seen):
        for g in edges[p]:
            if g in seen:
                continue
            seen.add(g)
            if match_gt[g] == -1 or try_augment(match_gt[g], seen):
                match_gt[g] = p
                return True
        return False

    count = 0
    for p in range(n_pred):
        if try_augment(p, set()):
            count += 1
    return count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", required=True, type=Path)
    ap.add_argument("--reward-json", required=True, type=Path)
    ap.add_argument("--reward-txt", required=True, type=Path)
    args = ap.parse_args()

    reason, preds = "ok", []
    try:
        sol = json.loads(args.solution.read_text())
        preds = sol.get("trade_episodes", [])
        if not isinstance(preds, list):
            raise ValueError("trade_episodes is not a list")
    except Exception as exc:  # noqa: BLE001
        reason, preds = f"unreadable solution.json: {exc}", []

    edges = [set() for _ in preds]
    for p, pr in enumerate(preds):
        if not isinstance(pr, dict):
            continue
        for g, gt in enumerate(GT):
            if episode_edge(pr, gt):
                edges[p].add(g)

    tp = max_bipartite_matching(edges, len(preds), len(GT))
    n_pred, n_gt = len(preds), len(GT)
    fp, fn = n_pred - tp, n_gt - tp
    f1 = (2 * tp / (2 * tp + fp + fn)) if (2 * tp + fp + fn) else 0.0
    details = {
        "reason": reason, "n_ground_truth": n_gt, "n_predicted": n_pred,
        "true_positives": tp, "false_positives": fp, "false_negatives": fn,
        "precision": round(tp / n_pred, 4) if n_pred else 0.0,
        "recall": round(tp / n_gt, 4) if n_gt else 0.0,
        "f1": round(f1, 4), "time_tolerance_s": TOL,
    }
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps({"reward": round(f1, 4), "details": details}, indent=2))
    args.reward_txt.write_text(f"{round(f1, 4)}\n")


if __name__ == "__main__":
    main()
