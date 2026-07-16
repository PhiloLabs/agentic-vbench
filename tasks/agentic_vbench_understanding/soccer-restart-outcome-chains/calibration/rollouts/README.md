# Rollouts

One folder per agent. Every folder has three layers of evidence:

1. `rollout.json` — the machine-readable summary: the agent's final answer,
   `model`, `num_tool_calls`, and `sampling_trace` (every frame time it sampled,
   one per tool-call turn).
2. `requests.txt` — the harness-side log of the same sampled timestamps, one per
   line, written by the sampling tool itself, for an independent turn count.
3. `transcripts/` — the raw transcript of the run, so tool use and the absence of
   web access can be audited directly. Image payloads inside transcripts are
   replaced with `[image elided: N bytes]` placeholders; everything else
   (reasoning, tool calls, tool results, timestamps) is verbatim.

Per agent:

- **claude-code** — `transcripts/opus48-full-capped.jsonl`: the raw Claude Code
  subagent transcript of the 110-call run (model `claude-opus-4-8`, recorded in
  every assistant message of the file).
- **claude-code-fable5** — a second, independent Claude Code run with the newest
  model (`claude-fable-5`, recorded in every assistant message): 118 calls, 13
  reported restarts, score 0.0. `transcripts/fable5-full-run.jsonl` is the raw
  transcript; `reward.json` the scored result.
- **codex** — four `transcripts/rollout-2026-07-13T02-4*.jsonl` files: the raw
  Codex CLI session logs of one MCP run with network access disabled
  (`sandbox_workspace_write.network_access: false`); the 02-41-41 file is the
  main thread, the other three are worker threads it spawned. Model
  `gpt-5.6-sol`, recorded in the session headers.
- **antigravity** — `transcripts/conversation-210bdb70.db`: the raw SQLite
  conversation database the Antigravity desktop app wrote for this run (open with
  `sqlite3`, table `steps`, 300 steps), plus `steps-extracted.txt`, a readable
  per-step string extraction for convenience. Model recorded in the payloads:
  `Gemini 3.5 Flash (Medium)`. The run used Antigravity's Sandbox Mode with the
  browser disabled and file access outside the working folder denied.

An additional integrity check that needs no transcript: frames were only ever
served at integer seconds, so any answer containing a non-integer `t` (like the
ground truth's millisecond values) could only have come from the label file. All
rollouts here contain integer times only.
