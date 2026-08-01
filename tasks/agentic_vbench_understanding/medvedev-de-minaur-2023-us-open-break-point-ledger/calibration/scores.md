# Calibration - medvedev-de-minaur-2023-us-open-break-point-ledger

## Current hardened task

| harness | harness version | model | reasoning | score | tool-call turns | trajectory |
|---|---|---|---|---:|---:|---|
| Oracle | local | bundled solution | n/a | 1.0 | n/a | n/a |
| Empty baseline | local | n/a | n/a | 0.0 | n/a | n/a |
| Codex CLI | 0.144.4 | GPT-5.6 Sol | high | 0.0 | 87 | `rollouts/codex-gpt-5.6-sol-v1.jsonl` |
| Claude Code | 2.1.220 | Claude Opus 4.8 (`claude-opus-4-8[1m]`, Vertex) | high | 0.0 | 411 | `rollouts/claude-opus-4.8-hardened-v1.jsonl` |
| Gemini CLI (Antigravity fallback) | 0.51.0 | Gemini 3.5 Flash (`gemini-3.5-flash`) | default | 0.0 | 91 | `rollouts/gemini-cli-3.5-flash-hardened-v1.jsonl` |
| Gemini CLI (Antigravity fallback) | 0.51.0 | Gemini 3.1 Pro Preview (`gemini-3.1-pro-preview`) | default | 0.0 | 56 | `rollouts/gemini-cli-3.1-pro-preview-hardened-v1.jsonl` |

The formal GPT-5.6 Sol run used the Azure `responses` provider, fast service tier,
disabled web search, and only the local match video. It reconstructed all 16 base
event identities but fully matched no event after the serve, rally, and terminal
fields were included.

| Codex field | correct |
|---|---:|
| Base event identity | 16/16 |
| First serve in | 11/16 |
| Serve direction | 6/16 |
| Rally shots | 3/16 |
| Terminal player | 12/16 |
| Terminal stroke | 6/16 |
| Terminal court position | 12/16 |
| Terminal result | 7/16 |
| Terminal error | 10/16 |
| All scored fields | 0/16 |

The formal Opus 4.8 run used only the isolated local match video. Its five
contiguous segments made 411 tool calls, used no web search or web fetch, and cost
$23.27. It reconstructed all 16 score-level events but fully matched none.

| Opus 4.8 field | correct |
|---|---:|
| Score-level event identity | 16/16 |
| First serve in | 11/16 |
| Serve direction | 1/16 |
| Rally shots | 2/16 |
| Terminal player | 8/16 |
| Terminal stroke | 3/16 |
| Terminal court position | 10/16 |
| Terminal result | 4/16 |
| Terminal error | 0/16 |
| All scored fields | 0/16 |

Native Antigravity `agy` was not available. The Gemini models were therefore run
through Gemini CLI at Meta 0.51.0 under a policy that denied web and MCP tools,
package installation, Swift/Vision, and paths outside the calibration directory.
`PYTHONNOUSERSITE=1` kept user-installed Python packages out of the runs.

The exact `gemini-3.1-pro` identifier returned HTTP 404; the available identifier
was `gemini-3.1-pro-preview`. Gemini 3.5 Flash predicted 16 events and matched no
score-level identity. Gemini 3.1 Pro Preview predicted seven events, matched three
score-level identities, and fully matched no events. These are fallback model
calibrations, not native Antigravity certification.

Claude Code resolved the requested Fable alias to `claude-fable-5`, but the provider
returned HTTP 403 before inference. The failed launch is retained at
`rollouts/claude-fable-5-access-blocked.jsonl` as an access result, not a score.

All completed model runs clear both measured gates: reward is below `0.10`, and
each trajectory required more than 50 tool calls.
