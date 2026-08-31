# Brief — "This Is America" 75-second Reels repurposed cut

You're cutting a **75-second repurpose** of *This Is America* by **Childish Gambino**
(dir. Hiro Murai, 2018) for **Instagram Reels**. Deliverable is **vertical
1080×1920**, target **75 s** (acceptable window 73 – 77 s).

The audience is the Reels feed: people who know the video and people who've
never seen it. The repurposed cut has to land for both the cult fan and the cold
scroller. We want the feeling of the original — false peace, sudden violence,
hypnotic distraction, terror — at a quarter of the runtime. Not a "highlight
reel." A compressed repurpose that keeps the song's spine and the video's argument
intact.

The most important thing to internalize: **the song is the audio.** "This Is
America" is the artwork. Trim the song to fit your runtime, fade the ends
cleanly, and let the picture do the talking. Do not write or perform a
voice-over. Do not lay narration over the music. Do not replace the song with
score or stock music. The hook — *"This is America / Don't catch you slippin'
now"* — has to land, in full, on its original beat-drop, the way it does in
the source at 0:53. If the hook is missing or chopped mid-phrase, you've lost
the song.

Four moments from the source are **non-negotiable**: the repurposed cut has to include
all four, identifiably, with at least 0.7 s of screen time each. They are the
**Jim Crow pose and first shooting** of the hooded guitarist on the hook drop
at 0:52, the **Gwara Gwara schoolkid dance** with Glover front-and-center in
the uniformed dance line at 1:09, the **gospel choir massacre** with the
AK-47 at 1:56, and the **final dark-corridor sprint** close-up of Glover
running from the mob at 3:45. Beyond those four, pick at least two more
recognizable images from the source, for example the pale horse passing
through the background, the car-roof dance over the abandoned sedans, or the
silent finger-gun cigarette-light bridge.

Cut on the beat. The source is famously shot in Steadicam long takes. You
can't replicate that in 75 s, so you'll cut more than the source does, but
every cut should land on a beat or phrase boundary. Random cuts will feel
wrong against this song.

Reframe to vertical without cropping Glover's head out of frame whenever he's
on screen.

**Tech specs.** MP4, H.264 or HEVC, 1080×1920 vertical, ≥ 24 fps, AAC stereo at
44.1 or 48 kHz, ≥ 1 Mbps video bitrate.

## Deliverables

- The source video is at `/workspace/materials/source.mp4`.
- Write your final repurposed cut to **`/workspace/output/repurpose.mp4`** (this exact path and filename).
- The container has `ffmpeg`, `python3`, and a pre-cached Whisper "base" model. Internet is available for `pip install`.
- You have ~30 minutes for the agent step. Aim for a watchable output rather than the perfect cut.
