# Calibration — industreal-multivideo-procedure-step-ledger

The current task is the complete-state checkpoint version described by `SPEC.md`.
Reward is deterministic checkpoint F1. A full match requires the correct anonymized
video, completion time within 2 seconds, every changed procedure-step ID, and the
complete 11-component post-transition state.

## End-to-end agents

| harness | harness version | model | reasoning | score | tool-call turns | trajectory |
|---|---|---|---|---:|---:|---|
| Oracle | Harbor 0.6.6 | bundled | — | 1.000000 | — | deterministic oracle |
| Nop / null | Harbor 0.6.6 | none | — | 0.000000 | 0 | empty output |
| Codex CLI | 0.144.6 via Harbor 0.6.6 | `openai/gpt-5.6-sol` | high | 0.065934 | 108 | `rollouts/codex-gpt-5.6-sol-high.jsonl` |
| Claude Code | 2.1.220 via Harbor 0.20.0 | `claude-opus-4-8` | xhigh | 0.000000 | 492 | `rollouts/claude-code-opus-4.8-xhigh.jsonl` |
| Antigravity | 1.1.8 via Harbor 0.20.0 | `gemini-3.5-flash` | high | 0.000000 | 185 | `rollouts/antigravity-gemini-3.5-flash-high.jsonl` |

The Codex run predicted 44 checkpoints and fully matched 3 of 47 ground-truth
checkpoints: 0.068182 precision and 0.063830 recall. Thirteen predictions matched
video and time, six also matched every changed step ID, and three additionally matched
the complete post-transition state. The run lasted 30m37s. Its 0.065934 reward passes
the `< 0.10` strong-agent gate, and 108 tool calls pass the `> 50` long-horizon gate.
The submitted model output is retained next to the trajectory as
`rollouts/codex-gpt-5.6-sol-high.solution.json`.

The valid Claude run predicted 43 checkpoints. Ten predictions matched video and
time, three also matched every changed step ID, and none matched the complete
post-transition state. Its main systematic error was treating the short rear chassis
as unused even though it is active in eight ground-truth checkpoints; it also missed
the one incorrect-install state. The run lasted 4h53m including one five-hour quota
wait. Claude created seven background agents itself, all seven completed, and the
runner preserved the same process, session, and turn across the reset.

The first Claude Code 2.1.217 attempt is excluded from calibration. Its main thread
ended while seven background subagents were still running; the default ten-minute
print-mode wait then stopped them before `solution.json` was written. This is a
harness-invalid attempt, not a model score. Fresh Claude runs leave delegation to
Claude, use the retry watchdog, remove the print-mode background cutoff inside
Harbor's task timeout, and must pass the runner's required-output and
verifier-completion gates.

A second `xhigh` attempt is also excluded: it hit the Claude subscription session
limit after 31m41s, with only videos D, E, and F complete and no `solution.json`.
The measured retry uses `xhigh` again with the same task instruction and preserves
one session across subscription reset windows.

The Antigravity run passed the completion gate and finished in 2h25m04s. It identified
48 candidate checkpoints but wrote an array at the JSON root instead of the required
`{"checkpoints": [...]}` object, so the official verifier parsed zero predictions and
awarded `0.0`. A read-only diagnostic that supplied only the missing wrapper found 11
video-and-time matches, three video-time-and-changes matches, and zero complete-state
matches; its exact-match F1 therefore also remained `0.0`. The native trajectory
contains 185 tool actions: 143 file views, 36 commands, five directory listings, and
one code action. Harbor 0.20 did not produce a normalized ATIF copy for Antigravity
CLI 1.1.8, so this count comes directly from the retained native event types.

The raw trajectory retains every model message, tool invocation, and textual tool
result. Base64 image bytes and encrypted reasoning blobs are replaced with
length-and-SHA256 placeholders to avoid committing binary-equivalent payload bloat.
See `rollouts/README.md`.

## Anti-shortcut ablations

All measured ablations use Harbor 0.6.6 and `openai/gpt-5.6-sol` with high reasoning.

| condition | score | predicted | model tool calls | trajectory |
|---|---:|---:|---:|---|
| Prompt/schema, no media | 0.000000 | 0 | 5 | `ablations/no-media-codex-high.jsonl` |
| One midpoint frame per A--G video | 0.000000 | 0 | 10 | `ablations/single-frame-codex-high.jsonl` |
| Every native 10 fps frame pasted, no tools | 0.025000 | 113 | 0 | `ablations/frame-dump-no-tools-codex-high.jsonl` |

The no-media image retained only zero-byte placeholders so setup and the prompt were
unchanged. The single-frame image replaced every video with a one-frame MP4 sampled
at its temporal midpoint and retained the reference PDF.

For the frame-dump run, every source frame was placed chronologically into 20-second
contact sheets with `VIDEO START+FRAME` labels; the reference pages were attached
alongside them. Shell, unified execution, plugins, and all other tools were disabled.
The run matched 2 of 47 checkpoints. All three rewards pass the ablation gate of at
most 0.15. Exact artifact conventions and retained model outputs are documented in
`ablations/README.md`.

## Submission status

Oracle, null, Codex, Claude Code, Antigravity, and the required shortcut ablations are
measured. All required raw trajectories and submitted solutions are retained, so the
calibration table is complete.
