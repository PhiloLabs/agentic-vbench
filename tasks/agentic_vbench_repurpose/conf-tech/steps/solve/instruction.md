You're cutting an insight reel for **Big Think Tech**, a YouTube channel that publishes 60-90 second highlights from major developer keynotes. The audience here is senior engineers, tech leads, and engineering managers who follow the JavaScript ecosystem but didn't get to attend the conference live. We're commissioning a **75-second insight reel** from the React Conf 2025 Keynote, the year's biggest React announcement event, delivered on stage by five Meta-affiliated React-team speakers in sequence.

Picture a viewer scrolling YouTube on a laptop with sound off, which is typical for this audience. They should walk away knowing two things: **React Compiler 1.0 has shipped**, and **the React Foundation has been formed**. Those are the two announcements this keynote exists to deliver, and a reel that lands one without the other has cut the news in half. Beyond those anchors, at least one supporting story should land too. The Activity component, ViewTransition animations, the six-billion-download stat, the 2.5x performance number, something concrete that gives a viewer a reason to believe the headlines.

Stay in the speakers' own voices throughout. No narrator. Every word a viewer hears should be the people who were on that stage. Burn in English captions across every word of speech so the muted-scroll viewer still gets the argument, in sync with the speaker and legible against the dark stage footage. It should feel like the keynote compressed: speakers on camera, the slides they're pointing at when the slide carries the number, the room when the room cheers. Not a repurposed cut dressed around two clips.

Open on something that earns the next fifteen seconds, a striking line in a speaker's own voice, not a "hi I'm" intro. Close on a brief title card with the keynote name and conference, a second or two, not a dragged-out pad. Deliver horizontal 1280x720, MP4 with stereo audio.

## Deliverables

- The source video is at `/workspace/materials/source.mp4`.
- Write your final repurposed cut to **`/workspace/output/repurpose.mp4`** (this exact path and filename).
- The container has `ffmpeg`, `python3`, and a pre-cached Whisper "base" model. Internet is available for `pip install`.
- You have ~30 minutes for the agent step. Aim for a watchable output rather than the perfect cut.
