#!/usr/bin/env python3
"""Grade a SuperTuxKart race-telemetry reconstruction. Pure stdlib, deterministic.

The video is a suite of races on different tracks. In every race the camera is a chase-cam
locked to a single **hero kart** (the same character throughout the suite) — STK's profile
camera follows the player kart, and the generator makes the hero the player. Only the hero's
counts are scored, so **every scored quantity is on screen the whole race** ("scope the counts
to what the camera sees"). The rest of the field still races — competing for boxes and bombing
the hero — it is just not the thing being counted.

For each race the agent reports, for the hero:
- **`items_collected`** — how many powerup boxes the hero drove through (the picked-up powerup
  then shows in the hero's HUD slot — visible, but never a running total, so it must be counted).
- **`times_exploded`** — how many times the hero was blown up (thrown into the air, spins out).

Scoring is **rank agreement across races**, not exact match:

    reward = max(0, 0.65*tau(items over races) + 0.35*tau(explosions over races))

where tau is the normalised Kendall correlation `(concordant - discordant)/n_pairs` over the
races, ordering them by the hero's count. You do not have to count exactly — getting the
high-pickup and low-pickup races in the right order earns credit; a random ordering scores 0
in expectation because concordant and discordant pairs cancel.

Why ranking races (not karts within a race): the earlier design ranked all twelve karts in a
race, but with one chase-cam only the followed kart's pickups are actually on screen, so eleven
of the twelve counts were unobservable and capped the achievable score below the oracle's 1.0.
Scoping to the hero and ranking it across the suite keeps a guess-proof rank target while making
every scored event visible. The difficulty is now *sustained counting over a long video*: the
hero's pickups must be tallied accurately in each race and the races ordered by those tallies —
one miscounted race flips several pairs.

Which fields are scored, and why not the others:
  * items / explosions — off-HUD (no on-screen counter) and unambiguously visible on the hero.
  * nitro — the hero's nitro METER is drawn and nitro use renders as boost flames, so it is a
    proxy an agent can read rather than count; reported for context, not scored.
  * finish / start position — displayed by the ranking column and starting grid; not scored.
  * bananas / rescues — witnessable on the hero but sparse across a suite (few distinct values),
    so ranking them is near-constant and not discriminative; reported for context, not scored.

Races are matched by their order in the video (report them in order). Ground truth is baked
verifier-side at /tests/ground_truth.json.
"""
import argparse, json
from pathlib import Path

GT_PATH = Path(__file__).with_name("ground_truth.json")
# (ground-truth field, prediction field, weight) — only OFF-HUD, hero-visible quantities.
DIMS = [("items_collected", "items_collected", 0.65),
        ("times_exploded",   "times_exploded",   0.35)]


def as_num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def tau(pairs):
    """Normalised Kendall correlation over (gt_value, pred_value) pairs. SIGNED, not clamped
    here: clamping each field at 0 discards the negative half of the noise distribution so
    random guessing would average positive. Signed values are aggregated first and the final
    reward is clamped once, which keeps a guess at ~0 in expectation."""
    n = len(pairs)
    if n < 2:
        return 0.0, 0
    con = dis = total = 0
    for i in range(n):
        for j in range(i + 1, n):
            gi, pi = pairs[i]
            gj, pj = pairs[j]
            dg, dp = gi - gj, pi - pj
            if dg == 0:
                continue          # ground-truth ties carry no order to recover
            total += 1
            if dp == 0:
                continue          # a predicted tie is neither right nor wrong, but still costs
            con += 1 if (dg > 0) == (dp > 0) else 0
            dis += 1 if (dg > 0) != (dp > 0) else 0
    if total == 0:
        return 0.0, 0
    return (con - dis) / total, total


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

    # A scored field with NO spread in the ground truth (every race tied) carries no order to
    # recover: tau() returns 0 pairs. Such a field must not drag the reward down — otherwise the
    # oracle, which ranks every varying field perfectly, could not reach 1.0. So weights are
    # renormalised over the fields that actually vary in this suite; a build-time check
    # (build_ground_truth.py) guarantees at least the primary field varies.
    taus, num, wsum = {}, 0.0, 0.0
    n_matched = min(len(gt_races), len(pred_races))
    for gt_field, pred_field, w in DIMS:
        pairs = []
        for i in range(n_matched):
            p = pred_races[i] if isinstance(pred_races[i], dict) else {}
            pv = as_num(p.get(pred_field))
            if pv is not None and gt_field in gt_races[i]:
                pairs.append((float(gt_races[i][gt_field]), pv))
        t, npairs = tau(pairs)
        gt_has_spread = tau([(g, g) for g in (r[gt_field] for r in gt_races if gt_field in r)])[1] > 0
        taus[gt_field] = {"tau": round(t, 4), "n_pairs": npairs, "gt_varies": gt_has_spread}
        if gt_has_spread:
            num += w * t
            wsum += w
    reward = max(0.0, num / wsum) if wsum else 0.0

    det = {"reason": reason, "hero": gt.get("hero"), "n_races": len(gt_races),
           "n_predicted_races": len(pred_races), "taus": taus,
           "weights": {f: w for f, _, w in DIMS},
           "note": "reward = (sum_field w*tau) / (sum of w over fields that vary in the GT); tau "
                   "is normalised Kendall correlation over the hero count ranked across races, so "
                   "guessing scores ~0 and the oracle scores 1.0"}
    a.reward_json.parent.mkdir(parents=True, exist_ok=True)
    a.reward_json.write_text(json.dumps({"reward": round(reward, 4), "details": det}, indent=2))
    a.reward_txt.write_text(f"{round(reward, 4)}\n")


if __name__ == "__main__":
    main()
