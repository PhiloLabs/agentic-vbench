# FlightGear task runbook

## Public solve environment

The agent receives only:

```text
/workspace/materials/flight.mp4
```

The image also provides `ffmpeg`, `ffprobe`, and an offline `transcribe`
command backed by `faster-whisper-small.en`. Internet access is disabled.

Telemetry, command schedules, generated ATC clips, controller traces, scenario
configuration, and ground truth never enter `/workspace`.

## Ground-truth construction

The fixed recording was generated as five independent scenario-controlled
12-minute FlightGear C172P legs and concatenated losslessly into one 60-minute MP4. The
public instruction states the exact hard-cut boundaries; aircraft state and
open-clearance chains reset at each boundary. Each source leg recorded:

- the executed spoken-command timeline;
- the actual command-application time;
- the external scripted controller state at 10 Hz;
- FlightGear raw and indicated state telemetry;
- the rendered 1280x720 cockpit at 15 fps.

The visible heading gyro is refreshed continuously so indicated heading tracks
the rendered aircraft state for the entire recording. Validation rejects a
segment when expected outcome classes differ from derived classes, when the
heading indicator diverges from raw heading, or when controller traces diverge
from FlightGear telemetry.

Ground truth is derived from the executed command log and indicated telemetry
using the exact public definitions in `steps/solve/instruction.md`.

## Scoring

`steps/solve/tests/judge.py` matches clearances one-to-one across the whole
recording, order-preserving, and pays graded credit per clearance.

A predicted clearance is matched to a ground-truth clearance on `command_type`
and an issue time inside the 2-second tolerance. Matching is global rather than
bucketed by leg: an earlier revision assigned each prediction to a leg by
`issued_time_s // 720` before matching, which dropped a prediction landing a
fraction of a second on the wrong side of a hard cut into the neighbouring leg,
where it could never match. The time tolerance is now the only thing that
decides, so a 1.5-second-early prediction across a cut still matches.

A matched pair then earns credit group by group, out of twenty units: target 4,
status 4, instrument snapshots 4, timing 4, supersession chain 2, progress 2.
Snapshots earn 4 when all four states are within the 100 ft / 8 deg / 3 kt
capture band and 2 when only issue and ending are. Timing pays 2 units per
timestamp — full within 1 second of truth, half within 4, nothing beyond. The
supersession group is an all-or-nothing pair: it requires both the resolved
`superseded_by_index` link *and* a correct `overshoot_bucket`, so a right
supersession with the wrong bucket earns 0 of the 2 units.

Snapshots are compared against the trajectory *interpolated to the timestamp the
answer itself reports*, reconstructed piecewise-linearly between the ground-truth
issue, execution, and completion anchors, rather than against the true event
time. An answer that is honest about a slightly-off timestamp is therefore not
charged twice for one mistake, while the timestamp error itself is still paid for
out of the timing group. This replaces an earlier design that widened the state
band by whatever error the accepted timing slack could force, which handed out
the widened credit even to answers whose timestamps were exact.

Raw units are not the score. Each clearance is first discounted by what the
*transcript alone* could have said about it:

```text
gain       = clip((units - transcript_only_units) / (20 - transcript_only_units), -1, 1)
gradable   = clearances where 20 - transcript_only_units > 0
spurious   = max(0, submitted - matched)
reward     = max(0, sum(gain)) / (len(gradable) + spurious)
```

The `max(0, ...)` on the numerator is what stops a ledger that is worse than the
transcript everywhere from going negative; per-clearance gains still subtract
freely below it, which is what makes guessing net out.

`transcript_only_units` is the best any audio-only strategy achieves on that
clearance, searched over the plausible ones: constant-gauge guessing, carrying
each spoken target forward as a believed instrument value, four status priors,
four overshoot priors, and supersession inferred from the spoken schedule. ATC
names every target aloud and holds land exactly on the commanded heading and
airspeed, so this ceiling is high — which is the point. It is a per-clearance
ceiling, not one global best ledger, so no single audio strategy can clear it
anywhere. On this release it is 953 of 1300 units, leaving 60 of 65 clearances
gradable; the other five are fully answered by the transcript, carry no video
signal, and leave the denominator rather than paying every submission for free.

The gain is deliberately signed. A shortcut answer that merely ties the ceiling
on average would otherwise profit from its own variance, since per-clearance
clipping at zero would keep its lucky guesses and discard its unlucky ones.
Letting a below-ceiling clearance subtract makes guessing net out at zero, which
is what the measured anchors show.

One consequence is disclosed rather than fixed: because a below-ceiling
clearance subtracts, an agent that could identify its own weak readings could
raise its score by withholding them. `calibration/rescore_ledgers.py` reports
that residual incentive per row in its `pruned` column.

Invalid or malformed output receives zero. The verifier uses the Python standard
library only and does not access the network or call a model.

## Calibration

Required full-media runs:

- Codex CLI with GPT-5.6 Sol;
- Claude Code with Opus 4.8, run natively as `claude -p` on the shipped
  instruction with no wrapper prompt;
- Antigravity with Gemini 3.6 Flash High.

Required degraded-input runs use the same prompt/model family with no media,
one representative frame, video-only, audio-only, and a pre-extracted frame
dump with agent tools disabled. Required-agent trajectories are retained under
`calibration/rollouts/`; the native Claude one is committed in condensed form
with its raw file pinned as a release asset, and `rollouts/README.md` gives the
hashes and the command that regenerates the committed copy from it. Ablation and
replaced-round trajectories are hash-pinned release assets listed in
`calibration/ablations/README.md`. The measured table is in
`calibration/scores.md`, and the tolerance evidence behind it is in
`calibration/observability/`.

Everything above reproduces from the repository alone, with no rollout replay,
no model call, and no network:

```bash
python3 -m unittest discover -s steps/solve/tests -p 'test_judge_unit.py'
python3 calibration/rescore_ledgers.py        # every number in scores.md
python3 calibration/shortcut_probe.py         # 29,100 video-free probes, ~3 min
python3 calibration/observability/measure_observability.py \
    --telemetry calibration/observability/telemetry.npz
python3 calibration/observability/anchoring_bias.py
python3 calibration/observability/tolerance_consistency.py
```

`shortcut_probe.py` exits non-zero if any video-free probe clears the
`AGENT_MAX = 0.10` gate, so it is safe to wire into CI as a regression guard on
the anti-shortcut property.
