# End-to-end rollout artifacts

`codex-gpt-5.6-sol-high.jsonl` is the raw Codex session event stream from the measured
Harbor run. It retains all model messages, tool calls, tool outputs, errors, and final
metrics. To keep the repository reviewable, base64 image bodies and encrypted
reasoning blobs are replaced in place by placeholders containing their original
length and SHA256. No textual tool result or visible model response is summarized.

`codex-gpt-5.6-sol-high.solution.json` is the exact file graded by the verifier.

`claude-code-opus-4.8-xhigh.jsonl` and its adjacent solution are the corresponding
artifacts from the successful Claude Code 2.1.220 calibration. The run used
`claude-opus-4-8` at `xhigh`, passed the completion gate, and received `0.0`.

`antigravity-gemini-3.5-flash-high.jsonl` is the byte-for-byte native Antigravity CLI
1.1.8 transcript from the successful Harbor run. It contains no embedded binary or
credential fields, so no elision was needed. The adjacent solution is the exact
48-entry root array graded by the verifier. The schema is invalid, but wrapping that
unchanged array under `checkpoints` still produces zero complete-state matches; see
`../scores.md` for the diagnostic counts.

Two Claude Code 2.1.217 attempts were invalid calibration evidence: the first stopped
seven background subagents before completion, and the second exhausted the
subscription session limit at `xhigh`. Neither created `solution.json`; do not commit
or report either missing-output attempt as a model score.

Use `docs/UNDERSTANDING_CALIBRATION.md` for fresh-computer setup and the exact
IndustReal commands. Retain artifacts as:

- `claude-code-opus-4.8-xhigh.jsonl`
- `claude-code-opus-4.8-xhigh.solution.json`
- `antigravity-gemini-3.5-flash-high.jsonl`
- `antigravity-gemini-3.5-flash-high.solution.json`

Use Harbor's harness-native `steps/solve/agent/claude-code.txt` or
`steps/solve/agent/antigravity-cli.trajectory.jsonl` as the raw trajectory source.
With Harbor 0.20, use `steps/solve/artifacts/logs/artifacts/solution.json` as the
submitted solution; older saved jobs may use `steps/solve/artifacts/solution.json`.
The normalized ATIF `trajectory.json` is useful for counting calls when Harbor emits
it, but does not replace the native transcript. For the Antigravity CLI 1.1.8 format,
count tool-action event types in the native JSONL because Harbor 0.20 does not emit a
normalized copy. Do not copy the whole `jobs/` directory into the task.
