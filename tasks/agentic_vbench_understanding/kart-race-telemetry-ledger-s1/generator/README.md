# P4 — SuperTuxKart race-telemetry ledger: generator

Programmatically renders a fully-labeled SuperTuxKart race video for the
`kart-race-telemetry-ledger` task. No manual annotation: the engine drives every kart and
prints exact per-kart telemetry, so each recorded run is its own machine-exact ground truth.

## Pipeline

```
run_suite.sh OUTDIR              # render N races on N tracks, parse each, concat -> race_suite.mp4
  └─ run_race.sh OUTDIR TRACK LAPS "kart1,..,kartK" [DIFFICULTY]   # one race
       └─ SuperTuxKart --profile-laps  (Xvfb + software GL, ffmpeg x11grab)
  └─ parse_profile.py stk_stdout.log gt.json --expect K           # profile table -> GT JSON
```

## Requirements

- SuperTuxKart 1.5 (prebuilt Linux binary; set `STK` in `run_race.sh`).
- `Xvfb`, a software-GL Mesa (`LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe`), and an
  `ffmpeg` with `x11grab` + `libx264` (this repo uses the `imageio-ffmpeg` build for encoding
  and the system ffmpeg for `ffprobe`).
- Python 3 with `numpy`/`Pillow` only for the optional review tooling; the generator itself
  is stdlib.

## Design notes (learned the hard way — see NOTES.md for detail)

- **Ground truth is `--profile-laps`, not the replay recorder.** Profile mode drives all
  karts by AI and prints the result table with no keypress, so the recorded run *is* the GT.
- **`parse_profile.py` is header-driven and asserted.** It reads columns from STK's own header
  line (an earlier positional regex silently mapped the wrong columns), asserts the parsed
  field size (`--expect`), and rejects duplicate karts — STK silently backfills an unknown
  kart id in `--aiNP` with a repeat, which would put two identical karts on track.
- **Every race is checked for a usable video.** `run_race.sh` picks a free X display (reusing
  a fixed one silently dropped the second race of a suite) and hard-fails if no video of
  sane length was written, instead of reporting success with nothing recorded.
- **SuperTux (difficulty 3) is deliberate.** The strongest AI overtakes, uses nitro and
  powerups and defends position, so grid order is not finishing order — which is what makes
  the reconstruction non-trivial.

## Scaling

The task is a generator, not a clip: 32 tracks × 18 karts × difficulty 0–3 × lap count ×
field size is an effectively unlimited space of distinct, machine-labeled races. Change the
`spec` list in `run_suite.sh` to mint new instances; hold out unseen (track, kart-set)
combinations for evaluation.

The shipped media came from the default `spec` list in `run_suite.sh`: **5 tracks × 10 karts ×
4 laps** on SuperTux difficulty (23.2 min). Field size matters for measurement as well as
difficulty — 10 karts give 45 tau-pairs per field instead of 15, which is what made a single
agent run separable from chance.

## Verifier

Task-side, at `myclone/tasks/agentic_vbench_understanding/kart-race-telemetry-ledger-s1/`.
Scores rank agreement (Kendall tau) over the OFF-HUD pickup counts only — items and nitro.
Finish order and start grid are reported for context but not scored, because the ranking column
and grid display them (calibration showed that rewarded leaderboard reading). Oracle 1.0, blind
guess 0.036 on the shipped 5x10 suite. See that task's `SPEC.md`.
