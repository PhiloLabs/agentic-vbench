# Calibration inside the shipped task environment

The runs in `../rollouts/` were executed on the calibration host, where the agents
reached for Tesseract, ImageMagick, NumPy and Pillow. The task image ships its own tool
set, so a number measured on the host does not necessarily describe what an agent can
do inside the task. These runs remove that gap: every action on the video happens
inside a container built from `environment/Dockerfile`.

## How the confinement works

It is structural rather than instructed. The workspace the agent sees holds **no video
at all** — the broadcast exists only inside the container, at the path the task's own
`workdir/setup.sh` puts it. The only route to it is a three-line wrapper:

```sh
#!/bin/sh
exec docker exec -w /workspace/work avb-parity-<task> sh -lc "$*"
```

The container runs with `--network none`, so no task action can reach the network,
which is what `allow_internet = false` means here. Its `/workspace/work` is a bind
mount of the host workspace, so frames the agent extracts inside appear on the host for
it to look at. `environment.txt` records what that environment was:

```
image digest: sha256:58ed2ce8cbd8a220b9d2c6249bac619955d95de611a4097e35a12834332e1aa2
container network: none
media inside the image: 13ccbabb…d08ba9e   (matches the pin)
ffmpeg, ffprobe, tesseract, convert, python3 + numpy 2.1.3, Pillow 11.0.0
```

`instruction-as-run.md` is the exact prompt: the shipped instruction plus one section
explaining the wrapper.

## Results

| agent | model / effort | reward | events | full | partial | rally anchors |
|---|---|---|---|---|---|---|
| Codex CLI | gpt-5.6-sol, xhigh | **0.0789** | 15 | 0 | 3 | 5 |
| Claude Code | Opus 5, xhigh | **0.0** | 0 | 0 | 0 | 0 |

Codex reported fewer events than on the host (15 against 31) and was right more often
about the rally, which is where the higher number comes from — precision 0.10 against
0.017. It still got no block point fully correct.

Opus submitted an empty list and wrote `opus.agent-notes.md` explaining why, which is
worth reading in full. In 242 tool-call turns it rebuilt **196 of the match's 200
points** from the score bug, including two overturned calls, and anchored 168 rallies
to a camera cut within 0.5–3.5 s of the ball landing. Then it stopped, because deciding
*how* each rally ended needs the ball:

> the ball is ~8–14 px and often motion-blurred […] at 0.1 s sampling the ball is
> readable, but each such sheet covers only ~1.2 s, so it needs an anchor tighter than
> the ±3.5 s I can derive […] The broadcast shows no replays.

It also records, usefully for the observability question, that blocker and hitter
jersey numbers **are** readable from the live wide shot at 4× upscale. What defeats it
is classifying the rally ending, not identifying the players.

Native traces for both runs are published with the other streams; `../scores.md` lists
the URLs and SHA256s.
