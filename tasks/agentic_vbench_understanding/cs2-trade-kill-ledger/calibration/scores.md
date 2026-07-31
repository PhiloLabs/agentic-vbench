# Calibration — cs2-trade-kill-ledger

Deterministic F1 scorer (`steps/solve/tests/judge.py`). A task clears the bar when
**every real agent scores below 0.10** and a real attempt takes **more than 50
tool-call turns**. Oracle must be 1.0 and an empty attempt 0.

Local anchors (`provenance/local_calibration.py`, no agents, run against the GT):

| run | score | notes |
|---|---|---|
| oracle | 1.0 | 169/169 full-tuple TPs |
| empty / null | 0.0 | |
| 169-entry random spam | 0.0 | 3 chance kill-level matches, 0 full-tuple |
| oracle with all `was_traded=false` | 0.8225 | designed cap for ignoring the trade half (139/169 kills are untraded); an agent that reconstructs every kill has done the long-horizon work, and the trade fields exist to couple entries so a missed kill corrupts its neighbours' `was_traded` |
| oracle with t fuzzed ±4 s | 1.0 | 5 s tolerance behaves as specified |

Partial-credit curve (accurate coverage of the first X% of the match), showing the
reward rises smoothly and the bar is reachable rather than degenerate:

| coverage | 25% | 50% | 75% | 100% |
|---|---|---|---|---|
| reward | 0.3981 | 0.664 | 0.8542 | 1.0 |

The curve also states the difficulty mechanism honestly: staying under the 0.10
agent bar requires that strong agents cannot accurately cover even ~5% of the 169
kills within the time budget.

**Single-POV probe (2026-07-31, informal, before final scope lock).** A 2-round
render of P3's POV (16-kill GT subset, same judge; oracle 1.0, empty 0.0) was
attempted by two real agents:

| agent | effort | result |
|---|---|---|
| Claude (Opus 4.8, via a Claude Code subagent - NOT the official headless harness) | 91 tool calls, 32 min, 219k tokens | **0.0** - localized P3's kills in time (±0.4 s), got team attribution and trade structure right, but missed every specific victim label; hallucinated 4 off-screen deaths from audio + elimination logic |
| Codex CLI (`codex exec --json`, no image viewing in its loop) | 16 commands | **0.0** - recovered firefight timing from audio energy (t within ~1 s of real kills) but fabricated all identities; also probed mp4 metadata with `strings` (clean, no identity leak) |

Honest read. In the single-POV probe, specific player labels beyond the camera
holder are structurally unobservable (labels bind to steamids, which only each
player's own POV reveals), so these zeros are partly unobservability, not pure
difficulty - the three near-misses each failed on exactly one identity field
with time, team, and trade structure correct. The full 10-POV task makes
identity recoverable by cross-POV death correlation, so full-task scores will be
above zero and whether they stay under the 0.10 bar is an open question that
only the official calibration can answer. What the probe does establish: per
kill, time localization is cheap and identity is the expensive part; 91 tool
calls covered 1/10 of the media without any cross-POV work, so coverage under
the time budget is the real difficulty mechanism. It also empirically confirms
the audio ablation claim (timing leaks, identity does not, F1 = 0). Full scope
(23 rounds) is retained. These probe runs used the author's host environment
and a task subset; they are cost measurements only, and the official
three-agent calibration will use the family's prescribed harness commands in
the shipped container.

Agent runs (post-render), per the family calibration guidance - iterate with Codex
first, raw trajectories only:

| harness | harness version | model | reasoning | score | tool-call turns | trajectory |
|---|---|---|---|---|---|---|
| Codex | _to run_ | GPT 5.6 Sol | _to run_ | _to run_ | _to run_ | rollouts/codex.jsonl |
| Antigravity | _to run_ | Gemini 3.5 Flash | _to run_ | _to run_ | _to run_ | rollouts/antigravity.log |
| Claude Code | _to run_ | Fable 5 | _to run_ | _to run_ | _to run_ | rollouts/claude.jsonl |

Anti-shortcut ablations (post-render): `no_media`, `single_frame`, `audio_only`,
`frame_dump_no_tools` — every one must land in the null band (<= 0.15).

Raw transcripts go in `rollouts/` — one directory per agent, so a reviewer can
confirm each score was earned honestly and count the tool-call turns.
