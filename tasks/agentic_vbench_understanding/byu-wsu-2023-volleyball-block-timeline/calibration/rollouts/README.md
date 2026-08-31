# Rollouts

Artifacts from the scored calibration runs. Scores and context are in `../scores.md`.

| file prefix | agent | score |
|---|---|---|
| `codex-fresh.*` | Codex CLI, gpt-5.6-sol, xhigh | 0.0213 |
| `opus-fresh.*` | Claude Code, Opus 5, xhigh | 0.0 |

`instruction-as-run.md` is the prompt both agents opened with; each `run-metadata.txt`
records it by SHA256 along with the model, effort and media hash. Each run also carries
the answer the agent wrote (`*.solution.json`) and a tool-call histogram. Both agents
wrote their own answer file, and neither referenced an answer key or the web.

**One caveat on the Opus run, which `instruction-as-run.md` alone does not show.** That
run is two legs of one session: 140 tool-call turns, a network drop, then 246 more on
resume. The resume was driven by a continuation prompt, and that prompt restated the
required schema **wrongly** — it carried the sister USC task's score label
(`"score_after":"USC-WSU"`) and omitted `setter` from the schema entirely:

> …write your COMPLETE final answer to ./output/solution.json in exactly the required
> schema: {"events":[{"set":N,"score_after":"USC-WSU","type":"block",
> "players":["First Last"],"blocked":"First Last"}, ...]}

So for 246 of its 386 turns — most of the run — Opus was being told to produce a
two-attribution answer with the wrong team-order label. Its 0.0 is therefore not a
clean measurement of this task's three-attribution schema, and the parity table marks
that row provisional for this reason as well as the harness one. The Codex run has no
resume leg and is unaffected.

The two histograms count different things because the CLIs do: the Codex figure is
completed tool-call items in its rollout, the Claude figure is assistant turns
carrying at least one tool call. Each file says which.

The raw streams themselves run to hundreds of MB, so they are published at an
immutable dataset revision rather than committed here; `../scores.md` lists every URL
with its SHA256.
