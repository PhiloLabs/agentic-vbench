# Qualifying Checkpointed Antigravity Rollout Summary

- Run id: `antigravity-qualifying-chess-20260719T170155Z`.
- Agent: Antigravity CLI `1.1.1`, Gemini 3.5 Flash (Medium).
- Conversation id: `97657c01-a3dc-4f09-ae9a-986420e52509`.
- Workspace: fresh replacement-source workspace under `calibration_runs_v5`;
  no ground truth or prior rollout artifacts were present.
- Prompt: canonical benchmark instruction with only `/workspace` rewritten to
  the fresh local path.
- Processed video SHA256:
  `b9839b0e67c02ffa4ae9a7662809b25a045f6feff9749844bb66eb19d6a99420`.
- Runtime: 6 minutes 36 seconds from the initial request through the last
  archived transcript record.
- Reward: `0.0` (`0/287` checks passed).
- Prediction: 0 of 104 expected plies, 0 of 26 expected capture events, and
  result `unknown` instead of `black_win`.
- Rollout length: 54 tool invocations and 51 conservative `DONE` tool-result
  records. The strict checker passes the `>50` gate using 51, while the 75-call
  hard cap was not approached.
- Other agents: Codex and Claude were not run in this rollout.

## Checkpoint And Stop

The canonical initial prompt contained no minimum turn count, pacing hint, or
checkpoint instruction. The external wrapper interrupted after call 46 because
no `output/solution.json` existed, then resumed the same conversation with the
content-free persistence request in `checkpoint-message.txt`.

Antigravity wrote an empty but schema-valid checkpoint on call 47, parsed it on
call 48, and continued analyzing the supplied video. Once the transcript had
naturally exceeded 50 calls, the wrapper scored the latest valid checkpoint at
call 53. Its reward was `0.0`, below `0.5`, so the wrapper immediately stopped
the run. One already-issued task-status call appears in the final transcript,
bringing the archived total to 54.

This is qualifying cross-agent evidence under the user-approved checkpointed
protocol. Because the wrapper sent one persistence message, it is not a
natural-prompt rollout; the natural Codex run remains the primary acceptance
calibration.

## Isolation Audit

Antigravity ran in terminal sandbox mode with a clean Python 3.12.7 environment
without pip or third-party Python packages. Temporary permission settings and a
pre-tool hook denied online tools, package/network commands, sandbox bypass,
and outside-workspace file or command paths.

The hook recorded 53 allowed calls and one denied availability probe that named
`pip3` and `conda`. No package installation or network request ran. Transcript
audit found no web, URL, browser, or MCP tools; no successful outside-workspace
file access; no host Python-library access; and no ground-truth or prior-rollout
access. See `environment-audit.md` and `hook-audit.jsonl` for the retained
evidence.

The full trajectory, checkpoint policy and message, response streams, submitted
JSON, score, guard configuration, environment audit, and turn counts are
archived beside this summary.
