#!/usr/bin/env python3
"""Grade a SuperTuxKart race-telemetry reconstruction. Pure stdlib, deterministic.

The video is a suite of races on different tracks. In every race the camera is a chase-cam
locked to a single **hero kart** (the same character throughout the suite) — STK's profile
camera follows the player kart, and the generator makes the hero the player. Only the hero's
telemetry is scored, so **every scored quantity is on screen the whole race**. The top-center
HUD powerup slot is masked, so pickups have no on-screen confirmation.

For each race the agent reports, for the hero, TWO scored off-HUD quantities:
- **`items_collected`** — powerup boxes the hero drove through (HUD indicator masked; count the
  drive-throughs).
- **`skid_time`** — total seconds the hero spent drifting, in VIDEO time. Drift shows as bright
  yellow sparks from BOTH rear wheels (distinct from straight driving); estimate the cumulative
  drift duration.
(`spinouts` — times the hero spun out, banana or bomb dizzy-stars — may be reported as context but
is NOT scored; see the DIMS note below for why.)

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

Weights: items_collected 0.55, skid_time 0.45 (drift seconds, in VIDEO time). Two off-HUD quantities
that both defeat a strong agent (it undercounts pickups ~half and cannot time drift within 30%).
spinouts is NOT scored — the dizzy-stars spin-out is legible enough that a strong agent counts it
well, so it is not a valid difficulty lever; it stays as unscored context. A field with no spread in
the GT is renormalised out so the oracle still reaches 1.0.

Ground truth is baked verifier-side at /tests/ground_truth.json.
"""
import argparse, json, math
from pathlib import Path

GT_PATH = Path(__file__).with_name("ground_truth.json")
# (ground-truth field, prediction field, weight)
DIMS = [("items_collected", "items_collected", 0.55),
        ("skid_time",        "skid_time",        0.45)]
# Two off-HUD, machine-exact quantities that are HARD for a strong agent (n=3 calibration showed both
# defeat it: it undercounts pickups by ~half and cannot time drift to within 30%):
#  * items_collected — the hero drives through a question-mark box (HUD powerup slot masked, no
#    on-screen count), so pickups must be caught from the video.
#  * skid_time — total DRIFT SECONDS in VIDEO time (the GT is rescaled from telemetry game-seconds to
#    the video clock; see generator/build_ground_truth.py). Drift's tell is bright YELLOW sparks from
#    BOTH rear wheels while skidding (calibration/crops/drift_720p.png), absent when running straight,
#    so it is witnessable and its duration scorable (hard: time + sum the drifts to within 30%).
# spinouts is NOT scored: the dizzy-stars spin-out is legible enough that a strong agent counts it
# well (n=3 calibration: accuracy up to 0.60), so it is not a valid difficulty lever and only weakened
# the <0.10 bar. It, bananas_hit, times_exploded, nitro and positions remain unscored context.


def as_num(v):
    """Parse to a FINITE float, else None. Rejects nan/inf (and their string forms) so a
    non-finite pseudo-number cannot pass the scored-field check or poison accuracy/tau."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


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

    # Time-windowed race matching: each GT race is paired with the predicted race whose reported
    # video time `t` falls within its [t_start, t_end] window (+/-15 s slack), one-to-one, nearest
    # first. This anchors each count-vector to the correct video SEGMENT instead of assuming the
    # agent listed races in order — a right-count / wrong-time (or wrong-race) entry earns nothing.
    TOL = 15.0
    def race_t(r):
        return as_num(r.get("t", r.get("t_start", r.get("time")))) if isinstance(r, dict) else None
    def has_all_scores(r):
        # A race counts as matched only if it carries a numeric value for EVERY scored dimension.
        # A time-matched {track, t} placeholder (no items_collected / skid_time) is not a real answer
        # and must earn no coverage — otherwise a few real races padded with in-window placeholders
        # would reach coverage 1.0 and score as if complete.
        return isinstance(r, dict) and all(as_num(r.get(pf)) is not None for _, pf, _ in DIMS)
    used, matched = set(), []
    for g in gt_races:
        ts, te = g.get("t_start"), g.get("t_end")
        best, bestd = None, None
        if ts is not None and te is not None:
            mid = (ts + te) / 2.0
            for i, p in enumerate(pred_races):
                if i in used or not has_all_scores(p):
                    continue
                pt = race_t(p)
                if pt is not None and ts - TOL <= pt <= te + TOL:
                    d = abs(pt - mid)
                    if bestd is None or d < bestd:
                        bestd, best = d, i
        matched.append((g, pred_races[best] if best is not None else None))
        if best is not None:
            used.add(best)
    n_matched = sum(1 for _, p in matched if isinstance(p, dict))

    dims, num, wsum = {}, 0.0, 0.0
    for gt_field, pred_field, w in DIMS:
        pairs = []
        for g, p in matched:
            if not isinstance(p, dict):
                continue
            pv = as_num(p.get(pred_field))
            if pv is not None and gt_field in g:
                pairs.append((float(g[gt_field]), pv))
        gt_has_spread = tau([(x, x) for x in (r[gt_field] for r in gt_races if gt_field in r)])[1] > 0
        t, npairs = tau(pairs)
        acc = accuracy(pairs)
        ds = max(0.0, t) * acc
        dims[gt_field] = {"tau": round(t, 4), "accuracy": round(acc, 4),
                          "score": round(ds, 4), "n_pairs": npairs, "gt_varies": gt_has_spread}
        if gt_has_spread:
            num += w * ds
            wsum += w
    base = max(0.0, num / wsum) if wsum else 0.0
    # COVERAGE. A GT race with no matched prediction (omitted, or a prediction timed into the wrong
    # segment) must contribute ZERO — otherwise a correct answer covering only k of n races would
    # score as if complete (e.g. a 2-of-12 oracle would reach 1.0). Scale the reward by the fraction
    # of GT races that got a matched prediction, so a partial answer cannot reach 1.0 while the full
    # oracle (every race matched) still does. tau/accuracy are computed over the matched pairs; this
    # factor puts the omitted races back into the denominator.
    coverage = n_matched / len(gt_races) if gt_races else 0.0
    reward = base * coverage

    det = {"reason": reason, "hero": gt.get("hero"), "n_races": len(gt_races),
           "n_predicted_races": len(pred_races), "n_time_matched": n_matched, "coverage": round(coverage, 4),
           "reward_before_coverage": round(base, 4), "time_tol_s": TOL,
           "dims": dims, "weights": {f: w for f, _, w in DIMS},
           "note": "each predicted race is matched to the GT race whose video window contains its t "
                   "(+/-15 s); reward = coverage * (sum_d w*clamp(tau,0,1)*accuracy)/(sum_d w over "
                   "varying fields), coverage = matched_races / total_races (omitted races score 0); "
                   "tau gates guessing to ~0, accuracy (within ~30% of the machine-exact "
                   "value) requires accurate counts/durations at the right time, oracle = 1.0"}
    a.reward_json.parent.mkdir(parents=True, exist_ok=True)
    a.reward_json.write_text(json.dumps({"reward": round(reward, 4), "details": det}, indent=2))
    a.reward_txt.write_text(f"{round(reward, 4)}\n")


if __name__ == "__main__":
    main()
