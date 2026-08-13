# Calibration — kart-race-telemetry-ledger-s1

**Scorer (as shipped).** TIME-ANCHORED: each predicted race is matched to the GT race whose video
window `[t_start,t_end]` contains its reported `t` (±15 s); then
`reward = sum_q w_q · clamp(tau_q,0,1) · accuracy_q`, renormalised over the scored quantities that
vary in the ground truth. `tau_q` = signed normalised Kendall correlation over the matched races;
`accuracy_q` = mean over matched races of `max(0, 1 - |pred-gt| / max(1, 0.30·gt))`.
Scored quantities (all off-HUD, hero-only, machine-exact): **items_collected (0.40)**,
**spinouts = bananas+explosions (0.30)**, **skid_time / drift seconds (0.30)**.

**Media (as shipped).** SuperTuxKart profile-mode ground truth — 12 races × 10 karts × 4 laps on
SuperTux (hardest) AI, camera locked to the hero kart `tux`, 55.1 min (12-race re-render, sha `4b4cee91…`), 1280×720, no audio, HUD
powerup slot masked.

## Results (Codex `gpt-5.6-sol`, reasoning=xhigh)

| run | reward | notes |
|---|---|---|
| oracle | **1.0** | harness path (`solve.sh` → `judge.py`); items/spinouts/skid all tau=1.0, acc=1.0 |
| correct counts, wrong times | **0.005** | right per-race counts placed at shuffled video times — the ±15 s window rejects them |
| blind guess (random counts) | **~0.02** | 300 trials; the tau gate collapses guessing |
| constant counts | 0.0 | all races equal → predicted ties → 0 |
| empty | 0.0 | |
| **Codex gpt-5.6-sol (xhigh) — shipped, time-anchored** | **0.0892** | fresh run on the shipped video; matched 12/12 races to the right window; rollout `rollouts/codex_ts_*.json` |
| Codex gpt-5.6-sol (xhigh) — positional re-score | 0.0236 | earlier completed 542-call run, re-scored with NO time window; rollout `rollouts/codex_3dim_*.json` |

Per-dimension (shipped time-anchored run): **items 0.024** (tau 0.45, accuracy 0.05 — undercounts
powerups by ~half, almost never within 30%; nearly unscored), **spinouts 0.174** (tau 0.66, accuracy
0.26 — the dizzy-stars event is the most legible and carries most of the reward), **skid_time 0.092**
(tau 0.32, accuracy 0.29 — timing the drift total to within 30% is hard). Requiring accurate counts +
a drift duration over a 55-min video keeps the agent under 0.10; the oracle stays 1.0 and a
within-30% agent would score far higher. n=1, run-dependent.

## Provenance / hardening (all measured)
`rollouts/codex_ts_*.json` is the shipped time-anchored run (**0.0892**). `rollouts/codex_exact_full_*.json`
is the earlier raw completed Codex run (4 quantities: items, explosions, bananas, skid) and
`rollouts/codex_3dim_*.json` re-scores it under the 3-dim metric with NO time window = **0.0236**.
The time window only ever removes credit from a given submission (it adds a constraint), so it is
strictly no easier; the 0.0892-vs-0.0236 gap is run-to-run variance, not the metric. Design history:
hero-scope + rank agreement 0.407 → + HUD powerup mask 0.345 → + exact-count metric (accuracy, not
rank) + observability fixes (merge banana/explosion, drift = yellow wheel sparks) → + time-anchored
(races matched by video time ±15 s) → **0.0892** (n=1). See `SPEC.md` for the full rationale and the
observability argument for each scored quantity.
