# Calibration — kart-race-telemetry-ledger-s1

**Scorer as shipped:** `reward = max(0, mean_races[0.60·tau(items) + 0.40·tau(nitro)])`, where
tau is the *signed* normalised Kendall correlation over kart pairs, aggregated across races and
fields and clamped once at the end.

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

## Open item: the task does NOT currently clear the <0.10 bar

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

Options are filed on the proposal issue (PhiloLabs/agentic-vbench#73) rather than decided
unilaterally, because tuning the weights until the task "passes" would be fitting the metric to
the desired answer: (1) restrict scoring to `items_collected` (Codex ≈ 0.07), (2) scale the field
to 12–16 karts, or (3) accept it as a medium-difficulty entry at ~0.17.

Raw agent trajectories are under `rollouts/`.
