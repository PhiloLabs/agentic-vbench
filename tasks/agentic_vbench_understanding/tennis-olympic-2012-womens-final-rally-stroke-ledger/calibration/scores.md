# Calibration — tennis-olympic-2012-womens-final-rally-stroke-ledger

Deterministic scorer (`steps/solve/tests/judge.py`): order-preserving 3-field F1. A
true positive requires the exact player, the exact stroke class, and a `start_frame`
within the inclusive +/-8-frame window (0.32 seconds at 25 fps). The key is 211
live-point strokes; nine Hit rows overlapping Fault/Let serve windows and all 112 Serve
rows are deliberately excluded (see `../SPEC.md`, transforms 1-2).

A task clears the family bar when the oracle scores 1.0, an empty submission scores
≤ 0.10, **every** real agent scores below 0.10, each ablation scores ≤ 0.15, and a real
attempt takes more than 50 tool-call turns.


## Measured anchors

Reproducible from this repo with no video: run `calibration/build_ground_truth.py` for
the oracle, and the judge directly for the rest.

| run | score | note |
|---|---:|---|
| oracle (exact 211-stroke ledger) | 1.000000 | asserted by `build_ground_truth.py` |
| empty submission (`{"strokes": []}`) | 0.000000 | |
| random guess over the vocabulary | PENDING | old 220-entry measurement invalidated |
| no-media prior | PENDING | old 220-entry measurement invalidated |

Scorer behaviour spot-checks, same harness:

| probe | score | what it shows |
|---|---:|---|
| oracle frames, both players swapped | 0.000000 | localization alone earns nothing |
| oracle frames, forehand/backhand flipped | 0.000000 | likewise for the stroke class |
| oracle, every entry duplicated | 0.666667 | padding is punished through precision |
| oracle submitted in reverse order | 0.004739 | the ledger must be chronological |
| oracle **plus all 112 serves** logged as strokes | 0.790262 | extra events reduce precision |
| 22 exact strokes only (every 10th) | 0.188841 | partial credit is smooth, not all-or-nothing |
| the same 22 padded to 211 with guesses | PENDING | old 220-entry measurement invalidated |


## Required agent calibration — PARTIALLY RUN; CODEX PASSES CEILING, CLAUDE MEDIUM EXCEEDS IT

| harness | harness version | model | reasoning | score | tool-call turns | trajectory |
|---|---|---|---|---:|---:|---|
| Codex CLI | 0.154.0 / Harbor 0.22.0 | gpt-5.6-sol | medium | 0.087591 | 88 | [`codex-gpt-5.6-sol.jsonl`](rollouts/codex-gpt-5.6-sol.jsonl) |
| Claude Code CLI | 2.1.247 / Harbor 0.22.0 | claude-opus-4-8 | high | 0.000000 | 88 | trajectory not retained (see below) |
| Claude Code CLI | 2.1.270 / Harbor 0.22.0 | claude-opus-4-8 | medium | 0.101806 | 204 | [`claude-opus-4.8.jsonl`](rollouts/claude-opus-4.8.jsonl) |
| Antigravity | | gemini-3.5-flash | | PENDING | | |

Run each through Harbor against the shipped image, keep the raw trajectory under
`rollouts/`, and fill the row. The task does not enter review until all three hold valid
final numbers.

The Codex run used the `skillbench` conda environment, Docker, medium reasoning, and
Codex CLI 0.154.0. Agent execution took 2h1m44s; the full Harbor job took 2h10m2s. It
submitted 474 valid strokes after 88 tool calls (70 command executions and 18 file
changes). The verifier found 30 true positives, 444 false positives, and 181 false
negatives (precision 0.063291, recall 0.142180) for an F1 of 0.087591. The run clears
the `> 50` effort floor and **passes the required `< 0.10` real-agent ceiling**. The
trajectory audit found no web-search tool call, external URL in an agent command, or
`curl`/`wget` use. Only the byte-for-byte native trajectory is kept in `rollouts/`; the
submitted ledger and verifier output were removed from the repo.

### Claude Code CLI (Opus 4.8, high) — THREE ATTEMPTS, no valid score yet

Run through Harbor (`-a claude-code -m claude-opus-4-8 --ak reasoning_effort=high`),
Docker executor, agent phase capped at 45 minutes via `--agent-timeout-multiplier 0.25`.
Authenticated with a subscription OAuth token
(`CLAUDE_CODE_OAUTH_TOKEN`); the CLI reported `apiKeySource: none`.

**This run produced no usable calibration number and must be repeated.** The agent worked
32m 20s of the 45m cap and the CLI then returned `api_error_status: 429` — *"You've hit
your org's monthly spend limit … your session limit resets 7:50pm (UTC)"*. Harbor
classified it `ApiRateLimitError`. This is a provider-side billing cutoff, not a task
failure and not an agent failure.

The verifier still ran and recorded `reward = 0.0` with `reason: "invalid solution:
[Errno 2] No such file or directory: '/workspace/output/solution.json'"`. **That zero is
an artifact of the cutoff.** The agent never reached the point of writing a ledger, so
there is no partial solution to score and none is kept.

What the partial trajectory does show: 15 tool calls (8 `Bash`, 7 `Read`) in the main
session, plus one `general-purpose` subagent spawned that failed immediately with 0 tool
calls of its own. That is well short of the `> 50` effort floor, but the run was cut off
rather than finished, so it is not evidence about the floor either way.

A first attempt the same day is also not a row: `CLAUDE_FORCE_OAUTH=1` was passed with no
credential behind it, the container had no access to the host keychain, Claude Code never
opened a session ("No Claude Code session directory found"), and the trial ended in
2m 21s with the same artifact `reward = 0.0`. No trajectory was produced and none is kept.

Artifacts for that attempt were not retained.

**A third attempt, after the session limit reset, ran to the full 45-minute cap and also
produced no ledger.** Harbor ended it with `AgentTimeoutError`. This is the run kept as
the Claude Code row above, and it is still not a valid score.

It is a far more substantial run than the rate-limited one: **88 tool calls** (53 `Bash`,
18 `Read`, 17 `Write`), clearing the `> 50` effort floor with room. The agent built a real
detection pipeline across 17 scripts in `work/` — audio onset detection (`onset.py`,
`peaks.py`, `frameenv.py`), ball tracking (`ball.py`, `ball_strikes.py`), frame montages
for player identification (`montage.py`, `cropmont.py`, `mlist.py`), and end/side
classification (`ends.py`, `endclass.py`, `endclass2.py`) — and was still waiting on a
ball-tracking stage when the cap expired. The stream also carries 43 `rate_limit_event`
entries, so throttling consumed part of the budget.

**No partial ledger exists to score.** The string `start_frame` appears zero times in the
19 MB trajectory: the agent never emitted a single stroke entry, so `reward = 0.0` with
`reason: "invalid solution: … No such file or directory: '/workspace/output/solution.json'"`
is again an artifact of the cutoff rather than a measurement. The `work/` intermediates
died with the container (`environment.delete: true`).

The lesson for the next attempt is the cap, not the model: Opus 4.8 pursued a heavy
pipeline and needs more than 45 minutes; the task's own `timeout_sec` is 10800.

**The raw trajectory for this run is not retained.** Harbor treats agent environment
values as secrets and redacts them from the artifacts it writes; the run passed
`CLAUDE_FORCE_OAUTH=1`, so the literal string `1` was scrubbed from every artifact. The
captured trajectory came out with each digit `1` replaced by `[REDACTED]` across 416
lines — `1280x720` became `[REDACTED]280x720`, frame `41135` became `4[REDACTED][REDACTED]35`
— which makes it useless as evidence, and the copy Harbor left in `jobs/` is damaged the
same way. No artifact from this run is kept in `rollouts/`. The turn counts quoted above
were measured before the artifact was discarded. **Anyone repeating this run should omit
`CLAUDE_FORCE_OAUTH=1`** — the OAuth token authenticates on its own — or the same
corruption will recur.

### Claude Code CLI (Opus 4.8, medium) — 0.101806, ABOVE THE `< 0.10` CEILING

Run through Harbor (`-a claude-code -m claude-opus-4-8 --ak reasoning_effort=medium`,
`--agent-setup-timeout-multiplier 3.0`), Docker executor, full 10800 s task budget, OAuth
token only (`apiKeySource: none`, no `CLAUDE_FORCE_OAUTH`). The trajectory has zero
`[REDACTED]` strings.

The agent ran 8506 s (about 2 h 22 min) of agent time and made 204 main-session tool
calls (127 `Bash`, 45 `Read`, 10 `Write`, 21 `Agent`, 1 `ListAgents`). Its 21 subagents
made another 228 tool calls. It wrote and validated `output/solution.json` (398 strokes,
frames 25845-121996). Grading used the task's own `steps/solve/tests/test.sh`.

Verifier: 398 valid strokes, 31 true positives, 367 false positives, 180 false negatives.
That is precision 0.077889 and recall 0.146919, for **F1 0.101806**. It also reports 59
player-and-frame matches and 127 frame-only matches. **This is just above the required
`< 0.10` real-agent ceiling**. Codex (0.087591) stays below it.

Trajectory audit: zero `[REDACTED]` strings, no credential value, and no `curl`/`wget`.
There are no `WebSearch` or `WebFetch` tool calls; those names appear only in the
tool list of the session init events.

## Required anti-shortcut runs — ALL RUN

The suite used `gpt-5.6-sol`; the current audio-only run used medium reasoning, Harbor
0.22.0, Codex CLI 0.154.0, and disabled web search. Harbor forced a fresh Docker build;
the staging guard exposed only a 4,955.022-second AAC file and the vocabulary, with no
video stream. An appended ablation instruction required a non-empty, best-effort answer
and blind guesses for visually unavailable fields. The trajectory audit found no web
call, external URL, or credential value. `turns` counts tool calls, the same metric as
the 88 in the calibration table above.

| degraded input | score | pred strokes | turns | outcome |
|---|---:|---:|---:|---|
| no media (prompt + vocabulary only) | **0.000000** | 0 | 6 | declined to fabricate; submitted `{"strokes": []}` |
| single frame | **0.000000** | 1 | 8 | logged one stroke, at the frame it was handed, with the wrong class |
| video only (audio stripped) | **0.090909** | 207 | 77 | full-length attempt; 19 true positives, close to the current full-media row |
| audio only | **0.018570** | 866 | 47 | full-length attempt; 10 true positives from audio transients plus blind labels |
| all frames pasted, no tools | **0.000000** | 0 | 0 | returned `{"strokes": []}` without attempting |

**`single_frame` is the informative one.** Handed frame 30773 (a documented rally
take-back) and nothing else, the agent submitted exactly one entry — Sharapova,
*backhand*, frame 30773. The key has Sharapova **forehand** at 30773, so even with the
frame supplied, the player correct, and the localization free, the stroke class was
wrong: `player_and_frame_matches` 1, `frame_only_matches` 1, true positives 0. One still
gives up the venue, the two players and the scoreboard, and none of that is in the
answer.

**Caveat on `no_media`.** The 0.0 is a refusal, not a defeated prior: the agent wrote an
empty ledger rather than guessing, so this run scores identically to the empty anchor and
does *not* on its own establish that recall of the match yields nothing. The stronger
form is the lacrosse task's adversarial-recall ablation — name the match outright, forbid
the video, and *require* a complete ledger — which is not yet run here and is the honest
way to close this item.

**`video_only` scores close to, and slightly above, the Codex full-media row.**
Stripping the AAC track (`-an -c:v copy`, guard-verified to leave no audio stream) and
otherwise handing over the same 82-minute broadcast, the agent worked 77 tool calls —
4 `ffmpeg` decodes for overview tiles, then 13 OpenCV passes — and submitted 207 strokes
for **0.090909**, against the Codex full-media row's 474 strokes and **0.087591**. (The
Claude Opus 4.8 medium full-media row, 0.101806, is a different agent.)
Detail: 19 true positives, 188 false positives, 192 false negatives, precision 0.091787,
recall 0.090047, `player_and_frame_matches` 31, `frame_only_matches` 42.

Both sides are single stochastic runs, so the difference is not a clean modality-effect
estimate. The video-only run nevertheless remains close to the full-media result and
clears the `≤ 0.15` ablation bar. The audio-only result is substantially lower, so this
pair does not support treating the two modalities as interchangeable.

**The `audio_only` run scores 0.018570.** The medium-reasoning model made 47 tool calls
(36 command executions and 11 file changes) and submitted 866 valid strokes. It decoded
the AAC into mono and stereo-difference analysis tracks, built short-window energy and
spectral features, grouped impacts by tennis-like cadence, removed each inferred
rally's first impact as the serve, and shifted the remaining impacts back 10 frames.
Player and stroke labels were necessarily inferred or guessed. The verifier found 10
true positives, 856 false positives, and 201 false negatives: precision 0.011547,
recall 0.047393, 17 player-and-frame matches, and 37 frame-only matches. Agent execution
took 15m38s; the full forced-build Harbor job took 20m52s. The native rollout,
Harbor-normalized trajectory, submitted solution, and verifier outputs are all kept
under `ablation/`.

**`frame_dump_no_tools` is a zero on the supplied sparse frames.** The agent got 83
frames — one every 60 s, so 1500 frames apart — in a read-only sandbox with no media to
seek. It made 0 tool calls, spent 282 reasoning tokens, and
returned `{"strokes": []}`. Read this row as confirming the ablation is airtight, not as
a measurement of what the model can see in a still: `single_frame` is the row that
actually probes perception, and it is the one that got the stroke class wrong.

**Consequences for the task as specified:**

- The non-refusal run is below the `≤ 0.15` bar at 0.018570. Audio supplied limited
  localization: 37 of 866 predictions matched a key frame before the blind player/class
  guesses reduced that set to 10 true positives.
- Audio transients yielded 37 frame-only matches, but padding the ledger with 866
  candidates reduced precision to 0.011547. Blind two-way player and class assignments
  left only 10 fully correct strokes.
- The disclosed 10-frame contact offset helped produce some matches, but this run does
  not show an actionable audio shortcut: its F1 is far below the full-media and
  video-only runs and passes the numerical ablation bar with room.

## Why the bar should hold

*Localization.* 211 strokes across 123875 frames, each placed on an anchor that is
deliberately not the salient moment. See the take-back table above.

*Player.* The camera never moves and the players change ends through the match, so
screen position is not identity and has to be re-established at every changeover. The
far player is roughly 40 px tall. Verified: Sharapova is the far player in game 1 and
the near player in game 2.

*Class.* Forehand and backhand split 120/91, so neither is a safe default, and the call
depends on the player's own orientation rather than on the side of the screen.

*Exclusions.* Nine raw Hit rows are Fault/Let serve swings, the separate 112-row Serve
track is also unscored, and broadcast replays show strokes again. These are separable
only from surrounding context. Appending all 112 serves to the corrected oracle lowers
F1 from 1.0 to 0.790262.

*Shortcut resistance.* The scoreboard graphic is on screen throughout and the match is a
famous one, but neither helps: the graphic shows the score, and nothing in the answer is
a score. No published source lists this match stroke by stroke with frame numbers, and
the corrected no-media prior still needs measurement.

None of this is established until the three agent rows above hold real numbers.
