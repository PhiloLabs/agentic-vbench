# Calibration inside the shipped task environment

A number measured on the calibration host does not describe what an agent can do inside
the task, because the host carries tools the image does not ship. These runs close that
gap. There are two generations of them and only the second one closes it properly.

## What the agent actually gets

**The agent runs inside the task image.** Not a wrapper around it — the CLI itself
executes in a container built from `environment/Dockerfile`, so every command it issues
uses that image's tools and there is no host tool surface at all. The prompt is
therefore the shipped instruction verbatim: inside the environment the video sits where
`workdir/setup.sh` puts it, and nothing has to be explained about how to reach it.

**Egress is default-deny.** The container's `OUTPUT` policy is DROP; the one hole is an
allowlisting CONNECT proxy that accepts the CLI's backend and refuses every other host
by name. A direct connection that skips the proxy is dropped by iptables — verified:
`stats.ncaa.org` refused, a raw connection to `1.1.1.1:443` times out, the backend
connects. That is what makes `allow_internet = false` true for task actions.

`environment-v2.txt` records the harness image digest, the task image under it, the
agent version, the egress rule and the tool inventory as the agent sees it.
`egress-v2.log` is the network evidence: every host the run asked for, allowed or not.

## Result

| agent | model / effort | reward | events | full | partial | rally anchors |
|---|---|---|---|---|---|---|
| Codex CLI | gpt-5.6-sol, xhigh | **0.0426** | 29 | 1 | 0 | 9 / 18 |

232 command executions over five hours. It still got one block point fully correct.

**Egress log: 1365 connections to the model backend, zero refusals.** The agent never
once asked for a host outside it — not a grep over a transcript, but the record of a
proxy that would have refused.

## The earlier rows, and why they are superseded

`codex.solution.json` / `opus.solution.json` (0.0952 and 0.0) came from a harness that
confined access to the video but not the processing of what came out of it: frames
landed on a bind mount and were then worked on with **host** Python, NumPy, Pillow and
OCR. The confinement claim made for them was wrong, and the review caught it.

Confining the processing halves the Codex figure:

| | first generation | corrected |
|---|---|---|
| reward | 0.0952 | **0.0426** |
| events | 24 | 29 |
| fully correct | 1 | 1 |
| rally anchors | 11 / 18 | 9 / 18 |

The gap is the score-bug scan: host tooling made a batch OCR pass over a two-hour
broadcast cheap, and inside the image the same work costs more, so fewer rallies get
found and precision falls. The corrected figure is the one that describes the task.

Two harness failures preceded the corrected run and neither produced a result:
a login shell reset `PATH` so the CLI was never found, and a read timeout left on the
proxy's upstream socket tore down the model stream after 30 s of quiet mid-generation.
Both are fixed; the second is why `create_connection`'s timeout is cleared explicitly.
