# Calibration — kart-race-telemetry-ledger-s1

**Scorer as shipped:** `reward = max(0, mean_races[0.65·tau(items_collected) + 0.35·tau(times_exploded)])`,
where tau is the *signed* normalised Kendall correlation over kart pairs, aggregated across races
and fields and clamped once at the end. Two off-HUD event counts — see "Which fields and why".

**Media as shipped:** SuperTuxKart profile-mode ground truth — 5 races (hacienda, snowmountain,
lighthouse, cornfield_crossing, scotland) × **10 karts** × 4 laps, SuperTux (hardest) AI,
23.2 min, 1280×720, no audio.

## Results

| run | score | turns | tokens | notes |
|---|---|---|---|---|
| oracle | **1.0** | — | — | harness path (`solve.sh` → `judge.py`); 5 races, 10/10 karts, all tau = 1.0 |
| blind guess (random counts) | **0.029 ± 0.041** | — | — | 600 trials, p95 0.116 |
| constant counts (all karts equal) | 0.0 | — | — | |
| leaderboard-only (ranking column + grid, no pickup info) | 0.0 | — | — | |
| empty | 0.0 | — | — | |
| **Codex `gpt-5.6-sol` (xhigh) — shipped 6×12, items+explosions, TARGETED** | **0.1495** | **33** | 1,369,349 | rollout `rollouts/codex_items_explosions_*.json` |
| Codex, same media, items-only, targeted | 0.335 | 34 | 1,050,734 | superseded scorer |
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


## Correction: the 0.066 items-only figure was a methodological error

`items-only ≈ 0.066` was obtained by **re-scoring an old rollout** that had been produced while the
agent was asked to report items *and* nitro *and* positions. That is not a valid estimate of the
items-only task's difficulty, and it flattered the task.

Run properly — Codex given the shipped 6x12 media and asked *only* for the powerup counts — the
score is **0.335** (34 turns, 1.05M tokens), against a blind floor of 0.035 ± 0.055. That is ~5σ
above chance: real, substantial skill.

**Narrowing the scored target made the task easier, not harder.** Concentrating the agent on one
quantity concentrated its effort on that quantity. The intuition that "score only the hard field"
would push the score down was wrong, and it was wrong in a way only a fresh targeted run could
reveal.

Per-race spread is wide (lighthouse **−0.300**, black_forest **+0.591**), i.e. Codex is genuinely
good on some tracks and actively inverted on others.

### Honest standing of this task
It is a **medium-difficulty** task at ~0.33, not a <0.10 one. Every previous claim in this file
that it cleared the bar came from a measurement that was later shown to be too weak or invalid:

| claim | value | why it was wrong |
|---|---|---|
| 4×6, 4 fields | 0.557 | scorer rewarded leaderboard reading |
| 4×6, items+nitro rescore | 0.064 | 60 tau-pairs — inside the noise band |
| 5×10, items+nitro | 0.170 | valid, and above the bar |
| 5×10, items-only rescore | 0.066 | **invalid** — rescored a differently-targeted rollout |
| **6×12, items-only, targeted** | **0.335** | the honest number |

Rule taken from this: never estimate difficulty by re-scoring a rollout produced under a different
objective, and never treat a single run inside the blind band as a pass.


## Broadening the scored target worked — the decisive experiment

The previous round established, uncomfortably, that *narrowing* the task made it easier: scoring
items alone let the agent pour all its effort into one quantity and it reached 0.335. The obvious
inverse hypothesis was that **broadening** would divide that effort. It was then tested rather than
assumed, with a fresh targeted run on identical media:

| scorer on the same 6×12 media | Codex | turns | tokens |
|---|---|---|---|
| items only | 0.335 | 34 | 1,050,734 |
| **items 0.65 + explosions 0.35** | **0.1495** | 33 | 1,369,349 |

Codex spent **more** tokens (1.37M vs 1.05M) for **less than half** the score. Per-race, three of
six races are now at or below zero (snowmountain −0.021, lighthouse 0.013, scotland −0.072), with
only black_forest (0.418) and hacienda (0.303) strong.

Standing: **0.1495 against a blind floor of 0.029 ± 0.041** — roughly 2.9σ above chance, and close
to but not yet under the family's <0.10 bar.

### Why `times_exploded` and not something else
Chosen on measured density and witnessability across the six shipped races, not on the score it
produced:

| candidate | distinct values in ≥6-of-12 karts | visually verifiable? | scored? |
|---|---|---|---|
| `bonus_count` (items) | 6/6 races | yes — kart drives through a question-mark box | **yes** |
| `explosion_count` | 4/6 races | yes — kart is thrown into the air and spins out | **yes** |
| `banana_count` | 1/6 races | yes | no — too sparse to rank |
| `bubblegum_count` | 1/6 races | yes | no — too sparse to rank |
| `rescue_count` | 0/6 races | yes | no — near-constant |
| `small/large_nitro` | 5/6 races | **partly** — boost flames are a proxy | no |
| `brake_count` | 6/6 races | **no** — braking has no visual tell | no — density alone is not enough |

### If more hardening is wanted
The remaining levers are field size (16–20 karts: more to track *and* more tau-pairs) and denser
item spawns. Adding a third scored count is **not** a good lever: the only candidates left are
near-constant, so an all-zeros guess would earn free credit — the same defect that removed rescues
and bananas.
