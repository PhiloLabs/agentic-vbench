# Calibration rollouts

`codex.jsonl` is the raw Codex CLI log from the clean exact-prompt Harbor run
reported in `../scores.md`. The run used GPT-5.6 Sol with high reasoning and made
195 tool calls. `codex.solution.json` is its submitted answer. Harbor's generated
ATIF copy is intentionally not duplicated here.

`codex-no-media.jsonl` is the raw GPT-5.6 Sol high-reasoning ablation from
2026-07-24. It made six tool calls, found no supplied media anywhere in the
container, and abstained. Harbor's verifier completed normally at reward `0.0000`.

`claude-code-opus-4.8-xhigh.jsonl` is the sanitized native Claude Code 2.1.219
stream from the clean exact-prompt run on 2026-07-24. It retains all 5,926 stream
events, visible model messages, tool invocations, textual tool results, retry
events, and final output. Base64 media and encrypted reasoning blobs are replaced
with length-and-SHA256 placeholders, reducing the trajectory from 215 MB raw to
3.48 MB without removing auditable model behavior.

The original native stream SHA256 is
`7cca32d2dd461c8ef59b55aead2a5ca70eb9c7acfb88381f954813ae4d6525fe`;
the sanitized JSONL SHA256 is
`955b4fd848a66ea255bd16d0303a4c21827b80d6963f55ee2eaa7c45d07864f2`.
`claude-code-opus-4.8-xhigh.solution.json` is byte-identical to the submitted
answer, and `claude-code-opus-4.8-xhigh.verifier-details.json` is the deterministic
diagnostic report behind the `0.0256` reward.

`antigravity-gemini-3.5-flash-high.jsonl` is the unmodified native Antigravity
CLI 1.1.8 transcript from the clean exact-prompt run on 2026-07-28. It retains
all 311 events, including 137 model tool calls and two native context checkpoints.
The run completed without a Harbor exception and scored `0.0000`.
`antigravity-gemini-3.5-flash-high.solution.json` is byte-identical to the
submitted answer, and `antigravity-gemini-3.5-flash-high.verifier-details.json`
contains the deterministic diagnostics.

The raw trajectory SHA256 is
`4c6a5a663c18228bc0460587a2f4fad08874df41dd0ed63b7c78604a91fe833d`;
the solution SHA256 is
`e337adac8a09acac127621fada55b8d4ea8b3105c7b4f1b8540ae8839ca3e78f`;
the verifier-details SHA256 is
`8fb298104da4d230b47b782cc727728d1cc9e9894807172af21ade855284d1be`.

The predecessor death-map trajectory is not retained because its ground truth used
an incorrect coordinate transform.

Use `docs/UNDERSTANDING_CALIBRATION.md` for fresh-computer setup and the exact local
Docker commands. Retain new harness-native artifacts as:

- `claude-code-opus-4.8-xhigh.jsonl` from
  `steps/solve/agent/claude-code.txt`, with binary-equivalent payloads replaced by
  length-and-SHA256 placeholders
- `claude-code-opus-4.8-xhigh.solution.json`
- `antigravity-gemini-3.5-flash-high.jsonl` from
  `steps/solve/agent/antigravity-cli.trajectory.jsonl`
- `antigravity-gemini-3.5-flash-high.solution.json`
- `antigravity-gemini-3.5-flash-high.verifier-details.json`

Use the `solution.json` retained recursively under `steps/solve/artifacts/` as the
submitted solution. Harbor's normalized ATIF `trajectory.json`, when emitted, is
useful for counting calls but does not replace the harness-native raw transcript.
Do not copy the whole `jobs/` directory into the task.
