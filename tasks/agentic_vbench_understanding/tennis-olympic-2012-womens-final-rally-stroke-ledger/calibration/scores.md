# Calibration — tennis-olympic-2012-womens-final-rally-stroke-ledger

Deterministic scorer (`steps/solve/tests/judge.py`): order-preserving 3-field F1. A
true positive requires the exact player, the exact stroke class, and a `start_frame`
within 8 frames (0.32 s at 25 fps) of the published annotation. The key is 211
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
| oracle shifted ±8 frames | 1.000000 | tolerance is inclusive at 8 |
| oracle frames, both players swapped | 0.000000 | localization alone earns nothing |
| oracle frames, forehand/backhand flipped | 0.000000 | likewise for the stroke class |
| oracle, every entry duplicated | 0.666667 | padding is punished through precision |
| oracle submitted in reverse order | 0.004739 | the ledger must be chronological |
| oracle **plus all 112 serves** logged as strokes | 0.790262 | extra events reduce precision |
| 22 exact strokes only (every 10th) | 0.188841 | partial credit is smooth, not all-or-nothing |
| the same 22 padded to 211 with guesses | PENDING | old 220-entry measurement invalidated |

The bar in concrete terms — exact strokes needed to clear 0.10, with nothing else
submitted:

| exact strokes | 8 | 10 | **12** | 14 | 16 |
|---|---:|---:|---:|---:|---:|
| F1 | 0.073059 | 0.090498 | **0.107623** | 0.124444 | 0.140969 |

So an agent has to fully reconstruct roughly 12 of the 211 strokes — right player, right
side, take-back frame within 0.32 s — before it scores 0.10.


## Required agent calibration — PARTIALLY RUN

| harness | harness version | model | reasoning | score | tool-call turns | trajectory |
|---|---|---|---|---:|---:|---|
| Codex CLI | 0.150.1 / Harbor 0.22.0 | gpt-5.6-sol | high | 0.083832 | 61 | [`codex-gpt-5.6-sol.jsonl`](rollouts/codex-gpt-5.6-sol.jsonl) |
| Claude Code CLI | 2.1.247 / Harbor 0.22.0 | claude-opus-4-8 | high | 0.000000 | 88 | trajectory not retained (see below) |
| Antigravity | | gemini-3.5-flash | | PENDING | | |

Run each through Harbor against the shipped image, keep the raw trajectory under
`rollouts/`, and fill the row. The task does not enter review until all three hold valid
final numbers.

The Codex run completed in 33m08s and submitted 123 valid strokes. Rescored at the
+/-8-frame tolerance it has 14 true positives, 109 false positives, and 197 false
negatives (precision 0.113821, recall 0.066351) for an F1 of 0.083832 — below the
required `< 0.10` real-agent ceiling, which it missed at 0.107784 under the old
+/-10-frame tolerance. Its 61 tool-call turns clear the `> 50` effort floor. Exactly four of
its 18 previously-matched strokes fall outside the tighter window, all four pinned 9
frames *after* the annotated take-back — the contact-anchoring bias, caught by the
tighter tolerance. The exact submitted ledger and verifier output are
kept beside the trajectory as `codex-gpt-5.6-sol.solution.json` and
`codex-gpt-5.6-sol.reward.json`.

### Claude Code CLI (Opus 4.8, high) — THREE ATTEMPTS, no valid score yet

Run through Harbor (`-a claude-code -m claude-opus-4-8 --ak reasoning_effort=high`),
Docker executor, agent phase capped at 45 minutes via `--agent-timeout-multiplier 0.25` —
the same cap the Codex row used. Authenticated with a subscription OAuth token
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

The lesson for the next attempt is the cap, not the model: `--agent-timeout-multiplier
0.25` was chosen to match the Codex row, which finished in 33m08s. Opus 4.8 pursued a
heavier pipeline and needs more than 45 minutes; the task's own `timeout_sec` is 10800.

**The raw trajectory for this run is not retained.** Harbor treats agent environment
values as secrets and redacts them from the artifacts it writes; the run passed
`CLAUDE_FORCE_OAUTH=1`, so the literal string `1` was scrubbed from every artifact. The
captured trajectory came out with each digit `1` replaced by `[REDACTED]` across 416
lines — `1280x720` became `[REDACTED]280x720`, frame `41135` became `4[REDACTED][REDACTED]35`
— which makes it useless as evidence, and the copy Harbor left in `jobs/` is damaged the
same way. Only `rollouts/claude-opus-4.8.reward.json` is kept, with the two counts the
redaction had corrupted (`ground_truth_strokes`, `false_negatives`) restored to 211 from
the task's own key. The turn counts quoted above were measured before the artifact was
discarded. **Anyone repeating this run should omit `CLAUDE_FORCE_OAUTH=1`** — the OAuth
token authenticates on its own — or the same corruption will recur.

## Required anti-shortcut runs — ALL RUN; ONE FAILS THE BAR

Measured with Codex CLI 0.149.1 / `gpt-5.6-sol` at high reasoning — the same
harness and settings as the calibration row — via `runpack/stage_ablation.sh` and
`runpack/run_codex_ablation.sh`. The three tool-using runs were sandboxed
`workspace-write` and `frame_dump_no_tools` `read-only`, all with `tools.web_search=false`;
the trajectory audit found no web call and no external URL in any of them. `turns` counts
tool calls, the same metric as the 61 in the calibration table above.

| degraded input | score | pred strokes | turns | outcome |
|---|---:|---:|---:|---|
| no media (prompt + vocabulary only) | **0.000000** | 0 | 6 | declined to fabricate; submitted `{"strokes": []}` |
| single frame | **0.000000** | 1 | 8 | logged one stroke, at the frame it was handed, with the wrong class |
| video only (audio stripped) | **0.090909** | 207 | 77 | full-length attempt; 19 true positives, above the full-media row |
| audio only | **0.150685** | 227 | 28 | onset detection minus a constant 10 frames; **fails the bar** |
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

**`video_only` did not degrade the agent — it scored *above* the full-media row.**
Stripping the AAC track (`-an -c:v copy`, guard-verified to leave no audio stream) and
otherwise handing over the same 82-minute broadcast, the agent worked 77 tool calls —
4 `ffmpeg` decodes for overview tiles, then 13 OpenCV passes — and submitted 207 strokes
for **0.090909**, against the full-media calibration row's 123 strokes and **0.083832**.
Detail: 19 true positives, 188 false positives, 192 false negatives, precision 0.091787,
recall 0.090047, `player_and_frame_matches` 31, `frame_only_matches` 42.

Both sides of that comparison are single stochastic runs and the gap is well inside
run-to-run noise, so this is not a measurement that audio *hurts*. What it does rule out
is any claim that audio is load-bearing: an agent denied the contact cue entirely still
matched the full-media attempt, and it is the take-back anchor and the player/class calls
— not the soundtrack — that hold the score down. This is the same conclusion SPEC open
item 3 reaches from the serve exclusion, now with a run behind it. The task is still
*better posed* as an audio-video problem, but it should not be advertised as one that
audio is required to solve. The run clears the `≤ 0.15` ablation bar with room.

**`frame_dump_no_tools` is a zero the task's own geometry guarantees.** The agent got
83 frames — one every 60 s, so 1500 frames apart — in a read-only sandbox with no media
to seek. Placing a stroke needs `start_frame` within ±8 frames, and no two supplied
frames are closer than 1500, so *no* stroke in the match is reachable no matter how well
the agent reads the pictures. It made 0 tool calls, spent 282 reasoning tokens, and
returned `{"strokes": []}`. Read this row as confirming the ablation is airtight, not as
a measurement of what the model can see in a still: `single_frame` is the row that
actually probes perception, and it is the one that got the stroke class wrong.

What the agent did, from `work/build_ledger.py` in its own workspace:

```python
frame = int(round(x['time']*25))-10                 # audio contact onset, minus a constant
h=(frame*1103515245 + (0 if player=='Sharapova' else 12345)) & 0x7fffffff
stroke='forehand' if h%10<6 else 'backhand'         # deterministic 3:2 prior, not perception
```

Three separate shortcuts compose:

1. **Localization is solved acoustically.** Racquet impacts are loud, isolated transients.
   The agent detected them and subtracted a **constant 10 frames** — the offset
   `instruction.md` discloses in the sentence "roughly 10 frames before the racquet
   strikes the ball". Measured against the key: of 227 predictions, 175 land within 40
   frames of a real stroke, with a median delta of **+5** and **111 inside the ±8
   window**. The take-back anchor is the SPEC's primary difficulty argument, and a single
   subtraction defeats it, because the offset is near-constant *and* we state its value.
2. **Player comes from structure, not sound.** Within-point alternation plus a
   "five-returned-point service-game proxy" — no perception at all. 64 of the 111
   frame-window hits got the player right (~58%, near the 50% floor).
3. **Class comes from a hash.** A seeded PRNG with a 3:2 forehand prior against the key's
   real 120/91 (≈57/43) split. 33 of those 64 survived (~52%).

So a run with *zero* visual information converts good onset detection plus two blind
priors into 33 true positives, while the full-media agent managed 14. Because both
vocabularies are 2-way and closed, guessing is cheap: the tuple survives at
`0.58 × 0.52 ≈ 30%` of whatever the audio localizes, and localizing is the easy part.

**Consequences for the task as specified:**

- The `≤ 0.15` ablation bar is **failed**. This task is not calibrated.
- "Video is required" is now contradicted twice — `video_only` (0.090909) matched the
  full-media row and `audio_only` (0.150685) nearly doubled it. Every ranking here is a
  single stochastic run, but the direction is consistent and the audio margin is not
  small.
- SPEC's *Localization* argument in "Why the bar should hold" is the specific claim that
  broke. The anchor is only adversarial to a **vision** pipeline stepping frame by frame;
  to an audio pipeline it is a fixed offset from the most detectable event in the signal.

Candidate fixes, none applied yet — this needs a decision:

- **Stop disclosing the offset.** `instruction.md` states "roughly 10 frames" twice.
  Removing the number does not remove the regularity, but it stops handing it over.
- **Tighten the tolerance.** At ±8 the median audio delta of +5 sits inside the window.
  The annotator-consistency argument that justified ±8 caps how far this can go.
- **Break the constant.** Anchor on something whose lead over contact genuinely varies
  with the shot (take-back for a full swing vs. a blocked return or volley), so no single
  subtraction fits.
- **Widen the vocabulary** so blind guessing pays less than a 2-way coin flip.

Until one of these lands, the honest status of this task is *uncalibrated, with a known
audio shortcut that outperforms the intended solution path.*

## Why the bar should hold

*Localization.* 211 strokes across 123875 frames, each to be placed within ±8 frames on
an anchor that is deliberately not the salient moment. See the take-back table above.

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
