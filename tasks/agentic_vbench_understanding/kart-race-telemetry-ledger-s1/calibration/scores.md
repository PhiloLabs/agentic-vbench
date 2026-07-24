# Calibration — kart-race-telemetry-ledger-s1

Rank agreement (Kendall tau) over four fields per kart:
`reward = 0.45·tau(finish) + 0.15·tau(start) + 0.25·tau(items) + 0.15·tau(nitro)`,
averaged over 4 races. GT = SuperTuxKart profile-mode result table (SuperTux difficulty AI,
6 karts × 4 tracks × 4 laps, 14.6 min, 720p).

| run | score | notes |
|---|---|---|
| oracle | 1.0 | verified through harness path (solve.sh → judge.py), all 4 races tau=1.0 |
| empty | 0.0 | verified |
| blind guess (all 4 fields random) | 0.16 | 500 trials, p95 0.26 |
| grid-only (read start grid, guess finish=grid) | 0.22 | honest partial credit (see SPEC) |
| podium-only (top-3 finish right) | 0.36 | partial credit is meaningful |
| Codex `gpt-5.6-sol` (xhigh) | **0.557** | Codex CLI v0.145.0, ChatGPT Pro, 330k tokens, ~50 tool calls; rollout in rollouts/ |
| Codex `gpt-5.6-sol` (xhigh), off-HUD scoring | **0.064** | same rollout re-scored under the shipped verifier |
| Antigravity (Gemini-3.x) | _to run_ | |
| Claude Code (Fable 5 / Opus 4.8) | _to run_ | |

Raw agent trajectories saved under `rollouts/` once each harness completes.


## Calibration finding (IMPORTANT — task is NOT yet at the <0.10 hard bar)

Codex scored **0.557**, far above the family's <0.10 target. Per-dimension mean tau shows
exactly why:

| dimension | Codex tau | on the HUD? |
|---|---|---|
| start_position | 0.90 | yes — the starting grid |
| finish_position | 0.75 | yes — the ranking column |
| items_collected | 0.27 | no — count pickups over time |
| nitro_collected | 0.12 | no — count pickups over time |

The ranking column and grid **display** the finishing order and start slots, so an agent that
reads the leaderboard gets 0.60 of the weight almost for free — that is leaderboard-OCR, not
video understanding. The genuine difficulty is the pickup counting (items/nitro), where Codex
is weak (0.12–0.27).

**This is a real anti-shortcut gap, surfaced by calibration, and the task must not be
submitted as a <0.10 hard task until it is fixed.** Options:
1. **Crop the ranking column + minimap** (the leaderboard giveaway) so finish/start must be
   inferred from the race itself — the standard anti-shortcut move (cf. hiding Pokémon
   move-name text). Trades against keeping those on-screen aids.
2. **Score only the off-HUD signals** (items/nitro) and scale up karts/races; Codex is already
   ~0.12–0.27 there, so this plausibly reaches the bar.
3. Keep as-is and label it a **medium** task (~0.5), if the family accepts sub-hard entries.
Decision pending.


## Agent configuration (so the numbers are reproducible)
Codex runs: `codex exec --dangerously-bypass-approvals-and-sandbox`, Codex CLI **v0.145.0**,
`model = gpt-5.6-sol`, `model_reasoning_effort = xhigh`, ChatGPT Pro auth, ffmpeg+ffprobe on
PATH, video mounted at `materials/race.mp4`. Scored with this task's own `judge.py`.

## Media revision
The first calibration used a 4-race x 6-kart cut (14.6 min). The shipped media is now
5 races x 10 karts (23.2 min) because the smaller cut left the measurement underpowered
(blind 0.057 +- 0.082 vs an agent score of 0.064). Blind is now 0.036 +- 0.052 (p95 0.146).
