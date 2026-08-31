# Rules for this task (binding)

This is an OFFLINE video-understanding task. The only evidence you may use is
the pixels of `game.mp4` and the files in this directory.

Hard rules — violating any of them voids the run:

1. **No network of any kind.** No web search, no web fetch, no URLs, no APIs,
   no search grounding, no browsing. Do not enable or request any web tool.
2. **Do not attempt to identify the real-world game.** Do not try to determine
   the teams, players, venue, date, league, or score from memory or from any
   source other than the pixels. Do not recall or reconstruct any box score,
   play-by-play, or news account you may have seen in training.
3. **Use only this directory.** Do not read, list, or search any file outside
   it. There is nothing else here for you: no answer key exists on this
   machine's reachable paths.
4. **Work from the video.** Extract frames, seek, zoom, and reason from what
   you see. Refer to the teams only as NAVY and WHITE per `instruction.md`.
5. Write your final answer to `output/solution.json` exactly per
   `schema.json`. A complete best-effort answer beats an empty one.
