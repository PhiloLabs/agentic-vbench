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
it to look at. `environment.txt` records what that environment was, and
`instruction-as-run.md` is the exact prompt: the shipped instruction plus one section
explaining the wrapper.

## Results

| agent | model / effort | reward | events | full | partial | rally anchors |
|---|---|---|---|---|---|---|
| Codex CLI | gpt-5.6-sol, xhigh | **0.0952** | 24 | 1 | 2 | 11 / 18 |
| Claude Code | Opus 5, xhigh | **0.0** | 8 | 0 | 0 | 1 / 18 |

Both are under the ~0.10 bar, Codex only just. It is also the first run on either task
to get a block point **fully correct** — set 1 at 18-14, with both credited blockers
(McEwan-Llarenas, Stowell), the stuffed hitter (Ryan) and the setter (Ung) all right.

The jump from the host figure (0.0213) is worth understanding, because it is not a
jump in attribution. Rally anchors found went from 3 to 11 while fully-correct events
went from 0 to 1: what the added tools bought is a **scripted pass over the score bug**
— OCR plus template matching across a two-hour broadcast — which makes finding the
rallies cheap. That is the tedious layer, not the hard one. The attribution layer moved
by one event.

Opus took 384 tool-call turns (231 Read, 152 Bash) and submitted 8 events, matching
one rally anchor and no attribution.
