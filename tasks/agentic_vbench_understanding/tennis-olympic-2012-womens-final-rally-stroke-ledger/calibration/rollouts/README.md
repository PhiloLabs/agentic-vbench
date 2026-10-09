# Rollouts

One raw agent transcript per calibrated harness, kept so a reviewer can audit the run
rather than trust a summary. See `../scores.md` for results and remaining runs.

| file | harness |
|---|---|
| `codex-gpt-5.6-sol.jsonl` | Codex CLI |
| `claude-opus-4.8.jsonl` | Claude Code CLI |
| `antigravity-gemini-3.5-flash.log` | Antigravity (pending) |

Audit each trajectory for web lookups and for recall of the match before trusting its
score: the instruction forbids both.

The Codex transcript was copied byte-for-byte from the CLI session rollout. Its agent
commands contain no external URL, web-search call, `curl`, or `wget`; a
credential-pattern audit found no credential value in the agent event stream. Its
solution and reward files were removed from the repo. The run used the `skillbench`
conda environment and Harbor 0.22.0 with Codex CLI 0.154.0, `gpt-5.6-sol`, and medium
reasoning. It made 88 tool calls and scored 0.087591.

The Claude transcript is Claude Code 2.1.270's `stream-json` output (`claude-code.txt`)
for `claude-opus-4-8` at medium reasoning. The run made 204 main-session tool calls and
scored 0.101806. The audit
found no `[REDACTED]` string, credential value, `curl`/`wget`, or web tool call.
