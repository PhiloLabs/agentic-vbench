# Calibration inside the shipped task environment

A number measured on the calibration host does not describe what an agent can do inside
the task, because the host carries tools the image does not ship. These runs close that
gap. There are two generations of them and only the second one closes it properly.

## What the agent actually gets

**The agent runs inside the task image.** Not a wrapper around it — the CLI itself
executes in a container built from `environment/Dockerfile`, so every command it issues
uses that image's tools and there is no host tool surface at all. The prompt is
therefore the shipped instruction verbatim: `instruction-as-run-v2.md` hashes to the
same SHA256 as `steps/solve/instruction.md`, because inside the environment the video
sits where `workdir/setup.sh` puts it and nothing has to be explained about how to
reach it.

**Egress is default-deny.** The container's `OUTPUT` policy is DROP; the one hole is an
allowlisting CONNECT proxy that accepts the CLI's backend and refuses every other host
by name. A direct connection that skips the proxy is dropped by iptables — verified:
`stats.ncaa.org` refused by the proxy and logged, a raw connection to `1.1.1.1:443`
times out, the backend connects. That is what makes `allow_internet = false` true for
task actions.

`environment-v2.txt` records the harness image digest, the task image under it, the
agent version, the egress rule and the tool inventory as the agent sees it.
`egress-v2.log` is the network evidence: every host the run asked for, allowed or not.

## Result

| agent | model / effort | reward | events | full | partial | rally anchors |
|---|---|---|---|---|---|---|
| Codex CLI | gpt-5.6-sol, xhigh | **0.0** | 16 | 0 | 0 | 2 / 23 |

153 command executions over three hours and ten minutes. It reached 16 events and got
none of them fully or partially right: two land on a real block point's set and score,
and both name the wrong players.

**Egress log: 994 connections to the model backend, zero refusals.** The agent never
once asked for a host outside it — not a grep over a transcript, but the record of a
proxy that would have refused.

## The earlier rows, and why they are superseded

`codex.solution.json` / `opus.solution.json` (0.0789 and 0.0) came from a harness that
confined access to the video but not the processing of what came out of it: frames
landed on a bind mount and were then worked on with **host** Python, NumPy, Pillow and
OCR. The confinement claim made for them was wrong, and the review caught it.

Confining the processing removes the Codex figure entirely:

| | first generation | corrected |
|---|---|---|
| reward | 0.0789 | **0.0** |
| events | 15 | 16 |
| fully correct | 0 | 0 |
| partials | 3 | 0 |
| rally anchors | 5 / 23 | 2 / 23 |

The gap is the score-bug scan: host tooling made a batch OCR pass over a two-hour
broadcast cheap, and inside the image the same work costs more, so far fewer rallies
get anchored and the three partials go with them. The corrected figure is the one that
describes the task.

`opus.agent-notes.md` is kept from the first generation because what it records is
about the video rather than the harness: in 242 tool-call turns Opus rebuilt 196 of the
match's 200 points from the score bug, anchored 168 rallies to a camera cut, and then
declined to guess how each rally ended, because the ball is 8-14 px and motion-blurred
and the broadcast carries no replays. That row is marked provisional and has not been
rerun under the corrected harness.
