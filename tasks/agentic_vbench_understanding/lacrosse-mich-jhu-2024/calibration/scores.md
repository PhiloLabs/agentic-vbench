# Calibration — `mich-jhu-2024-lacrosse-goal-ledger`

**Headline reward** = F1 over the ordered goal ledger on the tuple
**(team, scorer, assisted?, running-score-after)**, matched by an order-preserving
one-to-one alignment (LCS), computed by `steps/solve/tests/verify.py`.
Pure-Python, deterministic, no LLM/VLM judge, no network.

**Media (shipped):** `materials/game.mp4`, SHA-256
`7e53feeb327da479448203385e3b76016bf9c78f78422bb715a7f906b0429a34`
(full game, entire lower third masked, audio + metadata stripped). Pinned in
`materials/game.mp4.sha256`.

## Anchors

| output | reward |
|---|---:|
| oracle | **1.0000** |
| empty (`{}`) | **0.0000** |
| constant-guess (most-common team+scorer ×26) | **0.0000** |

## Agent calibration (network-isolated; one raw trajectory per harness)

| harness | version | model | reasoning | reward | tool-call turns | trajectory |
|---|---|---|---|---:|---:|---|
| Codex | codex-cli 0.144.6 | gpt-5.6-sol | xhigh | **0.0** | 112 | `rollouts/codex_gpt56_trueblind_xhigh.jsonl` |
| Claude Code | CLI 2.1.216 | claude-opus-4-8 | default | **0.0339** | 1263 | `rollouts/claude_opus48.jsonl` |
| Antigravity | 2.0 | gemini-3.6-flash | high | **0.0** | 87 | `rollouts/antigravity_gemini36_flash_transcript.jsonl` |

All three clear the bar (< 0.10) over > 50 tool-call turns. Every turn count is
recomputable from the committed trajectory: Codex = 112 `command_execution` items;
Claude = 1263 `tool_use` blocks (Read 905, Bash 330, Agent 13, Write 14, Edit 1);
Antigravity = 87 `tool_calls` (manage_task 30, run_command 26, schedule 15,
write_to_file 13, view_file 2, replace_file_content 1).

**Failure mode is identical across harnesses:** each miscounted the goal total, so
the running score desynced and cascaded. Claude over-counted (33 goals, 16/17 split
vs the true 26, 11/15). Antigravity predicted the exact right count (26/26) and still
matched **0** tuples (lenient team+scorer F1 0.1923).

**Audits.** No web or search tool calls, no external URLs, and no access to the
answer key or ground truth in any of the three trajectories. Claude: zero
WebFetch/WebSearch attempts across 1263 calls. Codex: the only URLs present are the
model API endpoint (`chatgpt.com/backend-api`, i.e. inference). Antigravity: its tool
set contains no web tool; that run was executed from the unpacked kit directory
rather than the isolated workspace `runpack/stage_workspace.sh` creates, and it
invoked `verify.py` on its own output twice, scoring 0.0 both times.

*Trajectory note:* `claude_opus48.jsonl` is the raw stream-json trajectory with the
base64 frame images stripped from `Read` results (placeholders retained, e.g.
`<frame image stripped: NNNNN B base64 png from game.mp4>`). Every tool call,
argument, reasoning step and text output is intact; only the re-encoded video pixels
were removed, taking the file from 160 MB (over GitHub's 100 MB limit) to 24 MB. The
Codex and Antigravity trajectories are byte-unmodified.

## Anti-shortcut ablations

| ablation | reward | note |
|---|---:|---|
| `no_media` (brief + roster only) | **0.0** | agent produced a "statistically typical game"; zero tuples matched |
| `single_frame` | **0.0** | only the two jerseys and the venue are inferable; the ledger is necessarily fabricated |
| `frame_dump_no_tools` (102 frames @ 1/60 s) | **0.0** | finds only celebration aftermaths (11-goal ledger vs 26) — agency (seek/zoom) is load-bearing |

**Gaming stress-test.** Post-processing the strongest measured output with the
optimal all-assisted base-rate guess reaches **0.0678** — still under the bar. The
binary `assisted?` flag cannot be gamed past 0.10 because the guard is the sequence
reconstruction itself, not the flag. Reported here in full.

**Recognizability.** In the `single_frame` ablation the agent identified the venue
from one frame. Team identity is painted on the field and printed on the jerseys and
cannot be masked without destroying the task. The no-recall defense is the posture of
the accepted volleyball tasks (whose games are named outright): the no-web/no-lookup
calibration rule, enforced in the harness and verified by raw-trajectory audit, plus
the measured `no_media = 0.0` — knowing which game this is yields nothing, because
the goal-by-goal ledger is in no public record at the scored granularity.

## Oracle certification (key-aware, both halves, on the shipped masked encode)

- **26/26 goals** locatable in key order; inter-goal video spacing matches the key's
  game-clock gaps throughout (sequence integrity verified).
- **26/26 scorers derivable.** First half 13/13 direct. Second half: g14 "34"
  (~2812.5 s), g19 "9" (hero shot 4350–4360 s) and g24 "MICHIGAN 19" (5456.75 s) are
  direct reads; g15 and g26 are the same player (the Michigan goalie, who scored
  coast-to-coast twice) via a documented identity chain — matching "…ONSO" nameplate
  on both celebrations, goalie gear in both replays, a clean "MICHIGAN 40" chest read
  at 5461.0 s, and an "x0" partial on the scorer at 5861.1 s. All agree with the key.
  Goal-moment crops at the baked 1280×720 are in `scorer_crops/`.
- **Assist binary observable** for all goals. Across the 20 box-score assists the pass
  is visible for 19; **goal 18** has no visible assisting pass (crease scramble, no
  replay), so the mechanical visibility rule applies — g18 is recorded unassisted in
  the video-derived key, with `assister_boxscore` preserved in `ground_truth.json`
  (the soccer buildup-null precedent).
- **Running score derivable** from the ordered team sequence.

The full assister *number* is deliberately not required: the key-aware audit found the
passer's number unreadable for roughly half the assisted goals, so requiring it would
break oracle-1.0. `assisted?` is scored as a binary; the passer number is reported as
a diagnostic only.

## Masking audit (full 102 min)

The whole game was scanned at 10 s sampling across all four quarters, halftime, and
every quarter break. The score-bearing graphics — the persistent scorebug and the
replay score/bio cards — all sit inside the masked lower third; no score appears
outside the band, and the stadium scoreboard is never in shot. The only timing display
outside the band is a field-level **80-second shot clock** (the "57/47/37/27/17"
countdown at each end) — a possession timer carrying no score or goal information.

## Adversarial recall ablation (PR #88 review item 2) — 2026-08-24

Stronger form of `no_media`: the agent is **given the exact game identity** —
"Michigan at Johns Hopkins, 2024-03-30, Homewood Field, Big Ten", with the
NAVY=Michigan / WHITE=Johns Hopkins mapping — **no video**, and is explicitly
instructed to reconstruct the ledger from its own recall of that specific game.
This simulates perfect identification off the pixels (venue, uniforms, wordmarks).

| condition | reward | pred goals | note |
|---|---:|---:|---|
| adversarial recall (identity given, no video, no web) | **0.0000** | 26 (NAVY 14 / WHITE 12) | 0 tuples matched; lenient team+scorer F1 0.1923 |

Truth: 26 goals, NAVY 11 / WHITE 15. The model produced a complete, schema- and
roster-valid ledger with the **exact right goal count** and still matched zero
tuples. It also called the winner backwards (Michigan 14-12 vs the true Hopkins
15-11) — a box-score lookup would have gotten the result right, so this is
behavioural evidence that no external lookup occurred. The model's own report:
"I do not actually recall this specific game… this is an inferred, constructed
ledger, not a retrieval."

**Conclusion:** identifying the game yields nothing. The goal-by-goal ledger at
the scored granularity (ordered team + scorer + assisted-flag + running score)
is not recoverable from memory even when the game is named outright.
