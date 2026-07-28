---
title: Dota 2 Game 5 pre-death trajectory proposal
summary: Proposal, ground-truth provenance, scoring, and calibration for a long-horizon minimap-tracking task.
read_when: Reviewing the Dota 2 Game 5 pre-death trajectory task.
---

# Dota 2 Game 5 pre-death trajectories

## Motivation

Kill feeds and scoreboards make death identity easy to index, but they do not reveal
how a player moved into danger. This task tests whether an agent can bind a death to
the correct hero and recover that hero's spatial trajectory across multiple earlier
moments in a long broadcast.

## Task

The input is one continuous 52-minute, 720p segment of PGL Wallachia Season 7 Grand
Final Game 5. For every major-teamfight death from HUD `00:00` through `50:30`, the
agent reports the time, victim, credited killer, and the victim's minimap cells 10
seconds before, 5 seconds before, and at death on a 14-by-14 grid. A major teamfight
is a maximal sequence of at least three deaths with every consecutive gap below 15
seconds. The output is a chronological JSON event list. The prompt does not reveal
the number of deaths or prescribe an analysis procedure.

Example shape, not an answer:

```json
{
  "events": [{
    "game": 5,
    "clock": "12:34",
    "victim": "Nisha",
    "killer": "watson",
    "cell_10s_before": "E7",
    "cell_5s_before": "F7",
    "death_cell": "G8"
  }]
}
```

## Ground truth

The 39 events come from OpenDota's kill log for Valve replay `8730786393`. Positions
come from the same replay parsed with `gem-dota==0.5.0` every three ticks, or 0.1
seconds. The nearest sample to each requested replay tick is at most two ticks, or
0.067 seconds, away. `tools/extract_replay_positions.py` creates the pinned position
snapshot; `tools/build_ground_truth.py` maps official game coordinates with
`(coordinate - 64) / 127`, the transform used by OpenDota's minimap code. An exact
internal boundary belongs to the east or north cell; the checked-in tests cover
every internal and outer boundary.

The checked-in audit records replay hashes, parser version, sampling error, and an
independent comparison against OpenDota's 39 available teamfight death positions.
All 39 agree on the resulting 14-by-14 death cell. The answer contains 117 position
labels, and all 39 three-cell trajectories are distinct. The calibration bundle
also includes native 720p minimap crops and grid overlays for stacked early- and
late-game fights.

## Evaluation

The deterministic verifier performs one-to-one matching with a two-second HUD-clock
tolerance. Reward is exact-trajectory F1: all identity fields and all three cells
must be correct for an event to match. It also reports time, victim, killer,
individual-cell, and neighboring-trajectory F1 as diagnostics. Duplicates lower
precision and omissions lower recall.

This strict reward is deliberate because the clock, victim, and killer are public
in OpenDota. Correct public identity fields without the complete private three-cell
trajectory receive the same zero reward as the null baseline.

## Calibration

A fresh clean Harbor 0.20.0 run with GPT-5.6 Sol at high reasoning used 195 tool
calls and scored `0.0000` (oracle `1.0000`, null `0.0000`). Codex submitted 38
schema-valid events. Thirty-three matched a GT clock within two seconds with the
correct victim and killer, showing that it could read much of the HUD and kill
feed. Five corresponding events fell outside the time tolerance, one GT death was
omitted, and no three-point trajectory was fully exact.

Claude Code 2.1.219 with Claude Opus 4.8 at xhigh reasoning then scored `0.0256`
in a clean exact-prompt run. It submitted all 39 events and matched every clock,
victim, and killer, but only one complete trajectory. Its individual cell matches
were 1/39 at minus 10 seconds, 4/39 at minus 5 seconds, and 6/39 at death.

Antigravity CLI 1.1.8 with Gemini 3.5 Flash at high reasoning scored `0.0000`
in a clean exact-prompt run. It submitted 18 schema-valid events. Four matched a
GT clock within two seconds, but none matched the corresponding victim, killer,
or complete three-cell trajectory. The full 311-event native transcript records
137 model tool calls and is retained with the submitted answer and verifier
diagnostics.

Three measured GPT-5.6 Sol high anti-shortcut ablations also scored `0.0000`: no
media, one temporal-midpoint frame, and all 93,450 native frames pasted into
chronological contact sheets with every model tool disabled. The all-frames run
submitted 30 events but matched no victim, killer, or complete trajectory. This
separates access to the visual record from the agentic ability to seek, magnify,
cross-reference, and track small HUD entities over a long timeline.

These runs isolate the harder capability. Codex inferred a shifted, oversized
minimap crop and quantized markers against it. For Nisha at `10:38`, it reported
`G7 -> H5 -> I4` while GT is `I4 -> I4 -> I5`. Claude recovered the public event
index perfectly, but for Boxi at `11:34` reported `F7 -> E7 -> F8` while GT is
`G6 -> F6 -> F7`. Gemini also missed the event-indexing layer: near the GT m1CKe
death at `05:26`, it instead reported Boxi at `05:24` with a different killer and
trajectory. The task therefore targets long-horizon completeness, small-object
identity binding, and precise temporal-spatial tracking rather than kill
recognition alone. Full diagnostics, submitted answers, and raw rollouts are in
`calibration/`.

## Sources

- Video: <https://www.youtube.com/watch?v=EjVZaHmDPlw>
- Match record: <https://api.opendota.com/api/matches/8730786393>
- OpenDota minimap transform: <https://github.com/odota/web/blob/master/src/utility.tsx#L352-L373>
- Replay parser: <https://github.com/edeindl/gem-dota>
