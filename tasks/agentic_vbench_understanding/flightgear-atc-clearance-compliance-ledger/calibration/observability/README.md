# Observability audit — are the ledger's snapshots readable at all?

The first revision of this task audited 19 of the 65 events. The maintainer
asked for all 65 before any more calibration runs, on the grounds that the
scoreboard looked like an unreadable metric rather than weak models: two of
three agents scored exactly 0 on complete 65-entry answers, and the audio-only
ablation beat every run that included video.

That reading was correct. This directory is the full audit, and the conclusion
is that the originally shipped 25 ft / 2 deg / 2 kt state tolerances were
satisfiable on only 5 of the 65 events — not literally impossible, but far too
tight to separate a good reader from a bad one. Three independent lines of
evidence say so, and the third needs no video at all.

## 1. Empirical: a reader sampled against all 65 events

`measure_observability.py` compares a pre-computed reconstruction of the three
instruments against every ground-truth snapshot — 65 events, 235 snapshots. Full
per-snapshot errors are in `audit_65_events.json`.

Read this section as corroboration only, and note two limits before the table.
The script is a comparison harness: it loads `telemetry.npz` and contains no
video-decoding code, so what reproduces here is the comparison, not a fresh
derivation from the video. And the reconstruction came from the Claude Opus 4.8
rollout's own instrument reader, which is the same run that scores highest under
the tolerances this table is used to justify. Sections 2 and 3 are the
reader-independent arguments and are the ones to lean on.

| alt | hdg | spd | snapshots within | events fully within |
|---:|---:|---:|---|---|
| 25 | 2 | 2 | 83/235 (35.3%) | **5/65 (7.7%)** |
| 50 | 4 | 3 | 229/235 (97.4%) | 59/65 (90.8%) |
| 75 | 6 | 3 | 232/235 (98.7%) | 62/65 (95.4%) |
| 100 | 8 | 3 | 232/235 (98.7%) | **62/65 (95.4%)** |
| 150 | 10 | 5 | 232/235 (98.7%) | 62/65 (95.4%) |
| 200 | 12 | 6 | 232/235 (98.7%) | 62/65 (95.4%) |

There is a cliff between the shipped tolerances and the next step, and a plateau
that begins at 75/6/3. The metric was sitting on the wrong side of the cliff.
The empirical data does not by itself distinguish 75/6/3 from 100/8/3 — both
land on 62/65, and widening further buys nothing. The tie-break is that
100 ft / 8 deg / 3 kt is not an arbitrary landing spot: it is the capture band
`instruction.md` already uses to define when a clearance is complete, so the
scorer and the task definition now use one number rather than two.

The residual 3 events (#9, #12, #13) are all the same `ending` snapshot at
t=719.0, the last second before the first leg cut, where the supplied
reconstruction is 15 kt off. That is a limitation of this reader, not a measured
property of the video: `telemetry.npz` saturates — `spd_kt` sits at exactly 72.0
for t=562..719 instead of following leg 1's deceleration toward 57 kt, and
`alt_ft` flattens at 4399.8 over t=705..719. The three residuals are the tail of
that flat-line.

This matters because the same window is cited in `SPEC.md` as headline
required-modality evidence ("an acceleration to 87 knots is followed by visible
deceleration to 57 knots"). So the honest statement is narrower than an earlier
draft of this file claimed: those three events are where *this reconstruction*
fails, and the audit does not establish whether the video is harder to read
there. Nothing in the tolerance choice depends on them — 62/65 versus 65/65
lands on the same plateau either way.

Reproduce:

```bash
python3 calibration/observability/measure_observability.py \
    --telemetry calibration/observability/telemetry.npz
```

`telemetry.npz` is the reconstruction itself (3600 samples at 1 Hz, 21 KB), so
the audit re-runs without downloading the 323 MB video.

## 2. An irreducible bias an agent cannot discover

`anchoring_bias.py` uses **only** `ground_truth.json`. It measures the cheapest
audio-only strategy — assume the aircraft ends up exactly where it was told to
go — against the 50 of 65 clearances that actually reached a stable hold
(`status` in `complied`, `complied_late`). The other 15 are superseded,
violated, or incomplete: they never settle on their target, so including them
would measure the interruption rather than the bias.

Heading and airspeed holds land *exactly* on the commanded value — across 20
heading clearances and 15 airspeed clearances the ending state matches the
target with standard deviation 0.000. Altitude does not:

```
ending altitude - commanded altitude:  mean -27.14 ft   sd 7.95
                                       range -42.91 .. -18.68 ft
```

So an agent that anchors its readings on the commanded values is exactly right
on two instruments and irreducibly wrong on the third, by 19-43 ft against what
was a 25 ft budget. Nothing in the video reveals that offset. Relatedly, ground
truth `completion_altitude_ft` sits within a hair of +/-100 ft of target (min
-99.98, max +99.91): completion is defined by the 100 ft capture band, so
landing inside 25 ft of it demanded sub-second precision on a completion time
that was itself allowed 4 s of slack.

Reproduce:

```bash
python3 calibration/observability/anchoring_bias.py
```

## 3. Reader-independent: the tolerances contradicted each other

`tolerance_consistency.py` uses **only** `ground_truth.json` -- no media, no
reader, no model -- so it cannot be dismissed as one vision pipeline's weakness.

A ledger entry names an event time and the instruments *at* that time, and the
event time is separately allowed to be off by up to 4 s. During a manoeuvre
those two allowances fight: an answer well inside the timing tolerance is still
reading the gauges somewhere else on the trajectory, wrong by `|rate| * dt`
through no fault of its own.

```
state tolerance 25 ft / 2 deg / 2 kt   -> 47 of 65 clearances unsatisfiable
state tolerance 100 ft / 8 deg / 3 kt  -> 28 of 65 clearances unsatisfiable
```

A flat budget cannot fix this. Heading swings up to 16.2 deg inside the timing
tolerance, so a flat budget wide enough to be self-consistent would be too wide
to mean anything on a turn.

So the judge does not use a flat budget, and it does not widen the band either.
Each snapshot is compared against the trajectory **interpolated to the timestamp
the answer itself reports**, reconstructed piecewise-linearly between the ground
truth's own issue, execution, and completion anchors. An answer whose timestamp
was right is read at the true moment and gets the strict band; an answer that
was late and honest about what it then saw is read at the moment it claims, and
is not charged twice for one mistake. The timestamp error is still paid for, out
of the timing group.

This replaces an earlier revision that widened each snapshot's band by the error
the accepted timing slack could force. That version removed the contradiction
but handed the widened band to every answer, including those whose timestamps
were exact — it bought consistency by making the strict case looser too.

The script verifies the shipped judge on this directly:

```
every event shifted +1s, gauges read at the shifted moment: state credit 260/260, reward 1.0000
every event shifted +2s, gauges read at the shifted moment: state credit 244/260, reward 0.5987
every event shifted +4s, gauges read at the shifted moment: state credit 216/260, reward 0.5203
```

State credit stays high because the readings are honest; reward falls because
the shift is charged to timing, which is the intended split. Under the old
scorer those same answers scored 0 outright.

## What this does not claim

The reconstruction in `telemetry.npz` came from the Claude Opus 4.8 rollout's
own instrument reader, and the same author wrote the revised scorer. That is a
conflict worth naming: measured achievability and the tolerance choice are not
fully independent of the run that scores highest under them.

The two arguments above that do not depend on that reader -- the anchoring bias
in section 2 and the internal contradiction in section 3 -- are the ones to lean
on, and both are computed from `ground_truth.json` alone. Section 1 is
corroboration, not the basis for the tolerance choice.
