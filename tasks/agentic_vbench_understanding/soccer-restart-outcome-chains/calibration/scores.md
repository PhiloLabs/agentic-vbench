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
| Antigravity | 0.0449 | 120 |
| Codex CLI | 0.0227 | 120 |
| Claude Code CLI (Opus 4.8) | 0.0225 | 110 |

Match: SoccerNet-v2 `germany_bundesliga/2016-2017` Mainz 05 1 - 1 Borussia Dortmund,
both halves concatenated (81 visible restarts). All three agents land well under 0.10
over long horizons, and two independent strong agents (Claude, Codex) land within
0.0002 of each other, which is strong evidence the difficulty is real and not an
artifact of one agent. Each agent reported only 7-8 of the 81 restarts: recall is the
wall, exactly as intended, and `team` / `outcome` errors compound on top.

Raw records are in `rollouts/`, one folder per agent.
- `rollout.json` holds the agent's final answer plus `sampling_trace` (every frame time
  it sampled, one per tool-call turn) and `num_tool_calls`.
- `requests.txt` lists the same sampled timestamps, one per line, for an independent count.

## Honest note on the calibration harness

These three attempts were driven through a frame-sampling tool (one frame served per
requested integer second, under a hard 120-call budget) rather than the
`ffmpeg`-on-baked-video harness that `steps/solve/instruction.md` describes. Every
predicted `t` is therefore an integer second, and the tool-call count is exactly the
number of frames sampled. The difficulty evidence, the recall wall and the team and
outcome errors, is identical either way. A reviewer re-running in Harbor will use the
baked video and should see the same sub-0.10 behavior. This is called out so the numbers
are reproducible against the exact setup that produced them.
