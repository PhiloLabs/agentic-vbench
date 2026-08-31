# Environment (Docker)

The task environment isolates the agent: it gets the video
(`/workspace/materials/minimap_vod.mp4`) and the prompt
(`/workspace` working dir + `steps/solve/instruction.md`) only. The ground truth
(`steps/solve/tests/gt.json`) and the scorer (`steps/solve/tests/judge.py`) are
**never** in the agent image — the harness mounts them for the verify step only,
after the agent finishes. This prevents the filesystem-snooping cheat caught during
local calibration (an agent reading `gt/timeline_named_gt.json` up the tree).

## Build

The video is fetched at build time from a pinned Hugging Face URL and verified by
SHA256 (see `ARG MATERIALS_URL` / `ARG MATERIALS_SHA256` in the Dockerfile), so no
local media file is needed and the build works on any host. Run from the task dir:

```bash
docker build -f environment/Dockerfile -t lol-minimap-task .
```

## Hosting

The ~157 MB video is not committed; it is hosted on Hugging Face and pinned by
checksum:

- URL: `https://huggingface.co/datasets/iTheresaApocalypse/agentvbench/resolve/main/lol_minimap/minimap_vod.mp4`
- `MATERIALS_SHA256=9d778f43930ff1d5d9938429f2e87c36e21ea9234eddf2168485de67dd7ab743`

To re-host elsewhere, override at build time:
`docker build --build-arg MATERIALS_URL=<new-url> --build-arg MATERIALS_SHA256=<new-digest> ...`.
