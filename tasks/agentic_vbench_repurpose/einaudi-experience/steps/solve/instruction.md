# Concert preview, Ludovico Einaudi, "Experience" (live)

You're cutting a **75-second concert preview** of Ludovico Einaudi performing "Experience" live with his sextet, pulled from the full 6:23 recording in `input/film.mp4`. The cut runs as a **YouTube concert-preview pre-roll** on the artist's official channel, in **1280x720 horizontal**. Its job is simple. Get viewers to play the full recording.

The source gives you everything a teaser needs. A hush opens into the first solo-piano note. The texture thickens slowly. The famous main-theme drop hits at 3:38. A pinned-pedal climax lands around 5:30 to 5:45, and the piece falls into silence on its final chord. You've got 75 seconds to convince a stranger to sit through six and a half minutes. Show the gravity of the room. Show the warm spotlight on Einaudi alone at the Steinway. Show the cool-blue wash that takes over when the full ensemble surges in.

**The recording is the audio. No voice-over, no narration, no commentary on top.** The performance is what we're selling. No announcer, no spoken caption track, no music bed under voice-over. The piano, the strings, the accordion, the room. That's the soundtrack.

**Cuts have to respect the music.** A trailer that splices mid-phrase, mid-arpeggio, or mid-bow is unwatchable to anyone who'd buy a ticket to this show. Listen for the phrase boundaries: rests, the natural breath at the end of a passage, the tail of a sustained note. Cut between them, never across them. Mirror the piece's arc. Open in restraint, build, peak, end on resolution. Don't level-normalise it flat. The quiet moments are part of what makes the loud ones land.

Lean on the source's coverage. The wide on the ring-lit pod. The medium on Einaudi at the music stand. The close on hands during the fast passages. The close on his face during the sustains. At least one glimpse of the live audience, so we know this is a concert and not a studio cut. Show the room the listener is being invited into.

Deliverable: 75 s plus or minus 0.5 s, 1280x720, 24 or 25 fps, MP4/H.264, stereo AAC.

## Deliverables

- The source video is at `/workspace/materials/source.mp4`.
- Write your final repurposed cut to **`/workspace/output/repurpose.mp4`** (this exact path and filename).
- The container has `ffmpeg`, `python3`, and a pre-cached Whisper "base" model. Internet is available for `pip install`.
- You have ~30 minutes for the agent step. Aim for a watchable output rather than the perfect cut.
