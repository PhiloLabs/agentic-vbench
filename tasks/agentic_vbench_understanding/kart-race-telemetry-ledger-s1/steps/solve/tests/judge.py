#!/usr/bin/env python3
"""Grade a SuperTuxKart race-telemetry reconstruction. Pure stdlib, deterministic.

The video is a suite of races on different tracks. In every race the camera is a chase-cam
locked to a single **hero kart** (the same character throughout the suite) — STK's profile
camera follows the player kart, and the generator makes the hero the player. Only the hero's
telemetry is scored, so **every scored quantity is on screen the whole race**. The top-center
HUD powerup slot is masked, so pickups have no on-screen confirmation.

For each race the agent reports, for the hero, three off-HUD quantities:
- **`items_collected`** — powerup boxes the hero drove through (HUD indicator masked; count the
  drive-throughs).
- **`spinouts`** — times the hero spun out (dizzy-stars). A banana and a bomb both cause the SAME
  visible spin-out and are not reliably distinguishable at 720p, so they are scored JOINTLY
  (spinouts = bananas_hit + times_exploded in the ground truth). bananas_hit / times_exploded may
  be reported separately as context but only their sum is scored.
- **`skid_time`** — total seconds the hero spent drifting/skidding (the slide + sparks). A
  *duration*, not a count — you estimate how long, cumulatively, the hero was drifting.

## Scoring — EXACT, not just rank

    per dimension d:  score_d = clamp(tau_d, 0, 1) * accuracy_d
      tau_d      = signed normalised Kendall correlation over the races (the guess GATE:
                   concordant-minus-discordant / pairs, so a constant or random answer -> ~0)
      accuracy_d = mean over races of  max(0, 1 - |pred - gt| / tol),  tol = max(1, 0.30*gt)
                   (you must be within ~30% of the true value, not merely rank the races right)
    reward = max(0, sum_d w_d * score_d) / sum_d w_d      (over dims that vary in the GT)

This scores the agent against STK's **full-precision** telemetry, not a coarse ranking of it.
Ranking alone is too forgiving: an agent that systematically under-counts (e.g. sees 8 of 20
powerups) still ranks the races roughly right and scores well; requiring the counts to be
*accurate* removes that free credit. The tau gate keeps it guess-proof — an ungated exact metric
was rejected in an earlier design because blind guessing scored 0.33; here blind guessing scores
~0.03, because a guess has no rank agreement to multiply the accuracy by.

Weights: items 0.40, spinouts 0.30, skid_time 0.30. (spinouts = bananas + explosions, scored
jointly because the two are not visually distinguishable; see below.)
A field with no spread in the GT is renormalised out so the oracle still reaches 1.0.

Ground truth is baked verifier-side at /tests/ground_truth.json.
"""
import argparse, json
from pathlib import Path

GT_PATH = Path(__file__).with_name("ground_truth.json")
# (ground-truth field, prediction field, weight)
DIMS = [("items_collected", "items_collected", 0.40),
        ("spinouts",         "spinouts",         0.30),
        ("skid_time",        "skid_time",         0.30)]
# spinouts = bananas_hit + times_exploded. A banana and a bomb both render as the SAME dizzy-stars
# spin-out and are not reliably distinguishable at 720p, so they are scored JOINTLY (the visible
# event is "the hero spun out"; its cause is not observable). Scoring them separately would demand
# an un-observable split. bananas_hit / times_exploded remain reportable as unscored context.


def as_num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def tau(pairs):
    """Signed normalised Kendall correlation over (gt, pred) pairs — the guess gate."""
    n = len(pairs)
    if n < 2:
        return 0.0, 0
    con = dis = total = 0
    for i in range(n):
        for j in range(i + 1, n):
            dg, dp = pairs[i][0] - pairs[j][0], pairs[i][1] - pairs[j][1]
            if dg == 0:
                continue                 # GT tie: no order to recover
            total += 1
            if dp == 0:
                continue                 # predicted tie: neither right nor wrong, still costs
            con += 1 if (dg > 0) == (dp > 0) else 0
            dis += 1 if (dg > 0) != (dp > 0) else 0
    if total == 0:
        return 0.0, 0
    return (con - dis) / total, total


def accuracy(pairs):
    """Mean per-race accuracy: within tol = max(1, 0.30*gt) scores toward 1, decaying to 0."""
    if not pairs:
        return 0.0
    s = 0.0
    for g, p in pairs:
        tol = max(1.0, 0.30 * g)
        s += max(0.0, 1.0 - abs(p - g) / tol)
    return s / len(pairs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", required=True, type=Path)
    ap.add_argument("--reward-json", required=True, type=Path)
    ap.add_argument("--reward-txt", required=True, type=Path)
    a = ap.parse_args()

    gt = json.loads(GT_PATH.read_text())
    gt_races = gt["races"]
    reason, pred_races = "ok", []
    try:
        sol = json.loads(a.solution.read_text())
        pred_races = sol.get("races", [])
        if not isinstance(pred_races, list):
            raise ValueError("races is not a list")
    except Exception as exc:  # noqa: BLE001
        reason = f"unreadable solution.json: {exc}"

    dims, num, wsum = {}, 0.0, 0.0
    n_matched = min(len(gt_races), len(pred_races))
    for gt_field, pred_field, w in DIMS:
        pairs = []
        for i in range(n_matched):
            p = pred_races[i] if isinstance(pred_races[i], dict) else {}
            pv = as_num(p.get(pred_field))
            if pv is not None and gt_field in gt_races[i]:
                pairs.append((float(gt_races[i][gt_field]), pv))
        gt_has_spread = tau([(g, g) for g in (r[gt_field] for r in gt_races if gt_field in r)])[1] > 0
        t, npairs = tau(pairs)
        acc = accuracy(pairs)
        ds = max(0.0, t) * acc
        dims[gt_field] = {"tau": round(t, 4), "accuracy": round(acc, 4),
                          "score": round(ds, 4), "n_pairs": npairs, "gt_varies": gt_has_spread}
        if gt_has_spread:
            num += w * ds
            wsum += w
    reward = max(0.0, num / wsum) if wsum else 0.0

    det = {"reason": reason, "hero": gt.get("hero"), "n_races": len(gt_races),
           "n_predicted_races": len(pred_races), "dims": dims,
           "weights": {f: w for f, _, w in DIMS},
           "note": "reward = (sum_d w*clamp(tau,0,1)*accuracy) / (sum_d w over varying fields); "
                   "tau gates guessing to ~0, accuracy (within ~30% of the machine-exact value) "
                   "requires accurate counts/durations, oracle = 1.0"}
    a.reward_json.parent.mkdir(parents=True, exist_ok=True)
    a.reward_json.write_text(json.dumps({"reward": round(reward, 4), "details": det}, indent=2))
    a.reward_txt.write_text(f"{round(reward, 4)}\n")


if __name__ == "__main__":
    main()
