---
title: Doom checkpoint state tracking calibration
summary: Measured anchors and agent runs for the final Doom task.
read_when: Auditing final task difficulty and rollout evidence.
---

# Calibration scores

| Harness | Version | Model | Reasoning | Score | Non-plan tool-call turns | Status | Trajectory |
|---|---|---|---|---:|---:|---|---|
| Oracle | Harbor 0.6.6 | oracle | n/a | `1.000000` | n/a | complete | local job |
| Null | Harbor 0.6.6 | nop | n/a | `0.000000` | n/a | complete | local job |
| Codex | Codex CLI 0.145.0 with Harbor 0.6.6 | `gpt-5.6-sol` | xhigh | `0.065234` | 279 | complete | `rollouts/codex.jsonl` |
| Antigravity | Antigravity CLI 1.1.8 | `gemini-3.5-flash-high` | high | `0.002500` | 30 conservative | complete | `rollouts/antigravity.jsonl` |
| Claude Code | Claude Code 2.1.220 | `claude-opus-4-8` | high | `0.050308` | 315 | complete | `rollouts/claude-code.jsonl` |

The solve runs used agent-visible task checksum
`d979d6e211210017cae96e47defd5a378211cdafc40402e4277f21059d539835`.

The current reward is 90% exact full-state event-F1 and 10% gated per-field F1.
Field credit is computed only after episode, type, entity, and timestamp align.
Keys, switches, and doors require exact set equality.

The Codex run completed without a Harbor exception in 1:06:46 and submitted valid
JSON containing 92 events. The trajectory contains 281 tool calls: two plan
updates and 279 non-plan calls. Even the conservative shell-and-file count is 75.

Of 138 ground-truth events, 82 predictions matched episode, type, entity, and time.
Only three also matched the complete post-event state. Codex omitted all 18 key
pickups and all 18 locked-door openings. On the 82 identity-and-time matches,
switches and checkpoint were exact in all 82, active weapon in 60, open doors in
16, and held keys in three. Its exact full-state event-F1 is `0.025641`, gated
per-field F1 is `0.421575`, and blended reward is `0.065234`.

The committed transcript preserves all 1,148 native events in order. Image bodies
returned by 187 `view_image` calls are replaced by explicit text markers; all
non-image field values are retained. The 1,187,798-byte JSONL has SHA256
`51990feec10c24c8bd7ea3ad2b9a1bdd9d23c67c38c82731b1bcbeb3abb6f3d3`.
No URL, search, answer-key, or credential markers were found in the audited run.

The Antigravity run used a fresh workspace and CLI state directory with
the same exact image, model, and effort. An execution-only guard required
synchronous commands and prohibited schedulers and subagents. It completed with
terminal `SUCCESS` in 21:39 and wrote valid JSON containing 54 events. Six
predictions matched episode, type, entity, and time; none matched complete
post-event state. Exact full-state event-F1 is `0.000000`, gated per-field F1 is
`0.025000`, and blended reward is `0.002500`.

The native stream contains 31 tool calls: 29 `run_command`, one `view_file`,
and one `manage_task` status check for a long command that the CLI automatically
detached. No `schedule`, browser, search, or subagent call occurred. Package
installation commands used the configured package repositories; no answer-key,
verifier, or credential path occurred in tool-call parameters. Excluding the
single task-status call leaves 30 conservative calls. The 223,401-byte native
stream has SHA256
`6a5b0b6198e91cb9c9cbc9ded00d0b5ae00715fcaad7cffd5ad545c2d58d3cac`.
The solution SHA256 is
`885c6738ae641ed67051e755f9bd92f1b52e60f951ca6364b8c7703e761f37b1`.

The Claude Code run used the exact final image, `claude-opus-4-8`, high effort,
no fallback, and one session resumed across six measured segments. It completed
in about 85 minutes of active CLI time over a 28:27 wall-clock span that included
quota waits and one user pause. Two zero-token expired-auth attempts are retained
outside the measured stream.

Claude submitted valid JSON containing 93 events. Sixty-nine predictions matched
episode, type, entity, and time; two also matched the complete post-event state.
It omitted all 18 key pickups and all 18 locked-door openings. Exact full-state
event-F1 is `0.017094`, gated per-field F1 is `0.349234`, and blended reward is
`0.050308`.

The measured native stream contains 2,646 events and is 147,437,147 bytes with
SHA256 `9d8a78f43f8a12006e2968316a387adac9f0a106721325bb79fa4a80f6a31e72`.
The committed transcript preserves every event in order in one file. The 245
embedded images, duplicated in message content and tool-result metadata, are
replaced by explicit text markers. The 1,807,343-byte JSONL has SHA256
`2ba1b9ddfebb657f2ba7cc08e8ef2752d4d4d7682c36a545c45fd5c00f06b7ff`.
The complete Claude session JSONL is retained locally: 147,593,603 bytes, SHA256
`3ca4c3c7eb7fd6bda0525d2526e079fea74563b533394a5747b639f7ce1f3881`.
The solution SHA256 is
`bf59c55aeacddf32e3da0d29ebb0672ef4d91ff6e58fcf11bae2f62c826e37ba`.
All 315 measured calls are Bash or Read. No URL, network, search, answer-key,
verifier, or credential marker occurred in tool-call parameters.

## Anti-shortcut ablations

The required degraded-input runs used Codex CLI 0.146.0 with `gpt-5.6-sol` at
xhigh. Each run received the task text and only the stated media, with no internet
or access to the full video. Answers and raw JSONL trajectories are retained under
`calibration/ablations/`; measured rewards are reported below.

| Condition | Media available | Sampling tools | Score |
|---|---|---|---:|
| No media | none | none | `0.000000` |
| Single frame | one frame at 1100 s | none | `0.000000` |
| Frame dump | 120 uniform frames at 22 s intervals | none | `0.000423` |

The frame-dump answer contained 44 events. Two matched event identity and time;
none matched complete post-event state.
