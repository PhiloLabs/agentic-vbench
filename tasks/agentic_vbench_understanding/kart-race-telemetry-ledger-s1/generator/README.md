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
  └─ (concat -> race_suite.mp4; hud_mask.py derives the mask box, drawbox writes race.mp4,
      verify_mask_box.py then checks the box in the file that ships equals the derived one)
  └─ build_ground_truth.py OUTDIR ground_truth.json             # hero-scoped GT (items+skid scored; spinouts context)
```

## Requirements

- SuperTuxKart 1.5, **patched** for the actual-skid columns (see *Actual-skid
  instrumentation* below); point `STK` at a directory holding a `run_game.sh` that execs it.
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

## Actual-skid instrumentation

The scored `skid_time` comes from a **patched** SuperTuxKart, not the stock build. Stock profile
mode prints one skid figure, and `KartWithStats::update` accumulates it whenever the skid INPUT is
held (`if(getControls().getSkidControl()) m_skidding_time += dt;`) — including while the kart is too
slow or airborne to actually drift. Measured on this suite it overstates visible drift by
1.136x–1.378x per race, so an agent timing the yellow sparks off the video cannot reproduce it at
any sane tolerance.

`generator/stk-actual-skid.patch` applies to upstream `supertuxkart/stk-code` commit `1fb491f` and
adds four drift readings, of which the scored one observes the particle emitter directly:

| column | clock | meaning |
| --- | --- | --- |
| `visible_skid_time` | rendered frames, i.e. recorded video | time the skid particle emitter was actually creating particles — **this is the scored `skid_time`** |
| `actual_skid_wall` | wall-clock | `SKID_ACCUMULATE_*` duration; an UPPER BOUND on the visible one (unscored context) |
| `actual_skid_time` | game | the same state in game seconds (unscored context) |
| `showgfx_skid_time` | game | the post-skid `SKID_SHOW_GFX_*` glow (unscored context) |

**Why the emitter and not the skid state.** The prompt defines the scored duration by the VISIBLE
yellow wheel sparks, and in pinned upstream STK three different predicates exist, each stricter than
the last:

- the skid state itself, `SKID_ACCUMULATE_LEFT/RIGHT`;
- the skid marks and the skid sound, which add `!isJumping()`
  (`graphics/skid_marks.cpp` and `karts/kart.cpp`);
- the sparks, whose emitter rate is raised only once the skid BONUS is in play, with the
  "tiny sparks" branch additionally requiring `!isJumping()` and a live skid state
  (`karts/skidding.cpp`).

Scoring the skid state therefore overstates what is on screen, and on this suite it overstates it by
more than the published 30 % tolerance on FIVE of the twelve races: sandtrack by 144 %,
stk_enterprise 107 %, olivermath 76 %, ravenbridge_mansion 43 %, cornfield_crossing 31 %. The
per-race scored/skid-state ratio spans 0.41-1.07 (it can exceed 1: the spray continues through the
3-4 s skid bonus after the drift itself ends). So `visible_skid_time` is read back from the emitter
(`KartGFX::getCreationRateFloat` on `KGFX_SKIDL`/`KGFX_SKIDR`) inside `Skidding::updateGraphics`,
which runs once per rendered frame and receives that frame's `dt`. The total is therefore in the
recorded video's own clock and equals the spark duration by construction, rather than being argued
to match it within a tolerance.

It also titles the `off_track_count` column, which stock prints in the data rows but omits from the
header, so header and rows now line up (`parse_profile.py` no longer drops a column by hand).

Scoring the wall-clock integral is what removes the game→video rescaling the earlier revision
applied. The suite is captured by `ffmpeg x11grab` at a constant wall-clock frame rate, so
wall-clock seconds *are* video seconds. The old rescale used `clip_duration / game_duration`, which
is not that ratio: on hacienda the clip ran 1.224x longer than game time while the drift's own
wall/game ratio was 1.152, and across the suite the two disagree by as much as 0.241
(cocoa_temple, 1.927 vs 1.686).

Build:

```
git clone https://github.com/supertuxkart/stk-code && cd stk-code
git checkout 1fb491f
git apply .../generator/stk-actual-skid.patch
cmake -B build_gfx -DCMAKE_BUILD_TYPE=Release && cmake --build build_gfx -j
```

Assets come from the 1.5 binary release (`SUPERTUXKART_DATADIR`, `SUPERTUXKART_ASSETS_DIR`).

## Per-race config isolation

`run_race.sh` gives each race its own `HOME`/`XDG_CONFIG_HOME`/`XDG_DATA_HOME` under
`$OUT/stkhome`, and does not inherit the host's. Two distinct reasons, both load-bearing:

1. Races run in parallel, so a shared config is written concurrently by up to `CONC` processes.
2. The mask box in `hud_mask.py` is derived for STK's **default** indicator placement (centred,
   `display 0`) at the default 64 px. A config that moved the indicator to the side (`display 1`)
   or resized it would put sprites outside the box, so the shipped media would leak exactly what
   the mask exists to hide.

`check_hud_config.sh` asserts the second point on the config THAT RACE wrote, and `run_race.sh`
calls it after the render, so a non-default HUD fails the race instead of producing quietly leaky
media. The check is exercised in all four states (default config, `display="1"`, a resized icon, no
config at all) and only the first passes.

**The shipped render already satisfied this**, verified after the fact rather than assumed, so it
does not need regenerating: the v3 suite left twelve independent config homes (one per race,
`stkhome77`..`stkhome88`, matching the `STK_DISP = 77+i` the runner assigns), each written inside
the render window, each a distinct inode from every other and from `~/.config/supertuxkart`, each
recording `1280x720`, and each carrying `display="0"` with `powerup-icon-size="64.000000"`.

**The two guards, and the test that proves they fire.** `generator/test_guards.sh` (13 cases, pure
stdlib + bash) exists because both guards were weaker than they looked:

* `check_hud_config.sh` matched the string prefix `powerup-icon-size="64`, which also accepts **640**
  and **64999**. It now parses the number and compares it EXACTLY against `hud_mask.POWERUP_SIZE`,
  read from `hud_mask.py` itself rather than repeated, so the guard cannot drift from the box it
  protects. The test covers display 1 / display 2 / 96 / 640 / 64999 / 63.999 / missing config /
  `<PowerUp>` with no attributes, and requires each to be REJECTED with the right exit code.
* `run_race.sh` and `run_suite.sh` re-used a populated output directory, so a re-run would assert on
  the PREVIOUS race's `config.xml` and could concatenate a stale `race_raw.mp4` left by a failed
  render. A non-empty output directory is now refused (exit 14) unless
  `AGENTICVBENCH_ALLOW_DIRTY_OUT=1` is set deliberately. The check runs with the other ARGUMENT
  validation, before the environment checks, and `AGENTICVBENCH_PRECHECK_ONLY=1` exercises it
  without rendering.

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
laps** on SuperTux (65.5 min).

## Verifier

Task-side, at the task dir's `steps/solve/tests/judge.py`. Scores an **exact-count** metric —
`clamp(tau,0,1) · within-30%-accuracy` — over the two scored hero quantities above (weights
items 0.55 / skid_time 0.45), renormalised over fields that vary. Positions, nitro
and the banana/explosion split are reported for context but not scored (positions are on the HUD;
the split is not visually distinguishable). On THIS instance, measured without an agent: oracle 1.0, blind guess 0.0104 (20 seeds), wrong-times / constant / empty / symlinked-key all 0.0, 26/26 scorer regressions. The host-run 3-agent lineup (max 0.0885) was measured on superseded instances and is VOID; the clean gate-setting pilot on this instance is pending (see `SPEC.md` / PR #106).
