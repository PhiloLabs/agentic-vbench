# Calibration — dualrunway-ops-ledger

Deterministic F1 scorer (`steps/solve/tests/judge.py`). A task clears the bar when
**every real agent scores below 0.10** and a real attempt takes **more than 50
tool-call turns**. Oracle must be 1.0 and an empty attempt near 0. All five
anti-shortcut ablations must score <= 0.15.

All agent rows measured 2026-08-02 on a 40-core Linux host, same image, same media,
same instruction, same shipped resource settings (8 cpus / 8 GB / 7200 s). Every run
ended on its own; none was cut off by the cap.

| run | score | rollout (tool-call turns) |
|---|---|---|
| oracle | **1.0** | — |
| empty / null | **0.0** | — |
| Claude Code CLI (Opus 5) | **0.0** | 93 |
| Antigravity (Gemini 3.5 Flash) | **0.0** | 260 |
| Antigravity (Gemini 3.1 Pro) | **0.0** | 101 |
| Codex CLI (GPT 5.6 Sol) | **0.0741** | 29 |

Highest of the four is **0.0741** — 2 of 49 operations fully reconstructed, from five
submitted. The other three scored zero: Opus 5 submitted 33 operations and matched none,
Gemini 3.5 Flash 21 and matched none, Gemini 3.1 Pro 9 and matched none. Getting an
operation *approximately* right is common; getting callsign, family, landing-vs-takeoff
and a 45 s window all right at once is not.

Codex is the outlier on rollout length: it wraps up after ~22 minutes and 29 turns while
the others run 70-80 minutes. That is an agent trait, not a task ceiling — the same task
and prompt draw 260 turns out of Gemini 3.5 Flash.

## Anti-shortcut ablations

All five measured 2026-08-01, Opus 5, same image, 5400 s each.

| ablation | score | expected |
|---|---|---|
| single_frame | **0.0** | <= 0.15 |
| video_only | **0.0** | <= 0.15 |
| audio_only | **0.0** | <= 0.15 |
| no_media | **0.0** | <= 0.15 |
| frame_dump_no_tools | **0.0** | <= 0.15 |

`audio_only` produced no `solution.json` at all — with no video there is no timeline to
anchor an entry to, so the agent had nothing to write. That is the intended failure.

Raw transcripts go in `rollouts/` — one file per agent, so a reviewer can confirm each
score was earned honestly and count the tool-call turns.

Status: **calibrated.** Oracle, null, all five ablations and all three required agents
(Antigravity on both models the family names, Codex CLI, Claude Code CLI) are real
measurements against the shipped scorer, prompt and resource settings.

## Scorer behaviour already measured (2026-08-01, local, shipped judge.py)

These are mechanical probes of the scorer, not agent runs. They are here because they
are what set the tolerance and what justify the two weak fields.

| probe | reward |
|---|---|
| oracle (mirrors GROUND_TRUTH) | 1.0 |
| empty `operations` list | 0.0 |
| fabricated callsigns, everything else correct | 0.0 |
| correct callsigns/types/operations, times guessed | 0.0 |
| everything correct but a uniform 90 s time offset | 0.0 |
| every real callsign + operation, no usable times or types (210 rows) | 0.0 |
| only the first 10 operations, all correct | 0.34 |
| everything correct but a uniform 40 s time offset (inside TOL) | 1.0 |
| `aircraft_type` = "B737-family" for all, everything else correct | 0.59 |
| `operation` = "landing" for all, everything else correct | 0.84 |

The last two are the traffic mix (59% B737, 84% arrivals), not a scorer defect: both
presuppose the callsigns and times are already right. The 90 s-offset probe is the
important one — it confirms that failing to recover the audio/video offset zeroes an
otherwise perfect answer, so the cross-modal alignment really is load-bearing.

## How the resource settings were chosen

`cpus`, `memory_mb` and `timeout_sec` in `task.toml` were set by measurement, not by
copying the family default, and the reasoning is recorded in the comments there. In
short: 8 cpus because 156 min of local ASR does not fit in the 2-4 the visual-only tasks
in this family use — at 4 cpus a strong agent never reaches 50 tool-call turns for lack
of compute rather than lack of depth. 7200 s because at 3600 s no agent produces a
`solution.json` at all (they are still building type-ID sheets when the cap lands, which
passes the bar for the wrong reason) and at 10800 s the budget starts rewarding
persistence over correspondence.

## Caveat on every agent number measured with this harness

The trial container has network, because the agent harness (`claude` CLI) runs *inside*
it and has to reach the API. The real Harbor trial runs `allow_internet=false`. Web
lookup is blocked explicitly (`--disallowedTools WebFetch,WebSearch`) and the trajectory
is scanned for `curl`/`wget`, so a schedule lookup would be visible — but `pip install`
still works here and would not work in the real trial. The first Opus run reached for
`pip install pillow` about 45 minutes in.

That specific reach was unnecessary: the image already ships **numpy 2.5.1** and
**PyAV 12.3.0**, which together decode frames straight into arrays. PIL, cv2 and scipy
are absent. So the offline environment can do frame analysis — the agent simply had no
way to know that, and spent turns finding out.

`instruction.md` now says so explicitly (no network, and what is already installed).
Any agent number measured *before* that edit was produced under a slightly harsher
prompt than the shipped task presents.

## Naive-pipeline ceiling (2026-08-01) — the strongest difficulty evidence so far

Not an agent run: a mechanical probe of whether the task can be solved without
per-aircraft cross-modal reasoning. The naive strategy is given every advantage:

- the **video side is assumed perfect** — it uses ground truth's own times, operations
  and aircraft types, i.e. an oracle that spots every operation and identifies every
  airframe;
- the **airline prefix is handed over for free** — only the flight-number digits have to
  be recovered;
- callsign is then taken from **the nearest "cleared to land / cleared for takeoff"
  in the 400 s before the operation**, parsed out of the real medium.en transcript.

**Result: reward 0.0816, 4 of 49 correct.**

For contrast, the correct flight number appears somewhere in that same 400 s window for
**39 of 49** operations. The information is present in the audio; naive pairing extracts
almost none of it. A pipeline with an oracle for the entire video channel still lands
below the 0.10 gate.

This is the quantitative form of the jitter argument: clearance→operation lead has
σ = 97 s while operations are 119 s apart, so "take the most recent clearance" attaches
the wrong aircraft most of the time. Anything scoring well above this had to do real
per-aircraft work.

## Why TOL is 45 s and not 8 s

The first draft used 8 s and it was not supportable. Two measurements forced it open:

1. **ADS-B report sparsity.** Median gap between an aircraft's last airborne state
   vector and its first on-ground one is 22 s in this capture, so machine truth can
   only ever place the transition to about ±11 s.
2. **The visible event leads the ADS-B time.** Five operations were hand-pinned against
   contact sheets (frames every 5 s, masks applied). In all five the aircraft was
   already rolling — or already airborne — 10-35 s before the ADS-B-derived time. Two
   of them (SWA2177, AAL2785) were already on the ground in the very first frame of a
   window starting 30 s early, so the true touchdown was earlier still.

Stored times are bias-corrected by 12 s; 45 s covers the residual scatter with margin.

## Ground-truth attrition, and why it is deliberate

192 debounced ADS-B operations → 76 with a confirmed airframe join → 51 observable →
**49 shipped** (two more fell to the audibility check below).
The filter is "the camera can be shown to have tracked this airframe": a contiguous
on-screen tracking segment of ≥ 15 s, with the ADS-B transition within 30 s of it.

What it caught:

- A Beech 200 King Air whose ADS-B landing time falls on a frame where the camera is
  pointed at the Luxor pyramid. Nothing to see, nothing to score.
- Five "takeoffs" (SWA2179, SWA2230, SWA2256, SWA287, FFT1896) whose only on-screen
  tracking segment was that same airframe's *landing*, 19-37 minutes earlier. The
  camera never watched them leave.
- A Cessna 172 that survives as pixels but not as evidence: at the sampled frames it is
  three navigation lights with no fuselage, no wing, no tail. No standard of expert
  identification recovers a type from that.

The 161 excluded-but-real operations are not thrown away — they go into the scorer's
`DONT_CARE` list so an agent that correctly reports one is excused rather than punished.

## Judgement call worth flagging to a reviewer

The identifiability bar is "**could the strongest human expert, watching the tracked
sequence, get the aircraft family right better than half the time?**" — not "is it
unambiguous". An earlier pass used the stricter bar and was about to drop a JSX ERJ-145
scoring 0.56 on an edge-density metric; looking at the actual frame, the tail, the
tail marking and the slim twin-jet proportions are all there. It was kept. Only the
Cessna, with no shape information whatsoever, failed.

This bar matters because the agent sees *motion*, not one still: an expert watching the
PTZ follow an aircraft has far more to work with than any single frame suggests.

## One prompt defect the calibration caught

The first sweep found two agents declaring victory after covering only the opening
minutes: Codex submitted 2 operations and stopped at 22 min, Gemini 3.1 Pro submitted 7
whose timestamps all fell inside the first 31 minutes of a 154-minute recording. Codex's
own opening line was "I'll work in short chronological batches and update solution.json
immediately" — it was following the prompt exactly.

The prompt was at fault: it said to write incrementally and to omit anything not fully
known, but never stated that the ledger spans the whole recording. "Do a few, write
them, finish" was a legitimate reading. `instruction.md` now says the coverage
expectation out loud, without leaking the ground-truth count.

Effect, same model either side of the change: Codex 2 submitted / 0 correct → 5
submitted / 2 correct; Gemini 3.5 Flash 0 submitted → 21; Opus 5 1 submitted → 33. All
numbers in the table above are from after the fix.

## Second annotation pass on `aircraft_type` — done, zero disagreement

The first pass read the type off the camera's on-screen tracking panel. The second pass
uses a source that never touches the video: the OpenSky aircraft database, joined by
registration, `typecode` → the closed family vocabulary.

All 46 distinct registrations behind the 49 rows resolve in the database, and the two
passes agree on **46 of 46**, with no disagreements.

Seven rows needed a second look before they counted as agreeing: their typecode is
`B38M` (one is blank with model `737-8`), which a naive `B73*` prefix test misses. They
are 737 MAX 8s and belong to `B737-family` exactly as the panel said — the mismatch was
in the prefix table, not in the data. Recording that because the same trap will catch
anyone re-deriving these families from typecodes.

## Callsign audibility — the gate that removed the last two rows

Every ground-truth callsign has to be *hearable*, or the row is unobservable. A full
medium.en pass over the shipped `tower.mp3` was checked row by row:

| evidence | rows |
|---|---|
| flight number + recognisable carrier word | 40 |
| flight number spoken in the right place, carrier word mangled by ASR | 9 |
| never spoken at all → **dropped** | 2 |

The two dropped are SWA2256 and SWA976. SWA976 appears nowhere in the transcript at all;
SWA2256's only occurrence is 54 minutes away in an unrelated exchange. Both moved to
`DONT_CARE`.

**The first version of this check was wrong and would have gutted the task.** It demanded
the telephony name literally adjacent to the digits and reported 51% coverage — which
looked like grounds to abandon the ledger. It was measuring ASR quality, not audibility.
The model writes "Soto 2177" for Southwest 2177, "Cessna 4226" for Southwest 4226,
"Legion 28" for Allegiant 28, "TOS 369" for Southwest 369, and drops the carrier word
entirely in "406, Las Vegas Tower, wind 200 at 6, runway 26L, cleared to land". Keying on
the digits within a time window, with the carrier word as corroboration rather than a
requirement, gives 96%. Worth knowing before trusting any callsign-recall number from
this recording: the digits survive ASR, the airline names frequently do not.

That asymmetry is also why the instruction ships a telephony→ICAO table. The agent has to
map a spoken carrier name it may only half-hear onto a three-letter code.

## Environment fixes found by actually building the image (2026-07-30)

- `faster-whisper==1.0.3` imports `requests` in `faster_whisper.utils`, but the wheel
  does not declare it. On `python:3.12-slim` the image **fails to build** at the
  model-prefetch step. Fixed in `environment/Dockerfile` by installing `requests`
  explicitly. This was a real defect in the shipped Dockerfile, not a local quirk.
- Verified inside the built image: ffmpeg 7.1.5 present, and the baked `medium.en`
  model loads with `local_files_only=True`, so the audio path genuinely works with no
  network — which is what `allow_internet=false` requires.
- `small.en` garbles ATC callsigns badly on real recordings; `medium.en` recovers
  repeated callsigns cleanly enough to be workable. Keep the larger model.

## A second image defect, found the same way (2026-08-01, Linux, 40-core node)

`WHISPER_MODEL_DIR` did not point at a loadable model. `download_root=/opt/whisper-model`
leaves a HuggingFace cache tree — `models--Systran--faster-whisper-medium.en/snapshots/
<sha>/model.bin` — so the directory the variable names contains no `model.bin` at all, and

    WhisperModel(os.environ["WHISPER_MODEL_DIR"])

dies with `RuntimeError: Unable to open file 'model.bin'`. That call is **exactly what
instruction.md tells the agent to do**, so every agent would have hit it, and the audio
channel — the only source of callsigns — would have looked unreachable through the
documented path. The task would have measured "can you debug our Dockerfile", and the
audio_only ablation would have passed for the wrong reason.

Fixed in `environment/Dockerfile`: prefetch into a scratch cache, flatten the snapshot
into `/opt/whisper-model` with `cp -L` (the entries are symlinks into `blobs/`), and
assert the flattened directory loads during the build so this cannot regress silently.

Both image defects found so far — the undeclared `requests` import and this one — were
invisible on inspection and only appeared on a real build-and-run. Do not sign off on an
environment that has not been executed.
