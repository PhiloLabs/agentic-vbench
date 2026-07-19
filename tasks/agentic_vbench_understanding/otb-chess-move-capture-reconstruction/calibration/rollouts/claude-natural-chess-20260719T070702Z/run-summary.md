# Natural-Prompt Claude Attempt Summary

- Agent: Claude Code CLI 2.1.204, `claude-sonnet-5`, high effort
- Run id: `claude-natural-chess-20260719T070702Z`
- Launch mode: fresh nonpersistent session with safe mode, slash commands and
  MCP servers disabled, web tools denied, and permission bypass inside a clean
  local workspace
- Source: silent 1280x720 replacement video, SHA-256
  `b9839b0e67c02ffa4ae9a7662809b25a045f6feff9749844bb66eb19d6a99420`
- Prompt variant: exact benchmark instruction with only the two `/workspace`
  paths rewritten to the clean local workspace; normalizing those paths restores
  the benchmark instruction byte for byte
- Final status: failed before submission when Claude returned `You've hit your
  session limit - resets 5am (America/Los_Angeles)` with API status 429
- Reward: `0.0` (`0/287` checks passed) because no `output/solution.json` was
  produced
- Rollout length: 210 completed tool-use blocks; Claude reported 212 native
  turns
- Runtime: 40 minutes 50 seconds
- Reported cost: `$22.4820501`

Claude sampled the full video, built a 5 fps motion-difference scan, selected
117 candidate settled positions, and repeatedly calibrated a board homography,
square labels, normalized crops, and high-resolution comparisons. It spent most
of the run correcting camera geometry and resolving the opening. Its final
partial notes contained only five provisional plies:

```text
1. e4 49.0
1... e5 50.5
2. Nf3 54.6
2... d6 78.0
3. Nc3 104.8
```

Those notes already diverged from the verified record by missing `2...Nc6`,
`3.Bb5 Nge7`, and `4.O-O` before the later `Nc3`. They were never serialized as
a submission and therefore were not scored as predicted moves.

The launch first encountered an invalid empty-MCP configuration before any
Claude session began. That setup-only error is preserved separately and is not
included in the turn count. During the real run, Claude installed the generic
`python-chess` package with `pip`; this is a harness caveat because the task
environment declares no internet, although Claude made zero web search/fetch
requests and did not retrieve the game or its moves. It also wrote two temporary
lists under `/tmp` containing only names of its own generated frames. Neither
action exposed ground truth or prior rollout artifacts.

This attempt naturally passes the long-horizon gate (`210 > 50`) and is useful
failure evidence, but it is not a completed cross-agent calibration because the
subscription limit stopped Claude before submission. A fresh post-reset Claude
run remains pending.
