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

    each predicted race is matched to a GT race by an OPTIMAL (assignment-safe) bipartite matching
    on its reported time t — a prediction whose t is CONTAINED in a GT segment [t_start, t_end] is
    preferred, else one within +/-15 s is eligible (see match_races). Then, per dimension d:
      score_d    = clamp(tau_d, 0, 1) * accuracy_d
      tau_d      = signed normalised Kendall correlation over the matched pairs that carry d (the
                   guess GATE: concordant-minus-discordant / pairs, so a constant/random answer -> ~0)
      accuracy_d = ( sum over matched pairs carrying d of max(0, 1 - |pred-gt| / tol) ) / N_GT_RACES,
                   tol = max(1, 0.30*gt)   -- the divisor is the TOTAL GT race count, so COVERAGE is
                   folded PER dimension: a GT race with no matched prediction, or a matched prediction
                   that omits field d (or gives a non-finite value), contributes 0 to dimension d.
    reward = max(0, sum_d w_d * score_d) / sum_d w_d      (over dims that vary in the GT)

Per-dimension coverage means an items-only answer earns its honest items credit while skid_time
scores 0 — and padding a dummy skid_time (or a non-finite one) can neither raise nor erase the other
field's credit. A partial answer still cannot reach 1.0 (a correct 2-of-12 answer scores ~2/12).

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


def accuracy(pairs, n_total):
    """Coverage-folded per-race accuracy for ONE dimension: sum of per-race accuracy (within
    tol = max(1, 0.30*gt) → 1, decaying to 0) over the matched pairs that carry this dimension's
    value, divided by the TOTAL number of GT races. A GT race with no matched prediction — or a
    matched prediction that omits THIS field — contributes 0, so coverage is applied per dimension:
    an omitted field scores zero for its own dimension without erasing honest credit for another."""
    if n_total <= 0:
        return 0.0
    s = 0.0
    for g, p in pairs:
        tol = max(1.0, 0.30 * g)
        s += max(0.0, 1.0 - abs(p - g) / tol)
    return s / n_total


def race_t(r):
    """The predicted video time for a race row: `t`, else `t_start`/`time`. None if unusable."""
    return as_num(r.get("t", r.get("t_start", r.get("time")))) if isinstance(r, dict) else None


def _hungarian(cost):
    """Min-cost perfect matching on a square cost matrix (Kuhn–Munkres, O(n^3)). Pure stdlib.
    Returns row->col assignment as a list `a` with `a[i] = j`."""
    n = len(cost)
    INF = float("inf")
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = INF
            j1 = -1
            for j in range(1, n + 1):
                if not used[j]:
                    cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j] = cur
                        way[j] = j0
                    if minv[j] < delta:
                        delta = minv[j]
                        j1 = j
            for j in range(0, n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    a = [-1] * n
    for j in range(1, n + 1):
        if p[j] > 0:
            a[p[j] - 1] = j - 1
    return a


def match_races(gt_races, pred_races, tol):
    """Assignment-safe race matching. Each predicted race is matched to at most one GT race, and
    vice versa, by an optimal (min-cost, max-cardinality) bipartite assignment — NOT greedy — so
    overlapping tolerance windows can no longer strand a race. A prediction whose reported time is
    *contained* in a GT race's [t_start, t_end] segment is preferred (cost by distance to the
    segment midpoint); a prediction merely within ±tol of a segment is eligible but always costs
    more than any true containment; anything else is ineligible. Returns `matched[gi] = pi | None`.

    Containment-first is what lets an exact answer that reports every race at its own `t_start`
    (permitted by the prompt) score 1.0: t_start ∈ [t_start, t_end], so every race is contained in
    its own segment and the optimal assignment recovers all of them, even though adjacent ±tol
    windows overlap."""
    ng, npd = len(gt_races), len(pred_races)
    if ng == 0 or npd == 0:
        return [None] * ng
    K = max(ng, npd)
    BIG = 1.0e6  # >> any real edge cost * K, so more eligible matches always beats lower cost
    cost = [[0.0] * K for _ in range(K)]      # padding rows/cols cost 0 (ineligible)
    elig = [[False] * K for _ in range(K)]
    for gi, g in enumerate(gt_races):
        ts, te = g.get("t_start"), g.get("t_end")
        if ts is None or te is None:
            continue
        mid = (ts + te) / 2.0
        width = te - ts
        for pi, p in enumerate(pred_races):
            pt = race_t(p)
            if pt is None:
                continue
            if ts <= pt <= te:
                c = abs(pt - mid)                        # contained: preferred
            elif ts - tol <= pt <= te + tol:
                c = abs(pt - mid) + width + tol          # tolerance: strictly worse than any containment
            else:
                continue                                 # ineligible
            cost[gi][pi] = c - BIG                       # reward each eligible match by -BIG
            elig[gi][pi] = True
    assign = _hungarian(cost)
    matched = [None] * ng
    for gi in range(ng):
        pj = assign[gi]
        if 0 <= pj < npd and elig[gi][pj]:
            matched[gi] = pj
    return matched


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
            # Normalize malformed `races` (null, dict, scalar, ...) to an empty list so the judge
            # scores 0 rather than crashing on a downstream len()/iteration.
            reason = "races was not a list; normalized to []"
            pred_races = []
    except Exception as exc:  # noqa: BLE001
        reason = f"unreadable solution.json: {exc}"
        pred_races = []

    # Assignment-safe, containment-first race matching (see match_races): each predicted race is
    # anchored to the GT race whose video segment [t_start, t_end] contains its reported time t
    # (preferred), or that it falls within ±TOL of, by an OPTIMAL bipartite assignment. This
    # anchors each count-vector to the correct video SEGMENT — a right-count / wrong-time entry
    # earns nothing — and, unlike the old greedy pass, does not strand a race when adjacent ±TOL
    # windows overlap (e.g. an exact answer reporting every race at its t_start now scores 1.0).
    TOL = 15.0
    matched = match_races(gt_races, pred_races, TOL)  # matched[gi] = pred index | None
    n_matched = sum(1 for pi in matched if pi is not None)
    NG = len(gt_races)

    dims, num, wsum = {}, 0.0, 0.0
    for gt_field, pred_field, w in DIMS:
        pairs, cov_d = [], 0
        for gi, pi in enumerate(matched):
            if pi is None:
                continue
            g, p = gt_races[gi], pred_races[pi]
            if not isinstance(p, dict):
                continue
            pv = as_num(p.get(pred_field))
            if pv is not None and gt_field in g:
                pairs.append((float(g[gt_field]), pv))
                cov_d += 1
        gt_has_spread = tau([(x, x) for x in (r[gt_field] for r in gt_races if gt_field in r)])[1] > 0
        t, npairs = tau(pairs)
        # PER-DIMENSION COVERAGE. accuracy() divides by the TOTAL GT race count, so a GT race with no
        # matched prediction OR a matched prediction that omits this field contributes 0 to this
        # dimension. There is no separate global coverage factor and no all-fields gate: an
        # items-only answer earns its honest items credit while skid_time scores 0, and padding a
        # dummy skid_time cannot raise (nor a missing one erase) the other field's credit. A partial
        # answer still cannot reach 1.0 (a correct 2-of-12 answer scores ~2/12 per dimension).
        acc = accuracy(pairs, NG)
        ds = max(0.0, t) * acc
        dims[gt_field] = {"tau": round(t, 4), "accuracy": round(acc, 4), "score": round(ds, 4),
                          "n_pairs": npairs, "coverage": round(cov_d / NG, 4) if NG else 0.0,
                          "gt_varies": gt_has_spread}
        if gt_has_spread:
            num += w * ds
            wsum += w
    reward = max(0.0, num / wsum) if wsum else 0.0

    det = {"reason": reason, "hero": gt.get("hero"), "n_races": NG,
           "n_predicted_races": len(pred_races), "n_time_matched": n_matched,
           "coverage": round(n_matched / NG, 4) if NG else 0.0, "time_tol_s": TOL,
           "dims": dims, "weights": {f: w for f, _, w in DIMS},
           "note": "each predicted race is matched to the GT race whose video segment contains its t "
                   "(preferred) or that it falls within +/-15 s of, by an optimal (assignment-safe) "
                   "bipartite matching; reward = (sum_d w*clamp(tau,0,1)*accuracy_d)/(sum_d w over "
                   "varying fields), where accuracy_d averages per-race within-~30% accuracy over ALL "
                   "GT races (coverage folded PER dimension: an omitted race or field scores 0 for "
                   "that dimension). tau gates guessing to ~0; oracle = 1.0"}
    a.reward_json.parent.mkdir(parents=True, exist_ok=True)
    a.reward_json.write_text(json.dumps({"reward": round(reward, 4), "details": det}, indent=2))
    a.reward_txt.write_text(f"{round(reward, 4)}\n")


if __name__ == "__main__":
    main()
