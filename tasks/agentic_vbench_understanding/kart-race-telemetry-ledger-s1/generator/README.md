# P4 — SuperTuxKart race-telemetry ledger: generator

Programmatically renders a fully-labeled SuperTuxKart race suite for the
`kart-race-telemetry-ledger` task. No manual annotation: the engine drives every kart and prints
exact per-kart telemetry, so each recorded run is its own machine-exact ground truth. The camera
follows one **hero kart** (`tux`) and only the hero's telemetry is scored, so every scored event is
on-camera by construction.

## Pipeline

```
run_suite.sh OUTDIR                                   # render the 12-race suite, then:
  └─ run_race.sh OUTDIR TRACK LAPS "kart1,..,kartK" DIFF HERO   # one race, camera on HERO
       └─ SuperTuxKart --profile-laps --kart=HERO --ai=<rest>   # Xvfb + software GL + ffmpeg x11grab
  └─ parse_profile.py  stk_stdout.log gt.json --expect K        # profile table -> per-race GT
  └─ (concat -> race_suite.mp4; the shipped race.mp4 masks the top-center HUD powerup slot)
  └─ build_ground_truth.py OUTDIR ground_truth.json             # hero-scoped GT (items+skid scored; spinouts context)
```

## Requirements

- SuperTuxKart 1.5 (prebuilt Linux binary; set `STK` in `run_race.sh`).
- `Xvfb`, software-GL Mesa (`LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe`), and an `ffmpeg`
  with `x11grab` + `libx264` (this repo uses the `imageio-ffmpeg` build for encoding and the system
  `ffprobe`). The generator itself is stdlib Python 3.

## What is scored (and why it is observable)

Two off-HUD, machine-exact SCORED quantities of the **hero** kart, per race (plus spinouts, computed but UNSCORED context):
- **`items_collected`** — powerup boxes driven through (HUD powerup slot masked in the shipped video).
- **`spinouts`** = `bananas_hit + times_exploded` — a banana hit and a bomb hit render as the *same*
  dizzy-stars spin-out and are not distinguishable at 720p; their sum (spinouts) is kept as UNSCORED context — not scored, since a strong agent counts it too well to be a difficulty lever.
- **`skid_time`** — drift seconds; drifting shows as bright yellow sparks off both rear wheels.

`build_ground_truth.py` emits the two scored fields (plus context incl. spinouts) and refuses to ship a suite
where any scored field has no spread across races.

## Design notes (learned the hard way — see NOTES.md)

- **Ground truth is `--profile-laps`, not the replay recorder.** Profile mode drives all karts by
  AI and prints the result table with no keypress, so the recorded run *is* the GT.
- **Hero-scope makes it observable.** `--kart=HERO --ai=<rest>` makes HERO the (still AI-driven)
  player kart the profile camera follows; scoring only the hero guarantees no scored event is off
  screen (the reviewer's twelve-kart observability point).
- **`parse_profile.py` is header-driven and asserted.** Columns are read from STK's own header line,
  the parsed field size is asserted (`--expect`), and duplicate kart ids are rejected (STK silently
  backfills an unknown `--aiNP` id with a repeat, which would put two identical karts on track).
- **Every race is checked for a usable video.** `run_race.sh` pins a unique X display per race
  (`STK_DISP`, so parallel races don't collide) and hard-fails if no sane-length video was written.
- **SuperTux (difficulty 3) is deliberate** — the strongest AI genuinely fights for boxes, gets
  bombed, and drifts hard corners, so the counts are non-trivial.
- **Track choice matters for software GL.** `black_forest` renders in slow-motion under llvmpipe
  (dense foliage) and was replaced with `olivermath`.

## Scaling

This is a generator, not a clip: tracks × karts × difficulty × laps × field size is an effectively
unlimited space of distinct, machine-labeled races. Edit the `SPECS` list in `run_suite.sh` to mint
new instances or hold out unseen (track, kart-set) combinations. More races/laps lower a strong
agent's score (recall of accurate counts drops); the shipped suite is **12 tracks × 10 karts × 4
laps** on SuperTux (53.4 min).

## Verifier

Task-side, at the task dir's `steps/solve/tests/judge.py`. Scores an **exact-count** metric —
`clamp(tau,0,1) · within-30%-accuracy` — over the two scored hero quantities above (weights
items 0.55 / skid_time 0.45), renormalised over fields that vary. Positions, nitro
and the banana/explosion split are reported for context but not scored (positions are on the HUD;
the split is not visually distinguishable). Oracle 1.0, blind guess ~0.02; the host-run 3-agent lineup (Codex / Claude Code / Gemini-3.5-flash) all scores < 0.10 (host-run with the pinned CV-tool profile: Gemini max 0.0885; stdlib cross-check max 0.0436). A clean gate-setting pilot on the finalized image is pending (see `SPEC.md` / PR #106).
