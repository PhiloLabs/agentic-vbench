# Calibration — egocentric-activity-understanding

Deterministic scorer (`steps/solve/tests/judge.py`): order-insensitive,
maximum-cardinality one-to-one 4-field F1. A true positive requires the exact verb,
the exact noun set, and both frame boundaries within the fixed ±12-frame window.

A task clears the family bar when the oracle scores 1.0, an empty submission scores
≤ 0.10, every real agent scores below 0.10, each ablation scores ≤ 0.15, and a real
attempt takes more than 50 tool-call turns.

## Measured anchors

| run | score | note |
|---|---:|---|
| oracle (exact 172-action ledger) | 1.000000 | asserted by `build_ground_truth.py` |
| empty submission (`{"actions": []}`) | 0.000000 | |
| random guess over the vocabulary (mean of 20 seeds, 172 entries) | 0.000000 | |
| no-media prior (best fixed guess, prompt + vocabulary only) | 0.005814 | most frequent class, evenly spaced, swept 100–300 entries |

Scorer behaviour spot-checks:

| probe | score | what it shows |
|---|---:|---|
| oracle with each `nouns` list reversed | 1.000000 | noun order is ignored |
| oracle with the equal-start rows swapped | 1.000000 | equal-time matching is order-insensitive |
| oracle timings, every verb+nouns replaced | 0.000000 | localization alone earns nothing |
| oracle labels, every entry duplicated | 0.666667 | padding is punished through precision |
| 20 exact actions only | 0.208333 | partial credit is smooth |
| the same 20 exact actions padded to 172 with guesses | 0.116279 | guessing to fill the list lowers the score |

## Agent calibration

| harness | harness version | model | reasoning | score | tool-call turns | trajectory |
|---|---|---|---|---:|---:|---|
| Codex CLI | 0.153.3 | gpt-5.6-sol | high | 0.000000 | 76 | `rollouts/codex-gpt-5.6-sol.jsonl` |
| Claude Code CLI | 2.1.246 | claude-opus-4-8 | high | 0.033613 (salvaged, run cut short) | 302 | `rollouts/claude-opus-4.8.jsonl.gz.part-*` |

### Codex CLI (GPT-5.6 Sol, high) — 0.000000

Fresh run from the `skillbench` conda environment through Harbor 0.22.0, with a
force-built Docker image and explicit `reasoning_effort=high` (job
`egocentric-gpt-5-6-sol-high-clean-20260904-r1`, task checksum
`08e7e8747d2a892b24dfdb1f5c1ad39077a90114ea355fae2a7519082592eff9`). Total job
wall time was 24m 4s, including 2m 56s of agent setup; agent execution was 19m 52s.
The 82-step Harbor ATIF trajectory contains 76 tool calls (75 `exec`, one `wait`) and
is stored as JSONL with session metadata and final metrics, apart from deterministic
personal-path redaction.

| | |
|---|---:|
| submitted ledger entries | 146 |
| official predicted actions | 0 |
| official true positives | 0 |
| official F1 | 0.000000 |
| diagnostic F1 after mechanically wrapping the bare array | 0.088050 |
| diagnostic true positives after wrapping | 14 |
| diagnostic `verb_and_boundary_matches` after wrapping | 28 |
| diagnostic `boundary_only_matches` after wrapping | 34 |

The agent built whole-video overview sheets, a four-frame-per-second proxy, 67 dense
event sheets, and exact-frame stove-control crops. It produced 146 chronological,
schema-valid action entries, but wrote the entries as a bare JSON array instead of the
required top-level `{"actions": [...]}` object. The deterministic verifier therefore
correctly rejected the submission shape and awarded 0.0. The wrapped diagnostic above
does not alter the official score or saved solution; it only shows what the ledger
would have scored if the top-level object had been present.

### Claude Code CLI (Opus 4.8, high) — 0.033613, terminated by provider rate limit

Run through Harbor 0.22.0 with the Docker executor, this task's own
`environment/Dockerfile`, and `--ak reasoning_effort=high`. The agent cap was
`--agent-timeout-multiplier 0.25` against `task.toml`'s `timeout_sec = 10800`, i.e. 45
minutes, matching the Codex row.

The run never reached its own time cap. Both attempts were cut off mid-analysis by the
subscription's five-hour rate window, which the CLI reports in its own
`rate_limit_event` records:

| attempt | job | wall time | ended at | terminal utilization |
|---|---|---:|---|---:|
| initial | `egocentric-claude-opus-4.8-high-rerun` | 42m 35s | `ApiRateLimitError` | 1.02 (`rejected`) |
| resumed | `egocentric-claude-opus-4.8-high-resume3` | 32m 42s | `ApiRateLimitError` | 1.01 (`rejected`) |

The resumed attempt restored the initial attempt's conversation via
`--load-trajectory` / `claude --resume`, so the two segments are one continuous agent
transcript. The split gzip `rollouts/claude-opus-4.8.jsonl.gz.part-*` reconstructs the
concatenated JSONL, delimited by `harbor_rollout_marker` records. Across both segments
the agent made 302 tool calls
(193 `Read`, 92 `Bash`, 15 `Agent` subagent spawns, two `Write`) in 533 assistant turns.

`/workspace/output/solution.json` was never written — the cutoff landed before the
agent's submission step in both attempts, so Harbor's own `reward.json` records
`reward = 0.0` with `predicted_actions = 0` for each. The score above is instead
**salvaged**: the agent's incremental append-only ledger `work/ledger.jsonl` was
captured from the live container at the 99%-utilization checkpoint, mechanically
wrapped in the submission shape, and scored offline with the shipped
`steps/solve/tests/judge.py`. Nothing in the ledger was edited.

| | |
|---|---:|
| predicted actions | 66 (all valid) |
| true positives | 4 |
| false positives | 62 |
| false negatives | 168 |
| precision | 0.060606 |
| recall | 0.023256 |
| `verb_and_boundary_matches` | 7 |
| `boundary_only_matches` | 10 |

The ledger spans frames 978–11766, roughly the first 46% of the 25692-frame video, so
recall is bounded by coverage as much as by accuracy. The initial attempt used a
15-subagent map-reduce over video regions and was killed before any subagent emitted
its segment file; the resumed attempt abandoned that design for a solo, strictly
append-after-each-region ledger, which is the only reason a partial result survived.

Read this number as a floor, not as a clean 45-minute trial comparable to the Codex
row: it reflects an incomplete pass over the video and a resumed run whose container
(and therefore whose intermediate contact sheets and annotation guide) did not survive
the restart. It is below the `< 0.10` family target, but a completed run is still
needed before this row can be treated as final.

## Anti-shortcut runs

| degraded input | score | outcome |
|---|---:|---|
| no media (prompt + vocabulary only) | 0.005814 | measured |
| single frame | 0.000000 | measured |
| video only | n/a | the source has no audio track |
| audio only | n/a | the source has no audio track |

## Why the task is hard

The published annotation contains 172 actions with a median length of 35 frames; 37
are under a second long. An agent must find every action across 25692 frames. `take` and
`put`, plus `open` and `close`, are visually similar motions in opposite directions,
and nine of the 35 task nouns are visually similar `*_container` packages. A prediction
must get the verb, complete noun set, and both boundaries right to score.
