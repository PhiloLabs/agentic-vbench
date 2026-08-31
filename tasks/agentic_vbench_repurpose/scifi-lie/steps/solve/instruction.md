You are a video editor cutting for **DUST**, the sci-fi short-film channel on YouTube. We've licensed a 21-minute short called *The Greatest Lie* and we want to release a 60-second repurpose as the lead-in trailer on our main YouTube channel. The audience is the channel's regular viewers: people who scroll a wall of sci-fi shorts looking for something with weight, and who'll give a one-minute repurpose exactly one minute to convince them to click through to the full film.

The piece needs to feel like the source feels: quietly devastating, not loud. This is a film about a mother in a literacy-banned future who dies for a book she wrote for her daughter, and it earns its emotion the way grown-up sci-fi does, through restraint, not exposition. I want a viewer who's never heard of this film to leave the repurposed cut understanding that something was lost and something was kept, and to want to know what was on the page the daughter is reading at the end. Don't summarize the plot beat-by-beat. Tell the story the way a trailer cut by someone who loved this film would tell it.

A single narrator carries the repurposed cut end-to-end. One voice, warm but careful, the kind of voice that knows what's coming and doesn't oversell it. Where the film is tender, let the voice be tender. Where the film breaks, let the voice break with it. Don't open on setup; open on a moment that makes a stranger want to lean in, then earn the ending.

End on a brief title-and-channel card, a second or two, not a multi-second pad, leaving the viewer with the title in their head and the channel they came from.

Deliver as 1920×1080 H.264 MP4 at 24 fps with stereo audio, exactly 60 seconds long.

## Deliverables

- The source video is at `/workspace/materials/source.mp4`.
- Write your final repurposed cut to **`/workspace/output/repurpose.mp4`** (this exact path and filename).
- The container has `ffmpeg`, `python3`, and a pre-cached Whisper "base" model. Internet is available for `pip install`.
- You have ~30 minutes for the agent step. Aim for a watchable output rather than the perfect cut.
