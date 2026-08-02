# Runway Operations Ledger

You are given two files covering the same real stretch of time at a real airport's
dual-runway complex, recorded from a camera near the runways:

- `/workspace/materials/runway.mp4` — silent video (no audio track).
- `/workspace/materials/tower.mp3` — the tower radio audio for the same period.

The two files are **not time-aligned** — they do not share a start time or a clock, and
no metadata anywhere tells you the offset between them. You have to work it out from
their content: match the sequence and spacing of the operations you can see against the
sequence and spacing of the clearances you can hear.

Two rectangular regions of the frame are blanked to black for the whole video. Nothing
you need is inside them; do not spend time on them.

The footage is at night, and the camera is a **moving PTZ camera operated by a person**:
it pans and zooms to follow individual aircraft, and it also wanders off to look at the
city between aircraft. It does not sit still on the runway, and it does not catch every
aircraft that uses it.

Reconstruct the ledger of the runway operations in the video — every aircraft that
either **lands** (main gear touches down) or **takes off** (lifts off during the
departure roll).

**The ledger covers the whole recording.** The video runs over two and a half hours and
the traffic is steady throughout: there are dozens of operations, spread from the first
minutes to the last. A ledger built from the opening stretch and then declared finished
is not a ledger — plan your time so that every part of the recording gets looked at.

For each operation, report:

- `video_time` — the timestamp **in the video file's own timeline** (`hh:mm:ss` from the
  start of `runway.mp4`): for a landing, the touchdown; for a takeoff, the liftoff.
- `operation` — exactly one of: `landing`, `takeoff`.
- `aircraft_type` — the aircraft family, from this closed vocabulary only (pick the
  closest match; do not invent new labels):
  `A220`, `A320-family`, `A330`, `A340`, `A350`, `A380`, `B737-family`, `B747`,
  `B757`, `B767`, `B777`, `B787`, `regional-jet`, `other`.
- `callsign` — the ICAO callsign (airline 3-letter code + flight number, e.g. `SWA1234`)
  as spoken by the tower controller in that aircraft's clearance ("cleared to land" for
  a landing, "cleared for takeoff" for a takeoff). Controllers speak the airline's
  radiotelephony name, not the ICAO code — "Southwest twelve thirty-four" is `SWA1234`.
  Use this table to convert:

  | telephony (spoken) | ICAO code | telephony (spoken) | ICAO code |
  |---|---|---|---|
  | Southwest | SWA | American | AAL |
  | Delta | DAL | United | UAL |
  | Alaska | ASA | JetBlue | JBU |
  | Spirit | NKS | Frontier | FFT |
  | Allegiant | AAY | Sun Country | SCX |
  | SkyWest | SKW | Horizon Air | QXE |
  | Envoy | ENY | Republic | RPA |
  | Mesa | ASH | Endeavor | EDV |
  | Jet Set | JSX | Breeze | MXY |
  | Rouge | ROU | WestJet | WJA |
  | Air Canada | ACA | Copa | CMP |
  | Aeromexico | AMX | Volaris | VOI |
  | Speedbird | BAW | KLM | KLM |
  | Lufthansa | DLH | Air France | AFR |
  | FedEx | FDX | UPS | UPS |

  A carrier not in this table: transcribe the ICAO code as best you can determine it
  from what is said, and do not guess a carrier that was not actually spoken. An
  aircraft with no airline callsign (business jets, light aircraft) is addressed by its
  registration — report that as spoken, e.g. `N123AB`.

## What to submit

Write `/workspace/output/solution.json` in exactly this shape:

```json
{
  "operations": [
    {"video_time": "00:14:32", "operation": "landing", "aircraft_type": "B737-family", "callsign": "SWA1428"},
    {"video_time": "00:19:05", "operation": "takeoff", "aircraft_type": "A320-family", "callsign": "AAY518"}
  ]
}
```

- One entry per runway operation, in any order.
- `video_time` tolerance: within about 45 seconds of the real moment.
- **Write this file early and keep overwriting it.** As soon as you have even one
  complete operation, write `solution.json` with what you have, and rewrite it each time
  you complete another. There is a time limit; whatever is in the file when the session
  ends is what gets graded, so never leave your findings only in notes or in
  intermediate files.
- **Budget your time as though the session could end at any moment.** The expensive
  mistake here is to process the whole video, then the whole audio, then pair the two at
  the end: that ordering produces nothing gradeable until the very last step, and it
  loses everything if you run out of time. Working through the recording in
  chronological stretches — see a stretch, hear the same stretch, pair it, append what
  you confirmed — keeps a usable answer on disk the whole way through.
- An entry with a missing or empty `callsign` counts against you exactly like a wrong
  one. If you cannot name an aircraft, leave that operation out entirely rather than
  submitting it with the field blank.

## Rules

- Stay inside this working directory. Do not read, write, or search outside it.
- No internet access is available and none is needed. Do not rely on memory or general
  knowledge of any specific airport, carrier schedule, or route network — every entry
  must be justified by something you directly observed in `runway.mp4` or heard in
  `tower.mp3`. Do not guess.
- Count only completed runway operations: landings (touchdown) and takeoffs (liftoff).
  Do not report go-arounds, rejected takeoffs, aircraft only taxiing or holding, or
  aircraft that merely cross a runway.
- Tools in the image include `ffmpeg`/`ffprobe` for seeking and sampling the video and
  for cutting audio segments, and a local speech-to-text model at `$WHISPER_MODEL_DIR`
  (load it with `faster_whisper.WhisperModel` in Python) for transcribing `tower.mp3` —
  there is no other way to recover the audio content.
- **There is no network, so `pip install` will not work.** Already installed and
  sufficient for everything here: `numpy`, `av` (PyAV — decodes video frames directly
  into numpy arrays), and `faster_whisper`. `PIL`, `cv2` and `scipy` are not installed;
  do not plan around them.
