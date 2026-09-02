# Rollouts

Artifacts from every calibration run. Scores and context are in `../scores.md`.

## Scored

| file prefix | agent | score |
|---|---|---|
| `codex-fresh.*` | Codex CLI, gpt-5.6-sol, xhigh | 0.0185 |
| `opus-fresh.*` | Claude Code, Opus 5, xhigh | 0.0 |

Each carries the answer the agent wrote (`*.solution.json`), the run's provenance
(`*.run-metadata.txt`: CLI version, model, effort, instruction hash, media hash,
judge commit) and a tool-call histogram. Both runs ended normally and wrote their own
answer file; neither referenced an answer key or the web.

The histograms count different things because the CLIs do: the Codex figure is
completed tool-call items in its rollout, the Claude figures are assistant turns
carrying at least one tool call. Each file says which.

`opus-fresh.final-report.md` is the agent's own closing account, verbatim. It is
worth reading: Opus rebuilt the full 200-rally timeline from the score bug and then
reported honestly that it could confirm only one block point, and that even that
blocker credit was inferred rather than read. That is the difficulty of this task
described from the inside.

## Interrupted

`fable-run.*` — Claude Code, Fable 5, xhigh: 210 tool-call turns of genuine frame
work, then the account's credit pool for that model ran out before an answer was
written. Archived as evidence of effort and deliberately unscored;
`fable-run.solution.json` is the partial event list recoverable from its transcript at
the point it stopped, not something the agent submitted.

`hybrid-fable-then-opus.*` — resuming that interrupted session with a different model,
which scored 0.0 and matched no rally at all. The write-up explains why the archived
run stays unscored rather than being completed under a name that did not produce it.

The raw streams themselves run to hundreds of MB, so they are published at an
immutable dataset revision rather than committed here; `../scores.md` lists every URL
with its SHA256.
