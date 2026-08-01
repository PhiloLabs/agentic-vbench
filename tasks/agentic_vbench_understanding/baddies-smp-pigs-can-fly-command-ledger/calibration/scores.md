# Calibration — baddies-smp-pigs-can-fly-command-ledger

Deterministic event-level F1 (`steps/solve/tests/judge.py`) against the frozen 21-row
ground truth. Measured 2026-08-01 on the shipped 228-min bake, with the offline
`transcribe` tool present in every sandbox exactly as the image ships it.

**Verdict: this task does NOT clear the family's difficulty bar.** The strongest agent
scores 0.1875 against a `< 0.10` gate. The long-horizon gate and every ablation gate
pass. Everything below is as-measured; nothing was re-scored, re-tuned, or selected
after the fact, and the section "Why the ledger cannot be enlarged into the gate"
records a fix that was tried and did not work.

## Anchors

| run | reward | notes |
|---|---:|---|
| oracle | **1.0** | the frozen ledger submitted verbatim |
| empty | **0.0** | `{"commands": []}` |

## Strong agents (full evidence: 228-min video + audio + offline ASR + ffmpeg)

| harness | harness version | model | reasoning | score | tool-call turns | trajectory |
|---|---|---|---|---:|---:|---|
| Claude Code | 2.1.220 | Opus 5 | xhigh | **0.1875** | 115 | `rollouts/opus5-full.jsonl` |
| Claude Code | 2.1.220 | Opus 4.8 | default | **0.1379** | 51 | `rollouts/opus48-full.jsonl` |
| Codex CLI | 0.145.0 | GPT-5.6 Sol | xhigh | **0.0741** | 112 | `rollouts/codex-full.jsonl` |

Difficulty gate (`< 0.10`): **fails** for Opus 5 and Opus 4.8; passes for Codex.
Long-horizon gate (`> 50` turns): passes for all three.

Antigravity (Gemini 3.5 Flash / 3.1 Pro) was NOT run — no API access on the machine
that produced these numbers. Opus 4.8 stands in as the third model, so the panel covers
two harnesses rather than the three the family names. That is a real gap, not a
substitution the family sanctioned.

## Ablations, Codex GPT-5.6 Sol xhigh (gate: `<= 0.15`)

| ablation | score | turns | what the agent had |
|---|---:|---:|---|
| video_only | **0.0000** | 92 | video with the audio stream **removed**; 4 rows submitted, 0 correct |
| audio_only | **0.0000** | 41 | the audio stream alone, no video anywhere; 6 rows submitted, 0 correct |
| no_media | **0.0000** | 4 | prompt + vocabulary only; submitted nothing |
| single_frame | **0.0000** | 5 | one still at 6843 s; submitted nothing |
| frame_dump_no_tools | **0.0000** | 3 | 20 stills every 684 s, no tools; submitted nothing |

The video-only and audio-only ablations use genuinely stripped media (`-an` / `-vn`),
not a prompt instruction to ignore a channel, so the agent cannot recover the missing
modality with ffmpeg.

**Both single-modality ablations score exactly zero, and both tried.** Video-only
submitted four rows over 92 turns and audio-only submitted six over 41; every one of
the ten was wrong. Neither channel alone yields a single correct chain, while agents
holding both score 0.0741–0.1875. The cross-modal requirement is therefore
unconditional — it needs no restriction of the ledger to make it hold.

That is a change from the earlier 15-row / 180-min configuration, where audio-only
scored **0.0952**, nearly matching the full-evidence agents, and the cross-modal claim
survived only if the ledger was restricted to rows whose fulfilment is never verbally
acknowledged. On the shipped 228-min ledger that filter is unnecessary: the transcript
alone gets nothing.

**The two single-modality runs fail in different ways, which is the stronger evidence.**
Detection F1 — credit for locating the right utterance, unscored — separates them:

| evidence | detection F1 | true positives | what it could and could not do |
|---|---:|---:|---|
| video only | **0.00** | 0 | could not even find that a request had been made |
| audio only | **0.30** | 0 | found 4 of the right requests, grounded none of them |
| both (Codex) | 0.37 | 1 | finds requests *and* begins to ground them |
| both (Opus 5) | 0.44 | 3 | — |

Audio-only's field diagnostics show exactly where it dies: `exec_time` accuracy 0.50 and
evidence-window IoU 0.25 among the rows it located. The transcript tells you **who asked
for what**; it never tells you **which second it got done**. The video supplies the
temporal anchor and nothing else supplies it. So the two channels are not redundant
sources that happen to both be weak — they carry different halves of the answer, and the
task cannot be completed from either half.

## Why the ledger cannot be enlarged into the gate

The obvious repair for "agent scores too high" is a bigger ground truth. It does not
work here, and the reason is worth recording because it is a property of the metric.

Event-level F1 is `2·TP / (P + N)` for predictions `P` and ground-truth rows `N`. When
`P` and `N` are the same order of magnitude, the reward tracks the agent's **solve
rate**, not the ledger size. Opus 5 solves 3 of 21 rows with 11 predictions; pushing it
under 0.10 requires `2·3 / (11 + N) < 0.10`, i.e. **N > 49** ground-truth rows. This
footage does not contain 49 defensible deferred requests, and the window was already
extended from 90 to 228 minutes in an attempt to get there — which raised the ledger
from 15 to 21 rows and raised Opus 5's score from 0.1053 to 0.1875, because the extra
footage gave it more solvable rows rather than diluting the ones it had.

**A second repair was measured and rejected.** The design hypothesis was that longer
command→execution gaps are harder, so raising the deferral floor should suppress the
agents. It does not: they solve long-gap rows as readily as short ones, so the filter
removes ground-truth rows and agent true positives at the same rate.

| deferral floor | GT rows | Opus 5 | Opus 4.8 | Codex |
|---:|---:|---:|---:|---:|
| 15 s | 18 | 0.2069 (3 TP) | 0.0769 (1 TP) | 0.0000 |
| 30 s | 14 | 0.1600 (2 TP) | 0.0909 (1 TP) | 0.0000 |
| 45 s | 12 | 0.0870 (1 TP) | 0.1000 (1 TP) | 0.0000 |
| 60 s | 11 | 0.0909 (1 TP) | 0.1053 (1 TP) | 0.0000 |
| 90 s | 10 | 0.0952 (1 TP) | 0.1111 (1 TP) | 0.0000 |
| 120 s | 9 | 0.1000 (1 TP) | 0.1176 (1 TP) | 0.0000 |
| 180 s | 6 | 0.1176 (1 TP) | 0.1429 (1 TP) | 0.0000 |

(These rows are all restricted to fulfilments with no verbal acknowledgement within
±25 s, so the audio-only shortcut is closed throughout.) No floor clears the gate for
both Claude agents. Opus 5's three solved rows have gaps of 36 s, 20 s and **549 s** —
it handles the nine-minute deferral as comfortably as the twenty-second one.

**So the deferral gap is not this task's difficulty axis.** What separates a solved row
from an unsolved one is whether the execution is *visually conspicuous* — a pig landing,
a block placed in an empty frame — not how long after the request it happened.

### That axis was then measured, not left as a suggestion

For every row: the fraction of pixels changing between exec−3 s and exec+8 s, minus the
same span 45 s earlier in the same scene, which baselines how much this camera moves
anyway. Deterministic; no model in the loop.

The 21 rows split by what the agents did — SOLVED (4), request LOCATED but execution
never grounded (4), never found at all (13). The third tier is confounded: those may be
missed because the *request* was missed. The first two are not — in both the agent heard
the request, so the only remaining difference is whether it could pin the execution.

| measure (baseline-corrected) | solved (n=4) | located only (n=4) | diff | exact p |
|---|---:|---:|---:|---:|
| fraction of pixels changed | **+0.289** | −0.259 | +0.548 | **0.043** |
| mean absolute difference | **+31.19** | −18.26 | +49.45 | **0.043** |

Ranked by footprint, all four solved rows land in the top half of the ledger and three
of the four located-only rows sit at the very bottom. **Every row below 0.35 — six of
them — was solved by no agent at all.**

Two honest limits. `n` is 4 vs 4, and 0.043 is close to the 1/70 = 0.014 floor that this
design can produce at all, so this is suggestive rather than settled. And the 0.35
threshold was chosen by looking at which rows went unsolved, so quoting it back on these
same 21 rows would be circular; it has to be validated on rows the measurement never saw.

### What building a revision on that axis would cost — surveyed, not guessed

The obvious next task selects footage on inconspicuousness. That was scoped rather than
assumed, and the scoping is discouraging enough to belong here.

The channel holds 326 videos / 1357 h, 136 on this server. Licence is per video, not per
channel — a sibling session in this same series is standard-licence — so each was checked
individually: **42 CC-BY sessions, 191 h**. Seven were pulled as audio only (~200 MB each
rather than ~3 GB), transcribed on SLURM (19,638 lines / 30 h, 99–100 % coverage), and
swept for deferred requests by 16 subagents.

Yield turns on whether the two players **co-build**, and almost none of them do:

| | shared project | parallel play | solo |
|---|---:|---:|---:|
| 10 new half-sessions | **0** | 7 | 3 |
| this session's 2 halves | **2** | 0 | 0 |

A positive control keeps that comparison honest: the identical strict sweep, re-run on
*this* session whose true ledger of 21 is known, returned 9 candidates — so the sweep has
about **43 % recall**, and raw sweep counts are calibrated rather than believed. Per
transcript line, this session still yields 3.2× the others.

Extrapolating at that recall, seven further sessions plus this one give roughly **11–13**
rows below the footprint threshold. At N=12 one lucky agent hit scores 2/(11+12) = 0.087
and still passes; two hits give 0.174 and fail. That is a one-hit margin — and the
hotel-era sessions, where this footage's collaboration actually happens, are almost all
standard-licence (2 of 18 are CC-BY, and one of those is already swept and is parallel
play). The axis is real. The footage to exploit it at scale is not obviously there.

## What the agents actually got wrong

Detection F1 — credit for merely locating the right utterance, not scored — is 0.44 /
0.41 / 0.37 for Opus 5 / Opus 4.8 / Codex, roughly three times their official score.
They find far more commands than they can pin. Field accuracy among located rows:

| run | speaker | target | action | object | executor | outcome | exec_time | evidence IoU |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Opus 5 | 1.00 | 1.00 | 0.86 | 1.00 | 1.00 | 1.00 | **0.57** | **0.57** |
| Opus 4.8 | 1.00 | 1.00 | 0.83 | 1.00 | 1.00 | 1.00 | 0.83 | **0.33** |
| Codex | 1.00 | 1.00 | 0.80 | 1.00 | 1.00 | 1.00 | 0.80 | **0.20** |

`object`, `executor` and `outcome` are perfect for every agent on every row they
located. The loss is concentrated in **when**: the execution timestamp and the evidence
window. They hear what was asked and they know who did it; they cannot say which second
it was done. That is the capability boundary this task actually measures, and it is a
narrower one than the task was designed to probe.

## Provenance and honesty notes

- **Contamination audit, re-run on these exact trajectories.** Zero of Opus 5's 115
  tool calls, Opus 4.8's 51, and Codex's 112 touch any answer-key path. A naive grep
  flags all of them, because the prompt's own prohibition list ("never open
  `ground_truth*`, `oracle*`, …") is echoed in the conversation history every turn;
  `media/annotation/audit_runs.sh` now inspects `tool_use` inputs only. That script
  previously reported "all clean" while auditing *zero* Opus runs — bare run names fell
  through its file-existence test — and it now fails loudly instead.
- **A leak was found and the affected runs were discarded**, not re-scored. An earlier
  `instruction.md` used a REAL ground-truth row as its worked example; Codex copied it
  verbatim for a free true positive. The example is now fictional (a request at 5500 s)
  and explicitly flagged as made up. Discarded logs are kept under
  `media/annotation/logs_leaked/` rather than deleted.
- **A phantom third player was caught and removed.** An on-screen tooltip reading
  "North Pick You" — a custom-named pickaxe, not a nameplate — was initially annotated
  as a player. It entered the closed vocabulary and caused one full Codex run to score
  0.0 by mislabelling the camera player in 17 of 19 rows. Verified from cropped frames
  and removed; the run was discarded.
- **Rows were never added to move a number.** A gap-fill sweep run specifically to
  enlarge the ledger had most of its candidates rejected on the evidence. Rejections
  included requests whose landing was confirmed but where the speaker turned out to be
  the executor (self-plan, not a request to another player).
- **One human reviewed the ledger** (the contributor, 2026-08-01, no corrections). The
  family asks for 2+ independent human annotators; a second, disinterested reviewer has
  not looked at it.

## Rollouts

`calibration/rollouts/` holds one unabridged trajectory per run, named for the tables
above. Submissions are in `media/annotation/runs/` (gitignored); per-row ground-truth
justifications, with the frames that settled each one, are in
`steps/solve/tests/ground_truth_provenance.json`.
