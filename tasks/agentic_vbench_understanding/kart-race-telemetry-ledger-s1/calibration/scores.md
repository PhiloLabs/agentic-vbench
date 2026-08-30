# Calibration — kart-race-telemetry-ledger-s1

**Scorer (as shipped).** TIME-ANCHORED + EXACT, **two** scored quantities. Each predicted race is
matched to the GT race whose video window `[t_start,t_end]` contains its reported `t` (±15 s); then
per quantity `score_q = clamp(tau_q,0,1) · accuracy_q`, `accuracy_q = mean max(0, 1 − |pred−gt| /
max(1, 0.30·gt))`, renormalised over quantities that vary, then scaled by **coverage =
matched_races / total_races** so an omitted (or mis-timed) race contributes zero — a partial answer
cannot reach 1.0 (a correct 2-of-12 answer scores ~0.17), the full oracle stays 1.0 (regression test
`steps/solve/tests/test_coverage.py`). Scored: **items_collected (0.55)** and
**skid_time / drift-seconds (0.45)**. `skid_time` is in VIDEO seconds (rescaled from telemetry
game-seconds — see the timebase note). `spinouts` is **no longer scored** (kept as context).

**Media.** SuperTuxKart profile-mode GT — 12 races × 10 karts × 4 laps on SuperTux (hardest) AI,
camera locked to the hero kart `tux`, 55.1 min, race.mp4 sha `4b4cee91…`, 1280×720, no audio, HUD
powerup slot masked.

## Strong-agent calibration lineup (image-parity)

Every row is a fresh run under the **shipped task image's tool surface** — a stdlib-only `python3`
(no `numpy`/`opencv`/`PIL`/`scipy`, exactly as in `python:3.12-slim`) plus `ffmpeg`/`ffprobe` and
coreutils — driven by the **final agent prompt** (no scoring formula, weights, or telemetry-GT
source). It replaces an earlier lineup that let the agents call host-only `opencv`/`numpy` (absent
from the image); removing those tools lowers every score and *widens* the margin under the family's
<0.10 bar. The audit record for each row is the agent's **full raw session transcript** (every tool
call, output, turn, and frame; only secrets + local paths redacted → `/workspace`), hosted immutably
on HF and pinned by revision with whole-file SHA256 in `rollouts/README.md`. Reward/solution dumps
are alongside on HF.

| harness (version) | model | reasoning | reward | tool-call turns | trajectory |
|---|---|---|---|---|---|
| Codex CLI (0.145.0) | gpt-5.6-sol | xhigh | **0.0101** | ~163 | image-parity raw archive (`rollouts/README.md`) |
| Claude Code CLI (2.1.241) | claude-opus-4-8 | extended thinking | **0.0436** | 104 | image-parity raw archive (`rollouts/README.md`) |
| Gemini CLI (0.57.0) | gemini-3.5-flash | default | **0.0082** | 189 | image-parity raw archive (`rollouts/README.md`) |

All measured on the shipped video (sha `4b4cee91…`) + shipped 2-dim scorer, in the image-parity
sandbox. Strong-agent **max 0.0436 (< 0.10)** — now **Claude Opus 4.8**. Gemini, the opencv-era max
(0.0885), collapses to **0.0082** once it can no longer colour-threshold frames with opencv,
confirming that number was tool-inflated. Per-dim accuracies stay low for every agent (items
0.01–0.22, skid 0.00–0.06): none can count masked-HUD pickups or time cumulative drift to within 30%
off raw frames + model vision. Rollout dumps (solution.json + reward.json) on HF, pinned to the
immutable revision (not mutable `main`; trajectory SHA256s in `rollouts/README.md`):
<https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/b49ffb9b8d83405dba6ab8dee30126bd1d53f196/kart-race-telemetry-ledger-s1/calibration>

## Results & ablations (shipped 2-dim scorer)

| submission | reward | notes |
|---|---|---|
| oracle | **1.0000** | harness path (`solve.sh` → `judge.py`); items & skid both tau 1.0, acc 1.0 |
| correct counts, wrong times | 0.0000 | right values at shuffled video times — the ±15 s window rejects |
| blind guess (random) | ~0.027 | seed-dependent (0.007–0.03); the tau gate collapses guessing |
| single frame | 0.0000 | one frame → no per-race differentiation → constant → tau 0 |
| no media / OCR-only | 0.009 / 0.0 | no scored quantity is on-screen text (HUD masked, off-HUD) |
| constant counts | 0.0000 | all races equal → predicted ties → 0 |
| empty | 0.0000 | |

Per-dim on the image-parity runs: **items** accuracy 0.01–0.22 (agents mis-count pickups under the
masked HUD — under-counting off raw frames, or over-counting when they guess high, so rarely within
30%); **skid** accuracy 0.00–0.06 (none can sum cumulative drift to within 30% over a 55-min video
without opencv). Both defeat the agent; the oracle is 1.0 and a within-30% agent would score far
higher.

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
(timebase fix) → + **drop spinouts** (too countable — with spinouts scored 0.073/0.103/0.186,
breaking the bar) → items+skid. Under the host-tool lineup this settled at Codex mean 0.027 / Gemini
max 0.0885; re-run in the **image-parity sandbox** (opencv/numpy removed, as in the shipped image)
the whole lineup drops — **max 0.0436 (Claude)**, Codex 0.0101, Gemini 0.0082. See `SPEC.md`.
