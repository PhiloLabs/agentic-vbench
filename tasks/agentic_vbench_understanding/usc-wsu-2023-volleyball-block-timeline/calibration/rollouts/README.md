# Rollouts

Artifacts from every calibration run of the block-only task. Scores and context are
in `../scores.md`.

## Fresh runs on the final block-only instruction

| file prefix | agent | score |
|---|---|---|
| `codex-fresh.*` | Codex CLI, gpt-5.6-sol, xhigh | 0.0185 |
| `opus-fresh.*` | Claude Code, Opus 5, xhigh | 0.0 |

Each carries the answer the agent wrote (`*.solution.json`), the run's provenance
(`*.run-metadata.txt`: CLI version, model, effort, instruction hash, media hash,
judge commit) and a tool-call histogram. Both runs ended normally and wrote their own
answer file; neither referenced an answer key or the web.

`opus-fresh.final-report.md` is the agent's own closing account, verbatim. It is
worth reading: Opus rebuilt the full 200-rally timeline from the score bug and then
reported honestly that it could confirm only one block point, and that even that
blocker credit was inferred rather than read. That is the difficulty of this task
described from the inside.

## Interrupted

`fable-run.*` — Claude Code, Fable 5, xhigh: 210 tool-call turns of genuine frame
work, then the account's credit pool for that model ran out before an answer was
written. Archived as evidence of effort, deliberately unscored.

## Superseded

`codex-aceblock-run.solution.json` — the answer from the earlier ace+block version of
this task, kept because `../scores.md` cites its re-grade in the design note.

Raw stream logs run to hundreds of MB and are not committed; the histograms and
answer files here, plus the metadata, are what a reviewer needs to check a score.
