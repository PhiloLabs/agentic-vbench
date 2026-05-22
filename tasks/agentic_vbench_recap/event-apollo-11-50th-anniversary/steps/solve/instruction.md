You are a video editor I'm hiring on behalf of Space.com's 50th-anniversary playlist. We're cutting a four-minute commemorative piece on Apollo 11 that'll sit at the front of our anniversary feed and play on the kiosk at the Smithsonian's "One Giant Leap" exhibit. Our viewers come from everywhere, people who watched the broadcast live in 1969 and people born thirty years after. Both need to walk away feeling the weight of what happened, not learning about it for the first time.

What I care about most is that the three men are honored as individuals. Neil Armstrong commanded the mission and stepped off first. Buzz Aldrin piloted the Lunar Module and joined him on the surface. Michael Collins piloted the Command Module and stayed in lunar orbit the whole time, he never set foot on the Moon, and every frame and every line of narration needs to respect that. The older half of our audience will spot it the second it's wrong. And the iconic line, "one small step for man, one giant leap for mankind", has to land in Armstrong's own archival voice as he comes down the ladder, with the narrator stepping back to let it breathe. That's the moment the whole piece is built around.

I want a fresh narrator voice over the cut. One person, carrying the whole four minutes, whose tone moves with the mission instead of explaining it. Reverent at the launch, patient through the descent, quiet around Armstrong's first step, settled at the close. Write the narrator copy yourself, and the narrator must name all three men aloud and make clear that Collins remained in orbit while the other two walked. When Armstrong's archival line plays, the narrator yields.

Build it around three or four chapters. Number them on screen, ONE, TWO, THREE, optionally FOUR, and title each with a short Apollo-11-specific label like LIFTOFF, TRANQUILITY, ONE SMALL STEP, COMING HOME. Each chapter title card sits on its own beat, two seconds or so, before its footage begins. Walk the timeline forward; don't jump. Stay inside Apollo 11 itself, the Space-Race lead-in our source opens on is context, not story, and doesn't belong here. Use NASA's own archival footage and archival audio underneath the narration.

Open on a moment that earns curiosity, the rollout of the Saturn V, or a quiet wide of the launch pad with a "JULY 16, 1969" overlay. Land on the iconography the world has been carrying for fifty years: the Aldrin visor, the mission plaque, the crew portrait, in whatever order feels right. Deliver as 1920×1080 H.264 .mp4 at 24 fps with audible stereo audio, right around four minutes, call it three forty-five to four ten end to end.

## Deliverables

- The source video is at `/workspace/materials/source.mp4`.
- Write your final recap to **`/workspace/output/recap.mp4`** (this exact path and filename).
- The container has `ffmpeg`, `python3`, and a pre-cached Whisper "base" model. Internet is available for `pip install`.
- You have ~30 minutes for the agent step. Aim for a watchable output rather than the perfect cut.
