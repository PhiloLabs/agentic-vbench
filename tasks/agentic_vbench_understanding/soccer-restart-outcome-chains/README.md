# soccer-restart-outcome-chains

An `agentic_vbench_understanding` task, built to the Harbor task layout. Over one full
90-minute soccer broadcast (Bundesliga 2016-17, Mainz 05 1 - 1 Borussia Dortmund), for
**every visible ball restart**, recover `(t, restart_type, team, outcome)`. It is
reasoning, not detection: each entry needs team attribution (kit colors held consistent
across the match) and following the ensuing 15-30 s of play to judge the outcome.

Task Proposal issue: PhiloLabs/agentic-vbench #50.

## Layout

```
soccer-restart-outcome-chains/
  SPEC.md                         filled-in Spec Card (every claim, with measured numbers)
  task.toml                       settings, resources, time limits
  environment/Dockerfile          bakes the media at build time (see the media open question)
  steps/solve/
    instruction.md                the agent prompt + output schema + deliverable path
    workdir/setup.sh              stages the baked video into /workspace/materials
    solution/solve.sh             the oracle (writes the verified timeline)
    tests/judge.py                deterministic grounded 4-tuple F1 scorer -> reward.json
    tests/test.sh                 verifier entry point
  calibration/
    scores.md                     per-agent score + rollout-turn table
    rollouts/<agent>/             one folder per agent: rollout.json + requests.txt
  provenance/                     how the ground truth is built (not part of the run)
    build_gt.py                   SoccerNet-v2 Labels-v2.json -> the GT, mechanically
    mainz_dortmund.labels-derived.json   the 81-restart GT (mirrors judge.py's GROUND_TRUTH)
    data_setup/                   label + video download helpers
    ablations/                    shortcut ablations on the official metric
```

## Clears the bar (measured)

| check | result |
|---|---|
| oracle | 1.0 |
| empty / null | 0.0 |
| no-media prior | 0.0247 |
| Claude Code (Opus 4.8) | 0.0225 over 110 turns |
| Codex | 0.0227 over 120 turns |
| Antigravity | 0.0449 over 120 turns |

All three strong agents < 0.10 over > 50 tool-call turns. See `SPEC.md` and
`calibration/scores.md`.

## Scoring rule (one coherent rule)

**Grounded order-preserving 4-tuple F1.** A predicted `(t, restart_type, team, outcome)`
is a true positive iff `restart_type ==` AND `team ==` AND `outcome ==` AND
`|dt| <= 3 s`, one-to-one under an order-preserving alignment; `official_score = F1`.
Pure Python stdlib, no VLM or LLM judge. Ground truth is hardcoded in `judge.py` and
mirrors the mechanical build in `provenance/build_gt.py`.

## Ground-truth provenance (fully mechanical)

Every field is a deterministic transform of SoccerNet-v2's published, multi-annotator
`Labels-v2.json` (free, no NDA):
- `t` / `restart_type` / `team` = the restart event's `position` / `label` / `team`
- `outcome` = scan the log: `2` if a Goal in `[t, t+30]`, else `1` if a Shot in
  `[t, t+15]`, else `0`
- only `visibility == "visible"`; `team == "not applicable"` dropped; tie-break `(t, label)`

`provenance/build_gt.py` asserts `verifier(oracle) == 1.0`, so provenance is
demonstrated, not asserted.

## One open item

The **video source** is the single unresolved design decision, raised in the PR
description: SoccerNet distributes the broadcast under an NDA (no public redistribution;
224p/720p, not a pinnable public URL), while the labels are free. `environment/Dockerfile`
carries a placeholder URL pending the maintainer's guidance on re-hosting an anonymized
>= 720p derivative on a public HF dataset (the pattern the egocentric tasks #45 / #47
use for gated footage). Everything else runs today against a locally staged copy.
