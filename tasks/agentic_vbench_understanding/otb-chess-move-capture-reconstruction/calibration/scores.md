# Calibration Scores

The replacement source and human-verified 104-ply ground truth are used by all
three primary rollouts below. Codex is a natural-prompt run. Claude Code and
Antigravity each received one content-free persistence checkpoint so an account
or print-window interruption could not erase the current best submission.

## Primary Agent Rollouts

| harness | harness version | model | reasoning effort | score | tool-call turns | trajectory |
|---|---:|---|---:|---:|---:|---|
| Codex CLI | 0.144.2 | GPT-5.6 Sol | high | 0.0379 | 237 | [raw trajectory](rollouts/codex-transcript.jsonl) |
| Claude Code CLI | 2.1.204 | Claude Opus 4.8 | high | 0.0 | 91 | [raw trajectory](rollouts/claude-transcript.jsonl) |
| Antigravity CLI | 1.1.5 | Gemini 3.5 Flash | medium | 0.0 | 51 | [raw trajectory](rollouts/antigravity-transcript.jsonl) |

## Run Details

- **Codex** (`codex-natural-chess-20260719T062119Z`) used the canonical prompt
  with path-only rewriting and no pacing instruction. It naturally completed
  237 shell calls, predicted 45/104 plies and 17/26 captures, and passed 13/343
  checks. Temporary analysis frames escaped the requested workspace, but the
  run did not access ground truth or public game data.
- **Claude Code** (`claude-opus-checkpoint-chess-20260723T183709Z`) ran in a
  fresh isolated workspace. A persistence checkpoint was sent after 41 tool
  results. It then continued naturally to 91 tool uses/results, with 88 allowed
  and three denied by the isolation hook. Its valid final submission predicted
  `draw` with empty move and capture lists and passed 0/287 checks. Fable 5 was
  unavailable to this account before sampling, so the approved Opus 4.8 model
  was used instead. The invoked CLI executable reported version 2.1.204; its
  emitted session-init events separately identify `claude_code_version` as
  2.1.197, and both values are retained in the trajectory.
- **Antigravity** (`antigravity-checkpoint-chess-20260723T192017Z`) ran in a
  fresh sandbox with a workspace-local 1.1.5 pre-tool hook. A persistence
  checkpoint was sent after 36 calls. The run was stopped under the standing
  cap at 53 audited invocations after its score remained below 0.5; 51 allowed
  tool results completed and two package probes were denied. The 51-result
  count includes one asynchronous command after its completion notification and
  one completed, allowed artifact-call error. Its valid final submission
  predicted `unknown` with empty move and capture lists and passed 0/287 checks.

No primary rollout successfully used web tools, installed packages, accessed
ground truth, or read a prior rollout. Claude and Antigravity qualify under the
checkpoint-allowed protocol; Codex independently supplies natural-prompt
long-horizon evidence.

## Oracle And Ablations

| run | score | result |
|---|---:|---|
| oracle | 1.0 | Human-verified 104-ply sequence and 26 captures; 287/287 checks passed. |
| empty baseline | 0.0 | Empty move and capture lists; 0/287 checks passed. |
| Codex single-frame (`codex-ablation-single-frame-20260719T012741Z`) | 0.0058 | One frame at 00:13:00; 2/343 checks passed. |
| Codex no-media (`codex-ablation-no-media-20260719T012741Z`) | 0.0 | Prompt and schema only; 0/287 checks passed. |
| Codex frame-dump/no-tools (`codex-ablation-frame-dump-no-tools-20260723T181157Z`) | 0.0239 | All 46,371 frames in 52 contact sheets, zero tool calls; 7/293 checks passed. |

## Review Status

- Ground-truth review is complete. Two independent human passes confirmed the
  full sequence, Black-win result, and all move and capture timestamps.
- All three primary agents score below 0.10 and exceed 50 tool-call turns.
- The oracle, empty baseline, primary-agent, long-horizon, and three supplied
  shortcut-ablation checks pass.

## Repository Evidence

The committed evidence contains one complete raw harness trajectory for each
primary agent plus this score table. Codex retains all 485 raw events, including
`item.started` and `item.completed` records. Claude retains all 1,212 events
from its initial and checkpoint-resume streams, including binary image payloads,
thinking-token events, and opaque signatures. Antigravity retains all 114 raw
transcript events. Synthetic envelope records preserve the canonical prompts
and run metadata; only machine-specific paths are normalized. Full reward
dumps, generated media, historical attempts, and personal paths remain
untracked.
