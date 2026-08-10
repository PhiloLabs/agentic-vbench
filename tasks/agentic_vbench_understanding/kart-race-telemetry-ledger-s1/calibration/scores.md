# Calibration — kart-race-telemetry-ledger-s1

**Scorer (as shipped).** `reward = sum_q w_q · clamp(tau_q,0,1) · accuracy_q`, renormalised over the
scored quantities that vary in the ground truth. `tau_q` = signed normalised Kendall correlation
over the 12 races; `accuracy_q` = mean over races of `max(0, 1 - |pred-gt| / max(1, 0.30·gt))`.
Scored quantities (all off-HUD, hero-only, machine-exact): **items_collected (0.40)**,
**spinouts = bananas+explosions (0.30)**, **skid_time / drift seconds (0.30)**.

**Media (as shipped).** SuperTuxKart profile-mode ground truth — 12 races × 10 karts × 4 laps on
SuperTux (hardest) AI, camera locked to the hero kart `tux`, 53.4 min, 1280×720, no audio, HUD
powerup slot masked.

## Results (Codex `gpt-5.6-sol`, reasoning=xhigh)

| run | reward | notes |
|---|---|---|
| oracle | **1.0** | harness path (`solve.sh` → `judge.py`); items/spinouts/skid all tau=1.0, acc=1.0 |
| blind guess (random counts) | **~0.02** | 300 trials; the tau gate collapses guessing |
| constant counts | 0.0 | all races equal → predicted ties → 0 |
| empty | 0.0 | |
| **Codex gpt-5.6-sol (xhigh)** | **0.0236** | 542 tool calls; rollout `rollouts/codex_3dim_*.json` |

Per-dimension (Codex): items 0.015 (accuracy ~0.04 — never within 30%, undercounts ~50%),
spinouts 0.027, skid_time 0.032. Requiring accurate counts + a drift duration over a 53-min video
defeats the agent; the oracle stays 1.0 and a within-30% agent would score far higher.

## Provenance / hardening (all measured)
`rollouts/codex_exact_full_*.json` is the raw completed Codex run (4 quantities: items, explosions,
bananas, skid). `rollouts/codex_3dim_*.json` re-scores it under the shipped 3-dim metric (bananas +
explosions summed into `spinouts`) = **0.0236**. Design history: hero-scope + rank agreement 0.407
→ + HUD powerup mask 0.345 → + exact-count metric (accuracy, not rank) + observability fixes
(merge banana/explosion, drift = yellow wheel sparks) → **0.0236** (n=1). See `SPEC.md` for the full
rationale and the observability argument for each scored quantity.
