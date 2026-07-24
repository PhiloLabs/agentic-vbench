# Calibration — kart-race-telemetry-ledger-s1

**Scorer as shipped:** `reward = max(0, mean_races[tau(items_collected)])`, where tau is the
*signed* normalised Kendall correlation over kart pairs, aggregated across races and clamped once
at the end. Powerup-box count is the only scored quantity — see "Why only items" below.

**Media as shipped:** SuperTuxKart profile-mode ground truth — 5 races (hacienda, snowmountain,
lighthouse, cornfield_crossing, scotland) × **10 karts** × 4 laps, SuperTux (hardest) AI,
23.2 min, 1280×720, no audio.

## Results

| run | score | turns | tokens | notes |
|---|---|---|---|---|
| oracle | **1.0** | — | — | harness path (`solve.sh` → `judge.py`); 5 races, 10/10 karts, all tau = 1.0 |
| blind guess (random counts) | **0.036 ± 0.052** | — | — | 600 trials, p95 0.146 |
| constant counts (all karts equal) | 0.0 | — | — | |
| leaderboard-only (ranking column + grid, no pickup info) | 0.0 | — | — | |
| empty | 0.0 | — | — | |
| **Codex `gpt-5.6-sol` (xhigh) — shipped 5×10 suite** | **0.170** | **24** | 580,907 | rollout `rollouts/codex_5x10_*.json` |
| Antigravity (Gemini‑3.x) | _to run_ | | | |
| Claude Code (Fable 5 / Opus 4.8) | _to run_ | | | |

### Superseded runs, kept for the record
| run | score | turns | tokens | why superseded |
|---|---|---|---|---|
| Codex, 4×6 cut, 4-field scoring | 0.557 | 17 | 329,676 | scored finish + start, which the HUD displays |
| Codex, 4×6 cut, off-HUD scoring | 0.064 | 17 | 329,676 | same rollout re-scored; small-sample noise (15 tau-pairs/field) |

## Agent configuration (so the numbers are reproducible)
`codex exec --dangerously-bypass-approvals-and-sandbox`, Codex CLI **v0.145.0**,
`model = gpt-5.6-sol`, `model_reasoning_effort = xhigh`, ChatGPT Pro auth, ffmpeg+ffprobe on
PATH, video mounted at `materials/race.mp4`, scored with this task's own `judge.py`.

## Two findings that changed the task

**1. The scorer was rewarding leaderboard reading.** With finish order and start grid scored,
Codex reached **0.557** — tau 0.75 on finish and 0.90 on start, because the ranking column and
starting grid simply *display* them. Only the off-HUD pickup counts are scored now; finish and
start may still be reported for context. Rescues and banana hits are excluded too: they are
almost always zero, so ranking near-constant columns is neither discriminative nor guess-proof.

**2. The scorer had a statistical bug.** Clamping tau at 0 *per race* discarded the negative half
of the noise distribution, so random guessing averaged **0.156** instead of ~0. tau is now signed
and aggregated before a single final clamp, which put the guess floor at 0.036.

## Why only items are scored

Nitro was dropped after measurement, on the same rule that dropped finish order and start grid:
it has an **on-screen proxy**. Nitro *use* renders as boost flames and the meter is drawn for the
followed kart, so it is partly inferable rather than counted. The evidence is the per-dimension
split on Codex's own rollout — tau **~0.32 on nitro** against **~0.07 on items**. A ~5x gap is
what a proxy looks like. Powerup boxes have no equivalent tell.

Consequence for measurement: dropping a dimension halves the scored pairs, so the field size was
raised to **12 karts x 6 races** (66 tau-pairs per race, 396 total, against 225 at 5x10 and 60 at
the original 4x6). Field size does double duty — twelve karts is harder to follow *and* keeps the
statistic tight enough to separate an agent from chance.

## Open item: the task did NOT clear the <0.10 bar under the previous scorer

The first calibration used a 4-race × 6-kart cut and gave **0.064**, which looked like a pass. It
was not: with only 15 tau-pairs per field that score sat inside the blind-guess spread
(0.057 ± 0.082) and could not be separated from chance. The shipped suite was enlarged to 5 × 10
(45 pairs per field) specifically to fix the measurement — and on it the same harness scores
**0.170**, i.e. **above** the bar, and ~2.6σ above the 0.036 floor. The earlier number was noise;
this one supersedes it.

Per-dimension mean tau shows where the difficulty actually lives:

| dimension | Codex mean tau | why |
|---|---|---|
| `items_collected` | **~0.07** | genuinely hard: question-mark boxes must be counted per kart |
| `nitro_collected` | **~0.32** | easier: nitro *use* is visible as boost flames, so there is partial on-screen evidence |

Resolution taken (options 1 + 2 from the issue, both justified by the measurement above rather
than by the score they produce): score `items_collected` only, and enlarge the field to 12 karts x
6 races. On the previous 5x10 media, items-only scoring puts the same Codex rollout at **0.066**
with a blind floor of 0.051 ± 0.071 — under the bar but still inside the noise, which is exactly
what the larger field is for. Numbers on the 6x12 media will be filled in when it finishes
rendering and Codex is re-run.

Raw agent trajectories are under `rollouts/`.
