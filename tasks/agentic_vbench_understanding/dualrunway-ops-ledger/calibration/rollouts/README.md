# Rollouts

Raw agent transcripts behind the table in `../scores.md`, so a reviewer can confirm each
score was earned honestly and count the tool-call turns independently.

| file | agent | reward | turns |
|---|---|---|---|
| `claude-code-opus-5-20260802.jsonl` | Claude Code CLI, `claude-opus-5` | 0.0 | 93 |
| `antigravity-gemini-3.5-flash-20260802.jsonl` | Gemini CLI, `gemini-3.5-flash` | 0.0 | 260 |
| `antigravity-gemini-3.1-pro-20260802.jsonl` | Gemini CLI, `gemini-3.1-pro-preview` | 0.0 | 101 |
| `codex-gpt-5.6-sol-20260802.jsonl` | Codex CLI, `gpt-5.6-sol` | 0.0741 | 29 |

`codex-gpt-5.6-sol-20260802.solution.json` is the only submission that scored above zero
— five operations, two of them fully correct.

All four ran on one 40-core Linux host with the shipped resource settings (8 cpus, 8 GB,
7200 s) and the shipped `instruction.md`. Every run ended on its own; none hit the cap.

Counting turns: Claude and Gemini emit `type: "tool_use"` events; Codex emits
`item.completed` with an item type of `command_execution` / `file_change`.

Two things a reviewer should know about how these were produced:

- The container had network, because the agent CLI runs inside it and has to reach its
  model API. The real Harbor trial runs `allow_internet=false`. Web tools were disabled
  explicitly and the transcripts were scanned for `curl`/`wget` — none appear. `pip
  install` would work here and would not in the real trial; nothing in these four runs
  depended on it.
- Model identity was verified rather than assumed. `gemini-cli` 0.53.1 silently accepts
  an unknown `-m` value and falls back to `gemini-3.5-flash` while still echoing the
  requested name in its `init` event — only the per-model token counts in the `result`
  event reveal it. Codex, by contrast, hard-fails on an unknown model. The two Gemini
  files here were confirmed against those token counts.
