#!/usr/bin/env python3
"""Grade a SuperTuxKart race-telemetry reconstruction. Pure stdlib, deterministic.

The video is a suite of AI-driven races on different tracks. For each race the agent reports,
per kart, how many powerup boxes it collected and how much nitro it picked up. (Finishing
order and starting grid may be reported for context but are NOT scored — see below.)

Every component is scored as **rank agreement**, not exact match:

    reward = max(0, mean over races of [0.60*tau(items) + 0.40*tau(nitro)])

where tau is the normalised Kendall correlation over kart pairs,
`(concordant - discordant) / n_pairs`, clamped at 0.

A field is scored only if it is (a) machine-exact in STK's profile table, (b) visible on
camera, and (c) NOT already displayed by the game's HUD. Powerup-box and nitro pickups are the
only quantities meeting all three: both are dense (3-22 per kart) and nowhere on screen, so
they must be counted by following each kart through the race. Rescues and banana hits are in
the table but are almost always zero — ranking near-constant columns is neither discriminative
nor guess-proof.

Two scoring designs were rejected by measurement, not taste:
  * Exact positions + tolerant counts: blind guessing scored 0.33 and reading only the start
    grid scored 0.43, because a random permutation still lands 1-in-6 positions exactly and
    sparse counts are almost always guessable.
  * Rank agreement including finish + start grid: a real Codex run scored 0.557, with tau 0.75
    on finish and 0.90 on start — the ranking column and grid simply display those, so it was
    rewarding leaderboard reading. The same run scored 0.27 / 0.12 on the pickup counts.
Rank agreement over the off-HUD counts keeps the guessing floor at ~0 (concordant and
discordant pairs cancel) while still granting partial credit for partial knowledge.

Karts are matched by name — the character is visible on track and in the ranking icons — so a
submission that gets the order right but mislabels who is who is scored accordingly. Karts
the submission omits are dropped from that race's pairs; a race with fewer than two matched
karts scores 0.

Ground truth is baked verifier-side at /tests/ground_truth.json.
"""
import argparse, json, re
from pathlib import Path

GT_PATH = Path(__file__).with_name("ground_truth.json")
# (ground-truth field, prediction field, weight)
# Only OFF-HUD quantities are scored. Calibration showed the on-screen ranking column and
# starting grid hand an agent the finishing order and start slots almost for free (Codex tau
# 0.75 / 0.90) — that is leaderboard reading, not video understanding. The pickup counts are
# not displayed anywhere: they require following each kart through the whole race and counting
# discrete events (Codex 0.27 / 0.12). Finish and start may still be REPORTED for context;
# they are ignored by the scorer, like `track`.
DIMS = [("items_collected", "items_collected", 0.60),
        ("nitro_collected", "nitro_collected", 0.40)]


def norm(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def as_num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def tau(pairs):
    """Normalised Kendall correlation over (gt_value, pred_value) pairs. SIGNED.

    Deliberately not clamped here: clamping each race/field at 0 discards the negative half of
    the noise distribution, so random guessing averages POSITIVE (measured 0.156 with 6 karts).
    The signed values are aggregated first and the final reward is clamped once, which keeps a
    guess at ~0 in expectation.
    """
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
                continue          # ground truth ties carry no order to recover, so they are
                                  # excluded from the denominator too — counting them made the
                                  # oracle top out at 0.98 whenever two karts tied on items
            total += 1
            if dp == 0:
                continue          # a predicted tie is neither right nor wrong, but still costs
            if (dg > 0) == (dp > 0):
                con += 1
            else:
                dis += 1
    if total == 0:
        return 0.0, 0
    return (con - dis) / total, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", required=True, type=Path)
    ap.add_argument("--reward-json", required=True, type=Path)
    ap.add_argument("--reward-txt", required=True, type=Path)
    a = ap.parse_args()

    gt_races = json.loads(GT_PATH.read_text())["races"]
    reason, pred_races = "ok", []
    try:
        sol = json.loads(a.solution.read_text())
        pred_races = sol.get("races", [])
        if not isinstance(pred_races, list):
            raise ValueError("races is not a list")
    except Exception as exc:  # noqa: BLE001
        reason = f"unreadable solution.json: {exc}"

    per_race, total = [], 0.0
    for i, g in enumerate(gt_races):
        p = pred_races[i] if i < len(pred_races) and isinstance(pred_races[i], dict) else {}
        pk = {norm(k.get("kart")): k for k in p.get("karts", []) if isinstance(k, dict)}
        race_score, taus, n_matched = 0.0, {}, 0
        for gt_field, pred_field, w in DIMS:
            pairs = []
            for k in g["karts"]:
                q = pk.get(norm(k["kart"]))
                if not q or gt_field not in k:
                    continue
                pv = as_num(q.get(pred_field))
                if pv is not None:
                    pairs.append((float(k[gt_field]), pv))
            t, _ = tau(pairs)
            taus[gt_field] = round(t, 4)
            race_score += w * t
            n_matched = max(n_matched, len(pairs))
        per_race.append({"track": g.get("track"), "score": round(race_score, 4),
                         "taus": taus, "n_karts": len(g["karts"]), "n_matched": n_matched})
        total += race_score
    reward = max(0.0, total / max(1, len(gt_races)))   # clamp ONCE, after aggregation

    det = {"reason": reason, "n_races": len(gt_races), "n_predicted_races": len(pred_races),
           "per_race": per_race, "weights": {f: w for f, _, w in DIMS},
           "note": "reward = sum_field w*tau(field order); tau is normalised Kendall "
                   "correlation clamped at 0, so guessing scores 0 in expectation"}
    a.reward_json.parent.mkdir(parents=True, exist_ok=True)
    a.reward_json.write_text(json.dumps({"reward": round(reward, 4), "details": det}, indent=2))
    a.reward_txt.write_text(f"{round(reward, 4)}\n")


if __name__ == "__main__":
    main()
