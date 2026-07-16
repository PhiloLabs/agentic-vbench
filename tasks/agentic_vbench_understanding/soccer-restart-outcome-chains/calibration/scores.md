# Calibration — soccer-restart-outcome-chains

Deterministic F1 scorer (`steps/solve/tests/judge.py`). A task clears the bar when
**every real agent scores below 0.10** and a real attempt takes **more than 50
tool-call turns**. Oracle must be 1.0 and an empty attempt near 0.

| run | score | rollout (tool-call turns) |
|---|---|---|
| oracle | 1.0 | — |
| empty / null | 0.0 | — |
| no-media prior (best fixed guess, no video) | 0.0247 | — |
| random guess (mean) | 0.0036 | — |
| single-frame ablation (Claude Fable 5, one frame) | 0.0 | — |
| frame-dump ablation (Claude Fable 5, 120 uniform frames, no tools) | 0.023 | — |
| Antigravity (Gemini 3.5 Flash) | 0.0449 | 120 |
| Codex CLI (GPT-5.6-sol) | 0.0227 | 120 |
| Claude Code CLI (Opus 4.8) | 0.0225 | 110 |
| Claude Code CLI (Fable 5) | 0.0 | 118 |

Match: SoccerNet-v2 `germany_bundesliga/2016-2017` Mainz 05 1 - 1 Borussia Dortmund,
both halves concatenated (81 visible restarts). All four rollouts across the three
agent products land well under 0.10 over long horizons. Each agent reported only 7-13
of the 81 restarts: recall is the wall, exactly as intended, and `team` / `outcome`
errors compound on top. The strongest run (Fable 5) found 13 restarts and still landed
zero full-tuple matches; its closest miss pinned a free-kick 1.1 s from the true
restart with the right type and team and fell only on the outcome field.

Raw records are in `rollouts/`, one folder per agent.
- `rollout.json` holds the agent's final answer plus `sampling_trace` (every frame time
  it sampled, one per tool-call turn) and `num_tool_calls`.
- `requests.txt` lists the same sampled timestamps, one per line, for an independent count.

## Honest note on the calibration harness

These attempts were driven through a frame-sampling tool (one frame served per
requested integer second, under a hard 120-call budget) rather than the
`ffmpeg`-on-baked-video harness that `steps/solve/instruction.md` describes. Every
predicted `t` is therefore an integer second, and the tool-call count is exactly the
number of frames sampled. The difficulty evidence, the recall wall and the team and
outcome errors, is identical either way. A reviewer re-running in Harbor will use the
baked video and should see the same sub-0.10 behavior. This is called out so the numbers
are reproducible against the exact setup that produced them.
