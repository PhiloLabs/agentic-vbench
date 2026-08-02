task: agentic_vbench_understanding/dualrunway-ops-ledger

cognitive_level: understanding
# Deciding which aircraft seen on screen corresponds to which tower clearance heard on
# the radio, with no shared clock between the two files, requires comparing and
# ordering events across two independent evidence streams -- not locating them.

modalities_required:
  video: the operation moment (video_time), whether it was a landing or a takeoff, and
    the aircraft family can only be read from the picture. The tower never states the
    aircraft type, and the audio carries no video timeline.
  audio: callsign exists only on the tower frequency. The camera's own on-screen
    tracking panel would leak callsign AND type, so it is masked to black for the
    entire video; nothing else on screen names an aircraft.
  audio_content_verified: >
    Confirmed by ASR over the shipped tower.mp3 (2026-08-01): it is a live controller
    feed carrying landing and takeoff clearances with runway assignments, and
    ground-truth callsigns are genuinely spoken -- e.g. "cleared to land, Southwest
    twenty-one seventy-seven" 194 s before SWA2177's stored touchdown, and "United
    nineteen ninety-five, runway two-six left, cleared to land". The feed is not
    tower-only: approach control and sightseeing-helicopter traffic share it, which
    adds realistic clutter an agent has to filter.
  location_is_not_secret: >
    The audio names local landmarks by voice, so the airport is identifiable from the
    material itself. Obscurity is therefore NOT a defense here -- allow_internet=false
    is the only thing preventing a schedule lookup, and it has to stay false.

question: >
  Reconstruct the ledger of runway operations in the video: for each, the video-timeline
  moment, landing vs takeoff, the aircraft family, and the ICAO callsign spoken in that
  aircraft's clearance.
output_schema: >
  {"operations": [{"video_time": "hh:mm:ss", "operation": "landing"|"takeoff",
  "aircraft_type": <14-way closed vocab>, "callsign": "ICAO3+flightnum"}, ...]},
  video_time tolerance 45 s (TOL in judge.py -- measured, see below).

evidence:
  - "t=<operation, video>: the aircraft on the runway -> video_time + landing/takeoff + silhouette -> aircraft_type"
  - "t=<clearance, audio, offset unknown>: tower clearance readback -> callsign, and its position in the sequence of clearances"
  - Recovering the unknown offset needs the ORDER and SPACING of operations seen to be
    matched against the order and spacing of clearances heard. A single lookup at one
    timestamp does not generalise to the rest of the ledger.
  why_a_constant_shift_fails: >
    Measured on this recording, and the single strongest argument that the task cannot be
    short-circuited. The gap between an aircraft's clearance being spoken and its
    operation happening has median 197 s but a standard deviation of 97 s, spread from
    2 s to 452 s. Ground-truth operations are only 119 s apart at the median. The jitter
    is therefore the same order as the spacing: an agent that lines up the clearance
    sequence and applies one constant shift will land routinely on the neighbouring
    aircraft, not the right one. Every row has to be confirmed against the picture
    individually. Solving the offset once is necessary but nowhere near sufficient.

ground_truth:
  source: >
    A live OpenSky state-vector capture was run against the runway complex for the whole
    recording (1864 successful polls, 7 errors, ~5 s cadence). Identity comes from an
    icao24 -> registration join against the camera's own on-screen tracking panel (OCR'd
    from the raw, unmasked capture), NEVER from "who was landing around then" -- an
    earlier draft matched on time alone and paired a Southwest flight with JetBlue's
    airframe. operation comes from debounced on_ground transitions (4 consecutive
    samples) in that same capture; aircraft_type from the panel's type string collapsed
    to the closed family vocabulary.
  observability_filter: >
    192 debounced ADS-B operations -> 76 with a confirmed panel/airframe join -> 51
    observable in the picture -> 49 shipped. An event is only ground truth if the camera
    can be SHOWN to have tracked it: a contiguous on-screen tracking segment of >= 15 s
    for that airframe, with the ADS-B transition within 30 s of it. This is load-bearing,
    not cosmetic. Spot checks found a Beech 200 whose ADS-B landing time lands on a frame
    where the camera is pointed at the Luxor pyramid, and five "takeoffs" whose only
    tracking segment was actually the same airframe's landing 20-35 minutes earlier. Both
    classes are real operations that the video cannot support, and both are excluded.
  audibility_filter: >
    The last two rows fell to a separate gate: is the callsign actually SPOKEN? A full
    medium.en pass over tower.mp3 was checked row by row. 40 of 51 have the flight number
    together with a recognisable carrier word; 9 more have the number spoken in the right
    place with the carrier word mangled by ASR; 2 -- SWA2256 and SWA976 -- never appear at
    all (SWA976 occurs nowhere in the transcript, and SWA2256 only 54 minutes away in an
    unrelated exchange). Those two are unobservable and were dropped.
    Method note that cost a full wrong answer first time round: an initial check demanded
    the telephony name literally adjacent to the digits and reported 51% coverage. That
    was measuring ASR quality, not audibility -- the model writes "Soto 2177" for
    Southwest 2177, "Cessna 4226" for Southwest 4226, "Legion 28" for Allegiant 28. Keying
    on the digits inside a time window and treating the carrier word as corroboration
    gives 96%.
  tier: machine-truth (callsign, operation, aircraft identity, time) + human-verified
    (the observability filter and the five hand-pinned timing checks).
  second_pass: >
    aircraft_type has two independent annotations that agree on 46 of 46 registrations
    with no disagreements. Pass 1 reads the type off the camera's on-screen tracking
    panel; pass 2 never touches the video at all -- registration -> OpenSky aircraft
    database -> typecode -> family. Seven rows only agree once you know `B38M` (and one
    blank typecode with model 737-8) is a 737 MAX 8; a naive B73* prefix test drops them.
  verification: >
    Five operations spread across the recording were hand-pinned frame by frame against
    contact sheets to check that the stored time really does land on the visible event.
    It did not: the visible touchdown/liftoff LEADS the raw ADS-B-derived time by
    10-35 s. Stored times are therefore bias-corrected by 12 s and TOL is set to 45 s
    (see below). This check is what set the tolerance; it was not chosen by taste.

scorer:
  metric: >
    F1 over operations. A TP requires operation, aircraft_type and callsign to match
    exactly and video_time within 45 s. Pure-stdlib (tests/judge.py).
  dont_care_set: >
    161 real operations that the camera was not verifiably pointed at, or whose callsign
    is never spoken, are held in a DONT_CARE list. A prediction matching one is dropped
    from the precision denominator rather than counted as a false positive. Without this,
    F1 against a deliberately conservative ledger would punish an agent for correctly
    reporting an operation our ground truth cannot see.
  oracle_reward: 1.0 (measured 2026-08-01, locally against the shipped judge.py)
  null_reward: 0.0 (measured; empty operations list)
  weak_fields: >
    Measured, and kept anyway: conditional on every other field being right, answering
    "B737-family" for all 49 scores 0.59 and "landing" for all 49 scores 0.84 -- the
    traffic really is 59% B737 and 84% arrivals. These are not shortcuts, because both
    numbers presuppose the callsigns and times are already correct, which is the whole
    difficulty. They act as a correctness tax rather than a discriminator. A `runway`
    field was cut outright for failing this same test far worse.

difficulty:
  strong_agent_reward: TODO (measure; must be < 0.10)
  tool_call_turns: TODO (measure; must be > 50)
  agent_model: TODO
  prior_finding: >
    A daytime version of this task at a different airport was measured with headless
    Claude Opus and came out TOO EASY -- 28 of 31 callsigns correct. That run is why
    this recording is night footage from a hand-operated PTZ camera: the aircraft is a
    silhouette against terminal lights rather than a clearly-lit airframe, and the
    camera does not stay on the runway.

anti_shortcut:
  single_frame: TODO
  video_only: TODO (expected ~0: no path to callsign without audio)
  audio_only: TODO (expected 0 -- verified mechanically against the shipped scorer: a
    submission carrying every real callsign and operation but no usable times or types
    scores 0.0000. The daytime predecessor confirmed this behaviourally too, producing
    only 2 entries because video_time has no anchor without the video.)
  no_media: TODO (expected ~0: schema alone gives no usable prior)
  frame_dump_no_tools: TODO
  alignment_is_load_bearing: >
    Verified mechanically: a submission that is perfect except for a uniform 90 s time
    offset -- an agent that solved everything but never recovered the audio/video
    offset -- scores 0.0000.

input:
  url: >
    https://huggingface.co/datasets/xuanmiao-31/dualrunway-ops-ledger/resolve/main/runway.mp4
    https://huggingface.co/datasets/xuanmiao-31/dualrunway-ops-ledger/resolve/main/tower.mp3
    Self-hosted rather than pinned upstream: the media was cut, masked and stripped for
    this task and exists nowhere else. Both digests re-verified by streaming the public
    URLs back down after upload.
  sha256: >
    runway.mp4 fc873ab0777d823f7d1c4b5356df21eebca083f66803db4861b414d360111304
    tower.mp3  8501a0c8debd0ca7afe9723173493bd07e442a1bd28914dc5f68fec381f6c7bc
    (already in environment/Dockerfile; re-hash if the media is ever re-cut)
  length_min: 153.9 video (9235.0 s) / 156.2 audio (9371.1 s)
  size: 2.31 GB video, 35.8 MB audio
  resolution: 2096x1178, night, two overlay regions masked to black
  audio_offset: >
    Deliberate. runway.mp4 starts 105 s into the raw capture (the opening seconds show
    the recording window being set up); tower.mp3 starts at 0. The 105 s offset is the
    thing the agent has to recover, and it is not recorded in any file metadata.
  duration_leak_closed: >
    The first cut of the media handed that offset away for free. Both files ended at the
    same point in the raw capture, so duration(audio) - duration(video) was 104.1 s --
    two ffprobe calls and a subtraction, and the whole cross-modal alignment step is
    skipped. The video is now cut short at the tail as well: durations are 9235.0 s
    (video) and 9371.1 s (audio), a difference of 136.1 s that has no relation to the
    real 105 s offset. The latest ground-truth event sits at video_t 9171 s, comfortably
    inside the shortened video.
    Worth remembering as a class of bug: an offset hidden in the content is only hidden
    if it is not also implied by the container metadata.
  metadata_stripped: >
    Same class of leak, second instance. The audio track was carrying the capture's
    QuickTime tags through untouched -- `com.apple.quicktime.author=ReplayKitRecording`
    plus the qt brand -- which announces that both files came off one screen recording,
    exactly the construction detail the unknown offset is supposed to hide. Both files
    are now written with `-map_metadata -1`; all that survives is ffmpeg's own encoder
    string. Anything re-cut from the source has to repeat that, and has to be re-hashed:
    the digests above cover the stripped files.
    (One trap on the way: `-write_xing 0` on a VBR mp3 drops the header players use to
    compute duration, and ffprobe then reported 12473 s for a 9371 s file. Keep the Xing
    header.)
