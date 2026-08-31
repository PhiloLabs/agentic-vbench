# Rollouts

One unabridged agent transcript per calibration run, so a reviewer can confirm each
score was earned honestly and count the tool-call turns independently. Scores and turn
counts live in `../scores.md`; this directory is the raw evidence behind them.

## Full-evidence runs (228-min video + audio + offline ASR + ffmpeg)

| file | harness | model |
|---|---|---|
| `opus5-full.jsonl` | Claude Code 2.1.220 | Opus 5, xhigh |
| `opus48-full.jsonl` | Claude Code 2.1.220 | Opus 4.8, default |
| `codex-full.jsonl` | Codex CLI 0.145.0 | GPT-5.6 Sol, xhigh |
| `antigravity-full.jsonl` | Antigravity CLI 1.1.21 | Gemini 3.5 Flash, high |

`antigravity-full.jsonl` is a host run, not a `harbor run` — see `../scores.md` §"The
Antigravity row" for why (agy authenticates only via interactive OAuth and cannot run
headless in the sandbox) and for its caveats (quota-terminated, empty submission → 0.0).

## Ablations (all Codex CLI 0.145.0, GPT-5.6 Sol xhigh)

| file | what the agent had |
|---|---|
| `codex-video-only.jsonl` | video with the audio stream removed (`-an`) |
| `codex-audio-only.jsonl` | the audio stream alone (`-vn`), no video anywhere |
| `codex-nomedia.jsonl` | prompt + vocabulary only |
| `codex-single-frame.jsonl` | one still at 6843 s |
| `codex-framedump.jsonl` | 20 stills every 684 s, no tools |

## Format

Claude Code transcripts are `--output-format stream-json`; count tool calls as
`message.content[].type == "tool_use"`. Codex transcripts are `codex exec --json`;
count `item.type == "command_execution"`. Antigravity transcripts are agy
`--output-format stream-json`; count the distinct `step_update` events that carry a
`tool_name` (dedupe by `step_index`, since one tool call emits an ACTIVE and a DONE
record). `scripts/understanding/audit_trajectory.py` counts all three formats and runs
the answer-key / web-grounding audit.

Both formats echo the full prompt in the conversation history every turn. Because that
prompt contains a prohibition list naming the answer-key files ("never open
`ground_truth*`, `oracle*`, …"), a plain `grep` for those names flags every transcript.
Audit `tool_use` **inputs** instead — `media/annotation/audit_runs.sh` does this, and
reports zero answer-key accesses across all runs shipped here.
