#!/usr/bin/env python3
"""Grade a CS2 trade-kill ledger reconstruction. Pure Python stdlib, deterministic.

The agent lists every kill with a timestamp, round, victim, killer, traded flag and
trader. Matching follows the maintainer guidance on issue #52: a predicted entry is
paired one-to-one with a ground-truth kill by (victim, killer, |dt| <= TOL) - never
by (round, index) - so one missed kill cannot shift the credit for a whole round.
A matched pair is a true positive only when the remaining fields (round, was_traded,
trader) also agree. reward = F1 over full tuples, so misses and spam both hurt.

Why this metric: ~170 kills are scattered across a full match with no killfeed or
scoreboard on screen. Only genuinely reconstructing who killed whom, when, from the
footage scores; the trade fields couple entries together, so a missed kill also
corrupts the was_traded of its neighbours. Oracle -> 1.0; empty or guessed -> ~0.
"""
import argparse
import json
import math
import re
from pathlib import Path

TOL = 5.0  # seconds; |predicted t - true t| must be within this

GT = json.loads((Path(__file__).resolve().parent / "gt_ledger.json").read_text())["ledger"]

NULLS = {"", "null", "none", "n/a", "-"}


def norm_player(v):
    s = re.sub(r"[^a-z0-9]", "", str(v).lower())
    return s.upper() if re.fullmatch(r"p([1-9]|10)", s) else None


def norm_trader(v):
    if v is None or str(v).strip().lower() in NULLS:
        return None
    return norm_player(v)


def norm_bool(v):
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return True if s == "true" else False if s == "false" else None


def as_float(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def as_int(v):
    try:
        f = float(v)
        return int(f) if math.isfinite(f) and f == int(f) else None
    except (TypeError, ValueError, OverflowError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", required=True, type=Path)
    ap.add_argument("--reward-json", required=True, type=Path)
    ap.add_argument("--reward-txt", required=True, type=Path)
    args = ap.parse_args()

    reason, preds = "ok", []
    try:
        sol = json.loads(args.solution.read_text())
        preds = sol.get("ledger", [])
        if not isinstance(preds, list):
            raise ValueError("ledger is not a list")
    except Exception as exc:  # noqa: BLE001 - malformed output scores 0
        reason, preds = f"unreadable solution.json: {exc}", []

    used = [False] * len(GT)
    tp = 0
    kill_matches = 0  # (t, victim, killer) correct; diagnostic only
    field_errors = {"round": 0, "was_traded": 0, "trader": 0}

    for pr in preds:
        if not isinstance(pr, dict):
            continue
        t = as_float(pr.get("t"))
        victim, killer = norm_player(pr.get("victim")), norm_player(pr.get("killer"))
        if t is None or victim is None or killer is None:
            continue
        # closest unused GT kill with the same victim and killer, within tolerance
        best, best_dt = None, None
        for i, gt in enumerate(GT):
            if used[i] or gt["victim"] != victim or gt["killer"] != killer:
                continue
            dt = abs(t - gt["t"])
            if dt <= TOL and (best_dt is None or dt < best_dt):
                best, best_dt = i, dt
        if best is None:
            continue
        used[best] = True
        kill_matches += 1
        gt = GT[best]
        ok_round = as_int(pr.get("round")) == gt["round"]
        ok_flag = norm_bool(pr.get("was_traded")) == gt["was_traded"]
        ok_trader = norm_trader(pr.get("trader")) == gt["trader"]
        for key, ok in [("round", ok_round), ("was_traded", ok_flag), ("trader", ok_trader)]:
            if not ok:
                field_errors[key] += 1
        if ok_round and ok_flag and ok_trader:
            tp += 1

    n_pred, n_gt = len(preds), len(GT)
    precision = tp / n_pred if n_pred else 0.0
    recall = tp / n_gt if n_gt else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    details = {
        "reason": reason,
        "n_ground_truth": n_gt,
        "n_predicted": n_pred,
        "true_positives_full_tuple": tp,
        "kill_level_matches": kill_matches,
        "field_errors_among_kill_matches": field_errors,
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
