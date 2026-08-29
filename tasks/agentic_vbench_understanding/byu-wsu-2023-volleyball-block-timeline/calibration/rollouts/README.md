# Rollouts

Artifacts from the scored calibration runs. Scores and context are in `../scores.md`.

| file prefix | agent | score |
|---|---|---|
| `codex-fresh.*` | Codex CLI, gpt-5.6-sol, xhigh | 0.0213 |
| `opus-fresh.*` | Claude Code, Opus 5, xhigh | 0.0 |

`instruction-as-run.md` is the exact prompt both agents were given; each
`run-metadata.txt` records it by SHA256 along with the model, effort and media hash.
Each run also carries the answer the agent wrote (`*.solution.json`) and a tool-call
histogram. Both agents wrote their own answer file, and neither referenced an answer
key or the web.

The two histograms count different things because the CLIs do: the Codex figure is
completed tool-call items in its rollout, the Claude figure is assistant turns
carrying at least one tool call. Each file says which.

The raw streams themselves run to hundreds of MB, so they are published at an
immutable dataset revision rather than committed here; `../scores.md` lists every URL
with its SHA256.
