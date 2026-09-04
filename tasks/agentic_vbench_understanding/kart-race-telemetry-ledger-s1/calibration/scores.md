# Calibration — kart-race-telemetry-ledger-s1

> **VOID as of 2026-09-04 — every agent score on this page was measured on the previous media
> instance.** Two defects were fixed at the source since: the drift timebase (a patched STK now
> measures real drift in wall-clock seconds, replacing a rescale of a skid-INPUT statistic) and the
> HUD mask box (hand-fitted 35 px too narrow on the left, so five held items left a 17 px sliver of
> the leftmost icon visible). Both changes require a fresh render, and STK profile mode is not
> reproducible run-to-run, so the current suite is a NEW instance: the strong-agent figure and the
> agent ablations here do not transfer and the gate-setting pilot must be re-run before merge.
> What HAS been re-measured on the current ground truth, because it needs no agent: oracle 1.0000,
> blind_guess 0.0173 (mean of 20 seeds, 0.0000–0.0468), correct_counts_wrong_times 0.0075,
> constant/single-frame 0.0000, empty 0.0000. The scorer itself is unchanged and its 22 regression
> checks pass against the new ground truth.

**Scorer (as shipped).** TIME-ANCHORED + EXACT. Each predicted race is matched to a GT race by an
**optimal (assignment-safe, min-cost max-cardinality) bipartite matching** on its reported `t` — a
prediction whose `t` is contained in a GT segment is preferred, else one within **±15 s** is
eligible. Segments are **half-open** `[t_start,t_end)` (the final race keeps its right end), so a
shared boundary `t_end == next t_start` belongs to the **later** race; the matcher's matrix is
**bounded to O(n_gt²)** regardless of how many rows are submitted. Then per quantity
`score_q = clamp(tau_q,0,1) · accuracy_q`, where
`accuracy_q = (Σ over matched pairs carrying q of max(0, 1 − |pred−gt| / max(1, 0.30·gt))) / N_GT_RACES`
and `reward = Σ_q w_q·score_q` renormalised over quantities that vary in the GT. **Coverage is folded
per dimension** via that denominator: a GT race with no matched prediction — or a matched prediction
that omits quantity `q`, or gives a non-finite value — contributes 0 to `q` only. So an items-only
answer earns its honest items credit while the other field scores 0, a dummy field can neither
inflate nor erase another field's credit, and a partial answer still cannot reach 1.0 (a correct
2-of-12 answer scores ~0.17) while the full oracle stays 1.0. Malformed `races` (null/non-list)
normalize to `[]` (score 0, no crash). Regression-tested in `steps/solve/tests/test_coverage.py`.
`spinouts` is **not scored** (kept as unscored context).

**Media.** SuperTuxKart profile-mode GT — 12 races × 10 karts × 4 laps on SuperTux (hardest) AI,
camera locked to the hero kart `tux`, 56.2 min, race.mp4 sha `ee7d966e…`, 1280×720, no audio, HUD
powerup slot masked with the box derived in `generator/hud_mask.py`.

## Tool profile (documented)

The task ships the standard CV/array stack **pinned in `environment/Dockerfile`** — `numpy==2.1.3`,
`Pillow==11.0.0`, `opencv-python-headless==4.10.0.84` — alongside `ffmpeg`/`ffprobe` and the Python
stdlib, with no solve-time network (`task.toml` `allow_internet=false`). These are normal CV tools an
agent is expected to have (cf. #45/#46/#47/#85); the difficulty is off-HUD counting/timing over a
55-min video, not tool withholding. **This is the profile the gate-setting calibration must run
under.**

## Strong-agent calibration lineup (host-run — clean image pilot PENDING)

Status: the numbers below are **host-run** (on our compute node; Docker is unavailable there and the
local sandbox did **not** fully enforce the documented profile — host packages leaked via PYTHONPATH,
CLI versions differed, and the prompt carried an uncommitted "Practical notes" suffix). They are
**indicative, not the finalized-image calibration**, and are all well under the family's <0.10 bar. A
single clean gate-setting pilot on the finalized image (pinned profile above, exact committed prompt,
`allow_internet=false`) is being run by a maintainer on a Docker/Harbor executor (see PR #106); this
table is replaced by that result.

| host-run variant | Codex gpt-5.6-sol (xhigh) | Claude Opus 4.8 | Gemini 3.5-flash |
|---|---|---|---|
| **with CV tools** (matches the pinned profile; earlier 3-field prompt, re-scored 2-dim) | 0.030 / 0.000 / 0.052 | 0.045 | **0.0885** |
| **stdlib-only sandbox** (final 2-field prompt; CV tools withheld) | 0.0101 | 0.0436 | 0.0082 |

Both variants sit under 0.10; the with-CV-tools Gemini row (0.0885) is the historical gate-setter and
the tightest to the bar. The audit record for each stdlib-sandbox run is the agent's **full raw
session transcript** (every tool call, output, turn, frame; only secrets + local paths redacted →
`/workspace`), on HF pinned by revision + whole-file SHA256 in `rollouts/README.md`
(`resolve/b49ffb9b8d83405dba6ab8dee30126bd1d53f196/`). The earlier with-CV-tools archives remain at
their prior revisions. Per-dim accuracies stay low across the board (items 0.01–0.22, skid 0.00–0.06):
no agent counts masked-HUD pickups or times cumulative drift to within 30%.

## Results & ablations (shipped 2-dim scorer)

| submission | reward | notes |
|---|---|---|
| oracle (mid-window t) | **1.0000** | harness path (`solve.sh` → `judge.py`); items & skid both tau 1.0, acc 1.0 |
| oracle reporting every race at its `t_start` | **1.0000** | permitted by the prompt; assignment-safe matching prefers true segment containment (was 0.0111 under greedy) |
| correct items-only (skid omitted) | 0.5500 | per-dimension coverage: honest items credit; a dummy `skid_time:0` neither raises nor erases it |
| correct counts, wrong times | 0.0000 | right values at shuffled video times — the ±15 s window rejects |
| blind guess (random) | ~0.027 | seed-dependent (0.007–0.03); the tau gate collapses guessing |
| single frame | 0.0000 | one frame → no per-race differentiation → constant → tau 0 |
| no media / OCR-only | 0.009 / 0.0 | no scored quantity is on-screen text (HUD masked, off-HUD) |
| constant counts | 0.0000 | all races equal → predicted ties → 0 |
| `races: null` / malformed | 0.0000 | normalized to `[]` (no crash) |
| empty | 0.0000 | |

All rows above are backed by `steps/solve/tests/test_coverage.py` (22 checks) and the family
`check_task.py` gate. Per-dim on the host-run agents: **items** accuracy 0.01–0.22 (agents mis-count
pickups under the masked HUD — under-counting, or over-counting when they guess high, so rarely within
30%); **skid** accuracy 0.00–0.06 (none sum cumulative drift to within 30% over a 55-min video). Both
defeat the agent; the oracle is 1.0 and a within-30% agent would score far higher.

## skid_time timebase (correctness) — SUPERSEDED 2026-09-04

**How it works now.** A patched SuperTuxKart integrates the kart's real skid state in **wall-clock**
seconds, and the capture records at a constant wall-clock rate, so the scored `skid_time` is already
in video seconds and nothing is rescaled. The GT keeps `skid_actual_game`, `skid_input_game`,
`skid_showgfx_game` and `render_speed_factor` per race as unscored context. See SPEC.md "SKID
TIMEBASE" and generator/README.md "Actual-skid instrumentation".

**What this replaced, and why.** The previous revision took STK's stock statistic — which counts the
time the skid INPUT was held, 1.136x–1.378x above the real drift on the current suite — and rescaled
it by the race's render factor, `skid_time_game · (video_clip_duration / game_race_duration)`. That
factor is not the drift's own factor: on the current suite the render factors run 1.128–1.927 while
each race's drift wall/game ratio runs 1.033–1.765, disagreeing by up to 0.241 (cocoa_temple, 1.927
vs 1.686). The render factors measured on the PREVIOUS instance were: hacienda 1.13, snowmountain
1.31, cornfield 1.56, lighthouse 1.47, gran_paradiso 1.87, sandtrack 1.23, olivermath 1.18,
cocoa_temple 1.75, scotland 1.28, fortmagma 1.31, ravenbridge 1.47, stk_enterprise 1.13 (mean 1.39).
The fields `skid_time_game` and `speed_factor` no longer exist.

## Provenance / hardening (all measured, Codex xhigh)

hero-scope + rank agreement 0.407 → + HUD powerup mask 0.345 → + exact-count metric (accuracy, not
rank) → + time-anchored (races matched by video time ±15 s) → + skid rescaled to video-seconds
(timebase fix) → + **drop spinouts** (too countable — with spinouts scored 0.073/0.103/0.186,
breaking the bar) → items+skid. Host-run under the pinned CV-tool profile this settled at Codex mean
0.027 / Gemini max **0.0885** (< 0.10); the stdlib-only cross-check (CV tools withheld) is lower still
(max 0.0436). The authoritative gate-setting number awaits the clean image pilot (see the lineup
section and PR #106). See `SPEC.md`.
