# Rules for this task (binding)

This is an OFFLINE video-understanding task. The only evidence you may use is the
pixels of `materials/game.mp4` and the files in this directory.

Hard rules — violating any of them voids the run:

1. **No network of any kind.** No web search, no web fetch, no URLs, no APIs, no
   search grounding, no browsing. Do not invoke any tool that reaches outside this
   machine, and do not enable or request one.
2. **Do not attempt to identify the source of this video or its annotations.** Do
   not search for the dataset, the recording, the venue, the players, the event,
   or any published annotation file. Do not recall or reconstruct any dataset,
   repository, or annotation you may have seen in training. The answer must come
   from the pixels, not from provenance.
3. **Use only this directory.** Do not read, list, or search any file outside it.
   There is nothing else here for you: no answer key exists on any path this
   machine can reach.
4. **Work from the video.** Extract frames, seek, zoom, and reason from what you
   see. Identify players only as `left` and `right` by their position in frame,
   per `instruction.md`.
5. Write your final answer to `output/solution.json` exactly per the schema in
   `instruction.md`.
