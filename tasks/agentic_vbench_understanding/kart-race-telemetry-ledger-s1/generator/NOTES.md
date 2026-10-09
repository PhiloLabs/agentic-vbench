# P4 — SuperTuxKart race-telemetry ledger: build notes

## Ground truth is solved (2026-07-22)

The blocker was triggering STK's replay recorder without a keypress. It is unnecessary:
**profile mode** drives every kart by AI and prints a machine-exact per-kart table to stdout.

```sh
cd SuperTuxKart-1.5-linux-x86_64
./run_game.sh --no-graphics --profile-laps=2 --track=hacienda --numkarts=6 \
              --aiNP=tux,gnu,adiumy,amanda,beastie,kiki
```

Printed columns (one row per kart, in grid order):

```
name start_position end_position time average_speed top_speed skid_time rescue_time
rescue_count brake_count explosion_time explosion_count bonus_count banana_count
small_nitro_count large_nitro_count bubblegum_count
```

Notes learned the hard way:
- Short flags `-t` / `-k` are rejected in this build — use `--track=` / `--numkarts=`.
- `--aiNP=` = AI karts with **no** player kart, so nothing needs input. Unknown kart names
  are silently dropped (`sara` is not a kart id; `sara_the_racer` is), which silently
  changes the field size — always assert the row count equals `--numkarts`.
- Headless runs at ~11 000 FPS: a 2-lap 6-kart race profiles in under a second, so GT is
  cheap to regenerate.
- Profile mode works with graphics on as well, so the *recorded* run can be its own GT —
  no cross-run determinism assumption needed.

## The HUD mask is verified by its box, not by hunting sprites (2026-09-04)

The first mask box was hand-fitted from a comment that mis-stated the sprite geometry, and it was
35 px too narrow on the left. `hud_mask.py` now derives the rectangle from STK's own drawing code
and self-tests it: at 1280x720 a single local player gives scale 1.6, so icons are 102 px tall at
y 32..134, and because the row is centred it is widest at `MAX_POWERUPS = 5`, spanning x 488..794.
The old box started at x=505, so with five items held a 17 px strip of the leftmost icon stayed
visible — enough to signal both that an item was held and, from the shifted layout, how many.

The obvious check — look for the sprites in the rendered video — does not work, and this was
measured rather than assumed. A held sprite is static while the scenery moves, so a burst of
consecutive frames separates it in principle; in practice STK powerup icons are mostly transparent
(`icon-bubblegum.png` is 22% opaque, mean alpha 0.28), so only a sprite's opaque core is static,
and the surviving signal does not separate from ordinary scenery. Sweeping the static-row and
texture thresholds over 40 scenery bursts plus a held-out set of 40: every setting sensitive enough
to catch a 17 px sliver also fired on 3–6 scenery bursts, and every setting that silenced scenery
also missed the sliver. Detecting the black box instead is unambiguous — it is found in 24/24
sampled frames, to the pixel — so `verify_mask_box.py` measures the shipped rectangle and compares
it to the derived one, and is checked in both directions (it must report the unmasked concat as
unmasked). Frames that are black all over, the transitions between races, are why presence needs
an agreement threshold rather than a single hit.

## What the scored drift duration is, and two ways of measuring it that were wrong (2026-09-08)

The prompt defines the scored drift duration by the VISIBLE yellow wheel sparks. Pinned upstream STK
has three progressively stricter predicates, so "the kart is skidding" is not that quantity:

| cue | condition | where |
| --- | --- | --- |
| skid state | `SKID_ACCUMULATE_LEFT/RIGHT` | `skidding.cpp` |
| skid marks, skid sound | the above **and** `!isJumping()` | `skid_marks.cpp:162`, `kart.cpp:2637` |
| the sparks | emitter rate raised on the skid bonus; the level-0 "tiny sparks" branch also needs `!isJumping()` and a live skid state | `skidding.cpp:285`, `:298` |

An earlier note here claimed the jump flag never clears in this build. That was wrong: it is
decremented in `Skidding::updateGraphics`, which runs once per RENDERED frame, and these renders
have graphics. The level-0 spark rate is also NOT zero -- `data/gfx/skid0.xml` sets 200 particles/s
(levels 1 and 2 use 2000 and 2500) -- so sparks do appear on ordinary skids, and the gap between the
skid state and the sparks is mostly the jump exclusion.

The scored value is now read from the emitter itself: `KartGFX::getCreationRateFloat` on
`KGFX_SKIDL`/`KGFX_SKIDR`, sampled in `Skidding::updateGraphics`. That observes what is drawn instead
of re-deriving the predicate that decides it.

**Two measurement attempts failed first, both instructive.**

*Pixels do not work.* Sparks are bright yellow, but so are the dizzy-stars of a spin-out and the
yellow of an explosion, and the nitro exhaust is bright and warm too. On labeled frames the
"small yellow blob" count reached 1021 for dizzy-stars and 3688 for an explosion while genuine
sparks gave 70 to 562, so no threshold separates them. This is the same conclusion the HUD-mask
sprite audit reached, for the same reason: brightness and hue are not identity.

*Summing the graphics `dt` measures frame RATE, not elapsed time.* The first emitter-based version
accumulated the frame delta while the emitter was on. It looked plausible on a single fast race
(about half of wall-clock) and collapsed on the loaded twelve-race run (about a ninth, with three
races at exactly 0.00). The tell was the ratio moving with machine load. The emitter-on duration now
comes from `StkTime::getMonoTimeMs()` deltas, like the existing wall-clock accumulator, so it is a
duration in the recorded video's own clock regardless of how fast the render was. A clean two-lap
probe then gave 28.13 s of emitter-on against 34.58 s of skid state, correctly ordered and a 23%
gap.

**The actual root cause: a whole-race total cleared by a mid-race reset.** Three instrument
versions read 0.00 s on several races, and the explanations that looked obvious were all wrong. What
settled it was a per-rendered-frame TRACE (`AGENTICVBENCH_SKIDTRACE=1`, in the patch) logging the raw
facts instead of a derived total. On scotland it showed: graphics on (`nog=0`), the emitter present
(`hasL=1`), the emitter running at 200/2000/2500 particles/s on 756 of 2285 hero frames -- and the
accumulated total climbing to 25.045 s and then dropping to exactly 0.000 TWICE, at t=48.7 s and
t=105.7 s.

`Skidding::reset()` is called mid-race whenever the kart is reset, and the first version of this
patch cleared `m_visible_skid_time` there. So every race whose last reset fell after its last drift
reported exactly zero, and the surviving value depended on WHEN the last reset happened -- which is
why the numbers looked track-dependent and irreproducible. The whole-race counters in
`KartWithStats` were unaffected because that class resets once per race. The total is now
initialised in the constructor and left alone by `reset()`, which only re-bases the clock so the gap
across a reset is not credited as visible time.

Three earlier conclusions recorded here were wrong and are withdrawn: that the 0.4 s
`graphical-jump-time` gated the cue (setting it to 0 changed nothing), that only 1 of 15 tracks
sustains visible drift (the survey was measuring reset timing), and that the field was degenerate
and should be dropped. On the corrected instrument all 12 races carry 9.34-172.38 s, all distinct,
none degenerate. The flick statistics above are still accurate as a description of how the AI
drives; they are simply not why the totals were zero.

**End-to-end validation against the video (the check that was missing).** Everything above
validates the instrument from the SOURCE side. That is not the same as showing the number matches
what a viewer sees, so this is the independent check, and it deliberately avoids needing a
frame-accurate alignment between the trace clock and the video clock (the two candidate anchors
disagreed by ~2 s, which is too coarse for interval-by-interval comparison).

Method: the trace says the hero's skid emitter was ON for 40.54 s of a 117.49 s render span, i.e.
34.5 % of the time. If that is the visible-spark duration, then that same fraction of UNIFORMLY
sampled video frames should show sparks. 48 frames were sampled uniformly across the span from that
race's own recording and scored BY EYE (colour cannot do it):

| | value |
| --- | --- |
| emitter-on share, from the trace | 34.5 % |
| frames showing spark spray at the wheels | 17 of 44 = 38.6 % |
| binomial SE at n=44 | 7.2 % |
| difference | 0.57 SE — consistent |

Four frames were excluded as unscorable (one loading screen, two fully occluded by an item, one
end-of-race fade). Three frames were judged conservatively as NO: the orange nitro flame with a few
specks, a motion-blurred streak, and a yellow road marking. Flipping all three moves the fraction by
about 2 points and changes nothing. The blue nitro/zipper flames (3 frames) are correctly not
sparks, and the emitter measure reads only `KGFX_SKIDL/R`, so it cannot count them either.

Known residual limitations, none of which this evidence hides:
  * The integration credits the whole inter-frame interval to the state sampled at its end, so each
    ON/OFF transition can be off by up to one rendered frame (~50 ms). With 28 ON intervals that
    bounds the error near 1.4 s on 40.5 s, about 3 %.
  * The quantity is wall-clock, so it is NOT reproducible across renders: the GT describes the
    render it shipped with, which is why re-rendering means re-deriving the key.
  * Extended to SEVEN of the twelve races on the SHIPPED media (below), not just the probe.

**Extended to seven races on the shipped media.** The same alignment-free test, now run against
`race.mp4` itself rather than a probe recording. For each race the predicted spark share is
`skid_time / racing_span` (the racing span excludes the opening "Loading" checkerboard, detected by
where colour appears, and a 1.5 s tail); 24 frames per race were sampled uniformly across that span
and scored BY EYE.

| race | predicted | observed | n | deviation |
| --- | --- | --- | --- | --- |
| sandtrack | 3.3 % | 0.0 % | 23 | 0.89 SE |
| stk_enterprise | 5.0 % | 4.2 % | 24 | 0.19 SE |
| cornfield_crossing | 10.8 % | 16.7 % | 24 | 0.93 SE |
| hacienda | 25.7 % | 21.7 % | 23 | 0.43 SE |
| lighthouse | 28.8 % | 33.3 % | 24 | 0.49 SE |
| gran_paradiso_island | 34.7 % | 29.2 % | 24 | 0.57 SE |
| scotland | 38.2 % | 33.3 % | 24 | 0.49 SE |

Correlation r = **0.947** across predictions spanning 3.3-38.2 %, no race off by even 1 SE, and
pooled 33 of 166 frames = **19.9 %** observed against **21.0 %** predicted (z = -0.36). A key that
was measuring the wrong thing could not track a twelvefold range this closely.

Honest limits of this audit: the scoring was NOT blind (the predictions were known), so it is
vulnerable to unconscious bias. Two mitigations are visible in the numbers rather than asserted: the
criterion was mechanical (yellow spray emanating from the rear wheels, which excludes the blue/orange
nitro flame, the dizzy-stars of a spin-out, yellow road markings and bright sand), and every
ambiguous frame was scored AGAINST the hypothesis (two nitro-plus-specks frames in hacienda scored
NO, which pushed that race further below its prediction). Deviations also change sign across races
rather than all favouring agreement. A blind protocol would still be stronger, and the five
remaining races have not been audited this way.

**Why render_speed_factor exists, and why it is kept.** `main_loop.cpp`'s `getLimitedDt()` clamps
the frame delta to 50 ms ("when the computer can't keep it up, slow down the shown time instead"),
and under software rendering our frames exceed that, so game time advances slower than the wall
clock. That clamp IS the 1.27-2.24 factor; nothing else contributes. `setAllowLargeDt()` disables it
and nothing calls it.

Uncapping it would make game time equal wall time and the key machine-independent, and it is
deliberately NOT done: the clamp is also what puts the footage into slow motion, and slow motion is
what makes a sub-second drift last long enough to land in a 15 fps capture. Uncapping would shorten
the suite to roughly 40 min, lower the effective frame rate and begin hiding the sparks the agent is
asked to time -- reopening a gap between the key and what is visible. The machine-dependent key costs
nothing in fairness, because the key always ships with the render it was measured on.

**Row-level blind validation of every race (PR #106, review round 4).** The reviewer asked for the
remaining five races to be finished BLIND and for the low-prevalence rows to be strengthened, since
`skid_time` carries 45 % of the reward and five wrong rows could move 0.1875, more than the 0.10
difficulty gate. All twelve rows were therefore re-done under one protocol.

*Protocol.* For each race the emitter-derived share is `skid_time / racing_span`, where the racing
span excludes the opening "Loading" checkerboard (located by where colour first appears) and a 1.5 s
tail. Frames were sampled uniformly across that span, sized so every race yields at least ~6.5
EXPECTED positives (so sandtrack's 3.3 % share gets 195 frames, not 24). All 816 frames were then
POOLED ACROSS RACES, SHUFFLED, and written out under opaque ids (`F0000`...); the id-to-race-and-time
mapping was not consulted until every frame had been scored. Scoring criterion, fixed before looking:
POSITIVE = yellow spray emanating from the REAR WHEELS, which excludes the blue/orange nitro flame,
the dizzy-stars of a spin-out, yellow road markings and bright sand; UNSCORABLE = frame fully
occluded by an item, a loading screen, or an explosion whiteout. hacienda was later given 96
additional frames at a quarter-step offset (see below).

| race | emitter `skid_time` | emitter share | blind visual | frames | deviation | if every borderline call = negative |
| --- | --- | --- | --- | --- | --- | --- |
| `sandtrack` | 9.34 s | 3.3 % | 1.5 % (3/195) | 195 | -1.35 SE | 1.5 % (-1.35 SE) |
| `stk_enterprise` | 15.13 s | 5.0 % | 6.8 % (9/133) | 133 | +0.97 SE | 6.0 % (+0.57 SE) |
| `ravenbridge_mansion` | 34.67 s | 9.4 % | 18.1 % (13/72) | 72 | +2.53 SE | 11.1 % (+0.51 SE) |
| `cornfield_crossing` | 45.76 s | 10.8 % | 7.8 % (5/64) | 64 | -0.77 SE | 4.7 % (-1.57 SE) |
| `olivermath` | 16.83 s | 12.1 % | 9.4 % (5/53) | 53 | -0.60 SE | 9.4 % (-0.60 SE) |
| `cocoa_temple` | 56.34 s | 14.1 % | 14.6 % (7/48) | 48 | +0.09 SE | 10.4 % (-0.74 SE) |
| `snowmountain` | 68.23 s | 23.1 % | 33.3 % (13/39) | 39 | +1.52 SE | 30.8 % (+1.14 SE) |
| `hacienda` | 76.74 s | 25.7 % | 22.6 % (30/133) | 133 | -0.82 SE | 20.3 % (-1.42 SE) |
| `fortmagma` | 71.78 s | 26.2 % | 18.9 % (7/37) | 37 | -1.01 SE | 16.2 % (-1.38 SE) |
| `lighthouse` | 65.77 s | 28.8 % | 36.8 % (14/38) | 38 | +1.09 SE | 28.9 % (+0.02 SE) |
| `gran_paradiso_island` | 172.38 s | 34.7 % | 38.5 % (15/39) | 39 | +0.49 SE | 28.2 % (-0.86 SE) |
| `scotland` | 100.73 s | 38.2 % | 34.2 % (13/38) | 38 | -0.51 SE | 34.2 % (-0.51 SE) |

12 races, **889 frames scored by eye**, 23 unscorable excluded. **r = 0.899** across emitter shares
spanning 3.3-38.2 %, and pooled **15.1 % observed vs 14.8 % predicted** (134/889, z = +0.22).

*The two rows that needed more than the headline.* hacienda first read 10.3 % on 39 frames
(-2.20 SE). Rather than leave it, 96 more frames were scored at a quarter-step offset; the combined
133 frames give 22.6 % (-0.82 SE), so the first pass was sampling noise, not a defect. That is also
the honest warning about this method: at n=39 a single race's estimate is worth +/-7 %.
ravenbridge_mansion is the one row still outside 2 SE as scored (+2.53). Five of its 13 positives are
borderline calls (long yellow streaks, and an orange boost flame carrying distinct specks); scoring
every borderline call NEGATIVE puts it at 11.1 % against 9.4 % predicted, i.e. +0.51 SE. Under that
conservative reading **no race deviates by even 1.6 SE** (worst: cornfield_crossing -1.57).

*What this does and does not establish.* It establishes that the scored quantity tracks what is drawn
in the pixels, per race, across a twelvefold range of prevalence. It does NOT establish per-frame
temporal alignment: prevalence agreement is an aggregate over each race. The 28 borderline calls
(22 scored positive, 6 negative) are the method's soft spot, and the table's last column prices them.
The scorer was the same person who built the instrument, which is why the shuffle-and-opaque-id step
matters and why the sensitivity column is published rather than a single number.

**Transition-level blind test (the reviewer's PREFERRED protocol, PR #106 round 4).** Prevalence
agreement is an aggregate: a signal that was shifted or scrambled in time could pass it with the same
duty cycle. This is the test that cannot be passed that way. It runs on a fresh TRACED PROBE render of
scotland on the shipped build (`AGENTICVBENCH_SKIDTRACE=1`, 2153 hero frames, 266 s); the shipped
media carries no trace, and no shipped artefact is affected by the probe.

*Aligning the trace to the video.* `StkTime::getMonoTimeMs()` counts from STK's own start, so there is
no absolute clock to join on. But the trace times ARE wall-clock and x11grab captures at a constant
wall-clock rate, so `video_time = trace_time + offset` with a SINGLE unknown. The offset was found by
cross-correlating a crude yellow-at-the-wheels pixel proxy against the telemetry square wave over
0-40 s: a single sharp peak at **23.40 s (r = 0.700)**, neighbours 0.697 / 0.682 / 0.667, and the
worst offsets at r = -0.117. A signal unrelated to the pixels produces no such peak at any offset, so
the peak is itself evidence.

*The blind test.* 24 strips of 8 panels each, spaced 0.133 s (two video frames): 14 strips spanning a
telemetry transition with the change placed at a RANDOM panel, mixed with 10 control strips lying
entirely inside a steady interval. All shuffled, opaque ids, labelled before the key was opened.

| | result |
| --- | --- |
| transitions labelled with the correct DIRECTION (onset vs offset) | **14 / 14** |
| timing error vs telemetry | every one within **+/-1 panel (133 ms)**; median -133 ms, mean -57 ms |
| controls correctly reported as "no change", right polarity | **8 / 9** |
| excluded | 1 control strip that fell on black frames |

The median -133 ms is a residual offset error, not drift: the correlation grid was 0.2 s and 23.2 s
scored almost as well as 23.4 s, so the true offset sits between them.

*The one control I got wrong, and what it turned out to mean.* On S00 the telemetry says the emitter
is ON throughout, but panels 6-8 show the blue boost flame and no spray. The trace explains the
setup: at that instant the state flips `SKID_ACCUMULATE_RIGHT` -> `SKID_SHOW_GFX_RIGHT` and
`bonus` drops 3.0 -> 0.0 (the boost fires), while the rate stays 2000 because
`skidding.cpp`'s raise-branch tests `bonus_time > 0 || level == 1 || level == 2` and level is still 1,
so the SHOW_GFX zeroing branch is never reached. That suggested the bonus phase might be
systematically dark, which would mean the key overcounts -- about 25 %% of emitter-ON frames are in
SHOW_GFX. Measured against the video it is NOT systematic:

| telemetry | samples with yellow at the wheels |
| --- | --- |
| ON, still drifting (`ACCUMULATE`) | 91.7 %% (200/218) |
| ON, bonus firing (`SHOW_GFX`) | **93.4 %% (113/121)** |
| ON, all states | 92.0 %% (333/362) |
| OFF | 17.2 %% (145/841) -- the crude proxy's false-positive floor (boost flames, spin-out stars) |

So S00 is an individual frame-window, not a state-dependent blindness, and the suspicion it raised is
falsified rather than left hanging. Sensitivity of the emitter signal for on-screen yellow is 92 %%;
the 17 %% OFF rate is the proxy's own noise, which is the same limitation that makes pixel counting
unusable as an instrument in the first place.

*Honest limits.* The offset came from the pixel proxy, so the TIMING comparison is not fully
independent of pixels; the direction result (14/14) does not depend on the offset at all, and the
controls tolerate it. One race, one observer, and the observer built the instrument.

**The general lesson.** A derived TOTAL cannot show you that it was silently reset, so each wrong
reading invited a new mechanism to explain it. Log the raw per-frame facts first; it found this in
one run after three wrong diagnoses.

The `skidep` episode lines are retained, and the episode sum still equals the skid-state total
exactly (107 episodes, 64.83 s, on the earlier hacienda render), which is what makes the two
quantities comparable rather than independent guesses.

## Rendering path

Xvfb + `LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe` (swrast present on this node),
captured with ffmpeg `x11grab` (module ffmpeg/4.2.2 has it). Software GL runs well below
realtime, so wall-clock capture yields a long slow-motion video — which suits a 10 min+
task and makes kart identity easier to track, but the HUD must be cropped out.

## Task shape

Question: for the camera-followed **hero kart**, per race, reconstruct the two off-HUD scored
quantities `{items_collected, skid_time}` (spinouts = bananas + explosions, reported but UNSCORED; positions /
nitro / the banana-vs-bomb split are exported for context but not scored — see the task SPEC).
Deterministic scorer: exact-count (`clamp(tau,0,1) · within-30%-accuracy`) over the 12 races, so a
single-frame glance cannot recover it and accurate counting/timing requires watching each race.
