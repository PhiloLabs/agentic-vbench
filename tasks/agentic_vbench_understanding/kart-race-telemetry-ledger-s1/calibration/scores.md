# Calibration — kart-race-telemetry-ledger-s1

**Scorer (as shipped).** TIME-ANCHORED + EXACT, **two** scored quantities. Each predicted race is
matched to the GT race whose video window `[t_start,t_end]` contains its reported `t` (±15 s); then
per quantity `score_q = clamp(tau_q,0,1) · accuracy_q`, `accuracy_q = mean max(0, 1 − |pred−gt| /
max(1, 0.30·gt))`, renormalised over quantities that vary. Scored: **items_collected (0.55)** and
**skid_time / drift-seconds (0.45)**. `skid_time` is in VIDEO seconds (rescaled from telemetry
game-seconds — see the timebase note). `spinouts` is **no longer scored** (kept as context).

**Media.** SuperTuxKart profile-mode GT — 12 races × 10 karts × 4 laps on SuperTux (hardest) AI,
camera locked to the hero kart `tux`, 55.1 min, race.mp4 sha `4b4cee91…`, 1280×720, no audio, HUD
powerup slot masked.

## Strong-agent calibration lineup

Each raw trajectory is committed here (secret-free audit record); the reward/solution **dumps live on
HF** (pinned links below), not in git.

| harness (version) | model | reasoning | reward | tool-call turns | trajectory |
|---|---|---|---|---|---|
| Codex CLI (0.145.0) | gpt-5.6-sol | xhigh | **n=3: 0.030 / 0.000 / 0.052** (mean 0.027) | 242 / 120 / 237 | `rollouts/codex_trajectory.md` |
| Claude Code CLI (2.1.241) | claude-opus-4-8 | extended thinking | **0.045** | 108 | `rollouts/claude_trajectory.md` |
| Antigravity CLI | Gemini 3.x | — | _pending (added by maintainer/owner)_ | — | — |

All measured on the shipped video + shipped 2-dim scorer. Strong-agent **max 0.052 (< 0.10)** across
the lineup. The n=3 Codex runs settle the variance the reviewer asked about: mean 0.027, max 0.052 —
comfortably under the bar. Rollout dumps (solution.json + reward.json) on HF, pinned to an immutable
revision (not mutable `main`; trajectory SHA256s in `rollouts/README.md`):
<https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/39f1b933102acb3e52348752eb736b31c4c9d50b/kart-race-telemetry-ledger-s1/calibration>

## Results & ablations (shipped 2-dim scorer)

| submission | reward | notes |
|---|---|---|
| oracle | **1.0000** | harness path (`solve.sh` → `judge.py`); items & skid both tau 1.0, acc 1.0 |
| correct counts, wrong times | 0.0000 | right values at shuffled video times — the ±15 s window rejects |
| blind guess (deterministic) | 0.0069 | the tau gate collapses guessing |
| single frame | 0.0000 | one frame → no per-race differentiation → constant → tau 0 |
| no media / OCR-only | 0.007 / 0.0 | no scored quantity is on-screen text (HUD masked, off-HUD) |
| constant counts | 0.0000 | all races equal → predicted ties → 0 |
| empty | 0.0000 | |

Per-dim on the strong runs: **items** accuracy ~0.00–0.05 (a strong agent undercounts pickups by
~half under the masked HUD, so it is almost never within 30%); **skid** accuracy ~0.08–0.17 (it
cannot sum the cumulative drift to within 30% over a 55-min video). Both defeat the agent; the oracle
is 1.0 and a within-30% agent would score far higher.

## skid_time timebase (correctness)

The software-GL capture runs **below realtime**, by a per-race factor (heavy tracks slow llvmpipe
more), so a race of G game-seconds spans V > G video-seconds. Telemetry `skid_time` is in game
seconds; the agent times drift off the **video** in video seconds. The GT is therefore rescaled per
race — `skid_time_video = skid_time_game · (video_clip_duration / game_race_duration)` — in
`generator/build_ground_truth.py`, and each race keeps `skid_time_game` + `speed_factor` for audit.
Measured speed factors (V/G): hacienda 1.13, snowmountain 1.31, cornfield 1.56, lighthouse 1.47,
gran_paradiso 1.87, sandtrack 1.23, olivermath 1.18, cocoa_temple 1.75, scotland 1.28, fortmagma
1.31, ravenbridge 1.47, stk_enterprise 1.13 (mean 1.39). Oracle = 1.0 on the rescaled values.

## Provenance / hardening (all measured, Codex xhigh)

hero-scope + rank agreement 0.407 → + HUD powerup mask 0.345 → + exact-count metric (accuracy, not
rank) → + time-anchored (races matched by video time ±15 s) → + skid rescaled to video-seconds
(timebase fix) → + **drop spinouts** (too countable — n=3 with spinouts scored 0.073/0.103/0.186,
breaking the bar) → items+skid, **Codex n=3 mean 0.027, max 0.052**. See `SPEC.md`.
