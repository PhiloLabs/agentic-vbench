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

`steps/solve/tests/judge.py` performs strict monotonic clearance matching inside
each independent flight leg. The main reward is exact complete-leg chain
accuracy blended with clearance-chain F1:

```text
reward = 0.9 * exact_leg_accuracy + 0.1 * clearance_chain_f1
```

A leg counts only when all 13 clearance chains match, with no missing or extra
event. This preserves diagnostic partial credit without allowing isolated
single-gauge success to dominate the complete-ledger objective. Each clearance
requires the complete command, target, maximum commanded-direction progress,
three-instrument states at issue/execution/completion/window-end, timing,
status, supersession, and overshoot chain to match. Invalid or malformed output
receives zero.

The verifier uses Python standard library only and does not access the network
or call a model.

## Calibration

Required full-media runs:

- Codex CLI with GPT-5.6 Sol;
- Claude Code with Opus 4.8;
- Antigravity with Gemini 3.5 Flash.

Required degraded-input runs use the same prompt/model family with no media,
one representative frame, video-only, audio-only, and a pre-extracted frame
dump with agent tools disabled. Raw trajectories are retained under
`calibration/rollouts/`; the measured table is in `calibration/scores.md`.
