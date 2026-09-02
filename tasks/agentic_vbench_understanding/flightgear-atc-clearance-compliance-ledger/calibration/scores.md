# Calibration — FlightGear ATC clearance compliance ledger

Every number here is produced by:

```bash
python3 calibration/rescore_ledgers.py
```

which rescores each agent's own submitted ledger with the shipped judge. No
rollout is replayed, no model is called, and nothing is downloaded.

## The metric

Reward is graded per-clearance credit, discounted by what a transcript alone
could have said about that clearance. A matched pair earns up to 20 units across
six groups; the per-clearance transcript ceiling is subtracted, the signed gain
is clipped to [-1, 1], clearances the transcript already answers in full leave
the denominator, and unmatched submissions are charged as padding.
`RUNBOOK.md` has the full statement.

On this release the ceiling is **953 of 1300 units**, leaving **60 of 65**
clearances gradable. The transcript-only anchor scores **0.0000**.

This replaces `0.9 * exact_leg_accuracy + 0.1 * clearance_chain_f1`, under which
`exact_leg_accuracy` was oracle-only and the audio-only ablation (0.0031) beat
every run that included video.

## Required agent calibration

| harness | version | model | reasoning | reward | tool-call turns | trajectory |
|---|---|---|---|---:|---:|---|
| Codex CLI | 0.147.0 | GPT-5.6 Sol | high | 0.0938 | 88 | `rollouts/codex-gpt-5.6-sol.jsonl` |
| Claude Code (native `claude -p`) | 2.1.226 | Claude Opus 4.8 | high | 0.0000 | 147 | `rollouts/claude-opus-4.8-native.jsonl` |
| Antigravity CLI | 1.1.12 | Gemini 3.6 Flash High | high | 0.0000 | 89 | `rollouts/antigravity-gemini-3.6-flash-high.jsonl` |

All three rows are under `AGENT_MAX = 0.10`.

The native Claude row scores 0.0000 for a schema reason and a substantive one,
and both are worth stating. It wrote `/workspace/output/solution.json` as a bare
JSON array of 65 objects rather than `{"clearances": [...]}`, which the judge
rejects outright. Wrapping it by hand — a diagnostic, *not* this row's score —
still gives 0.0000, with 8 of 260 instrument-snapshot units. It misheard the
first target ("two niner three" → 93), and its altitude readings run about
1000 ft off. This is a weak run, not a harness malfunction: `claude` exited 0
after 147 tool calls.

Instruction versions and per-row harness deviations are recorded in
`rollouts/README.md`. They are not uniform, and the differences are disclosed
there rather than smoothed over.

## Where the credit actually comes from

Group credit per row, earned/available. The `states` column is the one that
requires reading an instrument; everything else is available in some degree from
the spoken audio.

| run | target | status | states | timing | chain | progress |
|---|---:|---:|---:|---:|---:|---:|
| codex GPT-5.6 Sol | 260/260 | 208/260 | 62/260 | 187/260 | 106/130 | 124/130 |
| claude Opus 4.8 native | 252/260 | 184/260 | 8/260 | 150/260 | 64/130 | 0/130 |
| antigravity Gemini 3.6 | 252/260 | 196/260 | 14/260 | 111/260 | 106/130 | 46/130 |
| audio-only ablation | 252/260 | 196/260 | 86/260 | 78/260 | 106/130 | 54/130 |
| claude Opus 4.8 (replaced agent-host round) | 252/260 | 248/260 | 242/260 | 182/260 | 120/130 | 128/130 |

Three things worth reading off this table. The spoken-target column is nearly
saturated for everyone, which is why the old metric could be won without video.
The audio-only ablation earns *more* raw state units (86) than the Codex row
(62) while scoring 0.0000 against Codex's 0.0938 — because its snapshots are
exactly the values the transcript predicts, so they clear no headroom. That is
the discount doing its job.

The third is the uncomfortable one. The only run that genuinely read the
instruments is the round this PR *removes* for harness parity: 242/260 state
units, against 8, 14, and 62 for the three native rows. That round had a VS Code
Copilot wrapper prompt telling it to validate vocabularies and check that all
chronological clearances were represented. So this table shows the task is
solvable — 242/260 is not luck — while none of the three compliant harness rows
demonstrate it. See the open issues below.

## Anchors and anti-shortcut runs

| run | reward | submitted | matched | tool calls |
|---|---:|---:|---:|---:|
| oracle | 1.0000 | 65 | 65 | — |
| empty/null | 0.0000 | 0 | 0 | — |
| transcript-only anchor (constructed upper bound) | 0.0000 | 65 | 65 | — |
| no media | 0.0000 | 0 | 0 | 9 |
| one frame | 0.0000 | 0 | 0 | 9 |
| video only | 0.0000 | 56 | 37 | 65 |
| audio only | 0.0000 | 65 | 63 | 28 |
| frame dump + transcript, no media tools | 0.0000 | 65 | 63 | 1 |

Adversarial probing beyond the required ablations is a committed script rather
than a claim:

```bash
python3 calibration/shortcut_probe.py       # ~3 min, exits non-zero if any probe clears 0.10
```

It runs **29,100** video-free probes against the shipped judge — 12 structural
(all-null optional fields, padding to the 2000-entry acceptance limit,
truncation to 1/3/5/10/20/40, duplicating the highest-ceiling clearance 65×,
keeping only the zero-headroom clearances), a 27,648-point systematic-offset
grid over altitude/heading/airspeed/time/progress/status applied to the
transcript-only reference ledger, and 1,440 randomized jitter ledgers (12
magnitudes × 120 seeds). **Every one returns 0.0000.** The only figure above
zero requires ground truth to construct and is not realizable by an agent.

## Open issues, stated rather than resolved

**The difficulty gate passes, but read why before trusting it.**
`scripts/understanding/check_task.py` executes `AGENT_MAX = 0.10`. All three
required rows are under it: 0.0938, 0.0000, 0.0000. Oracle is 1.0000, the null
submission is 0.0000, and every ablation is 0.0000, so every measured gate in
that script is satisfied.

The honest caveat is that the gate passes partly because the strongest reader
was removed. The replaced agent-host round scores **0.6060** on the same judge —
6× the gate — and it is retained in the release so the number is checkable. Its
advantage was 242/260 state units. If a future native run reads gauges that well
without a wrapper prompt, this task will exceed `AGENT_MAX` and should be
re-examined rather than re-tuned; nothing here was widened or narrowed to move a
row across a threshold. Codex moved from 0.1506 under an earlier draft of this
scorer to 0.0938 now, and that came from graded timing and interpolated
snapshots, not from a tolerance change.

Note also that `check_task.py`'s module docstring says "strong agent reward <
0.50" while the constant it executes is `0.10`. Both readings pass for the three
required rows and both fail for the replaced round, so nothing here turns on it
— but it is worth settling.

**Is the task now too hard?** This is the mirror of the maintainer's original
concern and it deserves a direct answer. Three native rows at ~0 could mean an
unreadable metric. The evidence that it does not: the agent-host round reached
242/260 state units on the same media and the same judge, and the observability
audit finds 62 of 65 events readable within the shipped 100/8/3 band. So the
signal is there to be read. What the native rows show is that current harnesses
do not reliably read it unprompted — which is a statement about difficulty, not
about feasibility. Whether that is the right difficulty for this benchmark is a
maintainer call.

**A residual pruning incentive.** Because a below-ceiling clearance subtracts, an
agent that could identify its own weak readings could raise its score by
withholding them. `rescore_ledgers.py` reports the size of that gap per row in
its `pruned` column: Codex 0.0938 → 0.3291 over 45 retained entries, and the
replaced Claude round 0.6060 → 0.6594 over 60. The shipped `instruction.md` does
not describe the scoring method, so this is not something an agent is told; it
remains a property of the metric and is disclosed rather than fixed.

**Instruction parity is still incomplete.** The Claude row was re-run natively on
the shipped `instruction.md`, which is what the maintainer asked for. Codex and
Antigravity could not be re-run in this environment — Codex has no credentials
available, and the Antigravity harness's own sandbox could not be verified to
block egress, so re-running it would have published a row with a weaker network
posture than the one it replaces. Both therefore still reflect an earlier
`instruction.md` with tighter stated tolerances. The deviation runs against them:
they were told to hit a band four times tighter than the one they are scored
against, so 0.0938 and 0.0000 may understate those harnesses.
`rollouts/README.md` gives the exact hashes and the full reason per row.
