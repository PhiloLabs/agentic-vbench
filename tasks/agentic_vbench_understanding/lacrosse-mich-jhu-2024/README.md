# mich-jhu-2024-lacrosse-goal-ledger

**Family:** `agentic_vbench_understanding` · **Proposal issue:** [#72](https://github.com/PhiloLabs/agentic-vbench/issues/72)

Reconstruct the ordered goal ledger of a full men's college lacrosse game from a
silent, graphics-free broadcast: every goal in sequence with its team, scorer's
jersey number, whether it was assisted, and (implicitly, from the ordered team
sequence) the running score after it.

## Layout

```
task.toml                     # harness config (family layout)
SPEC.md                       # task spec card (every field filled + measured)
environment/Dockerfile        # bakes the video at build; SHA-256 mismatch FAILS the build
environment/{roster,schema}.json
steps/solve/instruction.md    # the agent-facing prompt
steps/solve/workdir/setup.sh  # copies baked materials into /workspace/materials
steps/solve/solution/solve.sh # oracle (answer key mounted only for this step)
steps/solve/tests/judge.py    # deterministic grader (pure stdlib)
steps/solve/tests/test.sh     # verifier entry point
calibration/                  # scores.md, raw trajectories, scorer crops, run-pack
```

## Task material (agent-visible at `/workspace/materials/`)

- `game.mp4` — the full game (~102 min, 720p, silent). The **entire lower third
  is blacked out**: no scoreboard, no score cards, no player-bio lower-thirds.
  Fetched at build time from a pinned URL and verified against the pinned
  SHA-256; a mismatch fails the build.
- `roster.json` (closed set of valid jersey numbers per team colour) and
  `schema.json`. Teams are referred to only as NAVY / WHITE.

## Ground truth & provenance (verifier-side: `steps/solve/tests/`)

- Source: the game's official NCAA box score / play-by-play (goals in order,
  scorer, assister, quarter+clock), numbers mapped via both teams' official
  rosters. Machine-logged; no hand annotation of the answer.
- **Video-derived key:** every logged goal was audited frame-by-frame against
  this exact masked encode by key-aware auditors (26/26 located in key order;
  inter-goal spacing matches the key's clock gaps). One deviation under the
  mechanical visibility rule: **goal 18's assist** (box score: #40) has no
  visible assisting pass (crease-scramble, no replay) → recorded unassisted;
  `assister_boxscore` preserved in `ground_truth.json`. 26/26 scorers were
  certified readable by a careful human (three via marginal reads, two via a
  documented identity chain — the opposing goalie scored coast-to-coast twice).
  Goal-moment crops at the baked 720p in `calibration/scorer_crops/` show four
  scorer numbers reading above the mask line (review comment #2).
- Jersey numbers repeat across teams; the scored key is always (team, number).

## Scoring (`steps/solve/tests/judge.py`)

Pure-Python, deterministic, no LLM/VLM, no network.

- **Headline reward** = F1 over the ordered goal ledger on the tuple
  **(team, scorer, assisted?, running-score-after)**, matched by an
  order-preserving one-to-one alignment (LCS) so one miss desyncs the running
  score from that point without index-zeroing prior matches.
- The running score is derived from the predicted team sequence — the agent
  must find every goal, in order, correctly attributed; over/under-counting
  cascades. `assisted?` is binary (assister null vs non-null); the passer's
  number is a diagnostic only (the audit found it unreadable for ~half the
  assisted goals — requiring it would break oracle-1.0).
- Diagnostics reported, never blended: assister-number F1, lenient
  (team+scorer) F1, penalty ledger F1.
- Anchors: **oracle 1.0 · empty 0.0 · constant-guess 0.0**.
- Gaming stress-test, reported in `calibration/scores.md`: post-processing the
  strongest measured output with the optimal all-assisted base-rate guess
  reaches only 0.0678 — the guard is the sequence reconstruction itself.

## Measured results (details + trajectories: `calibration/`)

| run | reward | tool-call turns |
|---|---|---:|
| Codex codex-cli 0.144.6, gpt-5.6-sol (xhigh) | **0.0** | 112 |
| Claude Code CLI 2.1.216, claude-opus-4-8 (zero web attempts) | **0.0339** | 1263 |
| Antigravity 2.0, gemini-3.6-flash (high) | **0.0** | 87 |
| blind strong-agent probe (masked video) | 0.000 | 99 |
| blind probe, counting-coached | 0.034 | 97 |
| no_media | 0.0 | — |
| no_media, adversarial (game named outright, answer from recall) | 0.0 | — |
| single_frame | 0.0 | — |
| frame_dump_no_tools (102 frames @ 1/60 s) | 0.0 | — |

An independent full-game blind reconstruction (6 parallel agents, audited **zero**
web lookups) scored **0.035**, overcounting 31 vs 26 goals (team split 14/17 vs
11/15) — corroborating the official row. Supporting evidence (fanned-out
multi-agent + mechanical merge), not a clean single-agent row.

All three harnesses are < 0.10 over > 50 tool-call turns; one raw trajectory per
harness is committed under `calibration/rollouts/`.

## Media prep pipeline (reproducible)

1. Source: public full-game broadcast upload (720p).
2. `ffmpeg -vf "drawbox=x=0:y=505:w=1280:h=215:color=black:t=fill" -an`
   → masks all lower-third graphics (scorebug, score cards, bio cards) and
   strips audio; H.264 CRF 23.
3. SHA-256 pinned; bake at build time (worked-example posture).
4. **Masking audit** (review comment #1): the full game was scanned at 10 s
   sampling across all four quarters, halftime, and the quarter breaks — the
   scorebug and all replay score/bio cards sit inside the masked band, no score
   appears outside it, and the stadium scoreboard is never in shot. The only timing
   display outside the band is a field-level 80-second shot clock (possession timer;
   it carries no score or goal information).

## Why hard (measured, not argued)

Reading one scorer is easy; reconstructing the full 26-goal sequence is not.
In a condensed, celebration-dense broadcast with no scoreboard, every measured
agent mis-counted (27–33 goals vs 26; team splits off by 3–5), desyncing the
running score. Difficulty is reconstruction under sustained tracking — not
perception tricks, not hidden information (the oracle audit proves every scored
fact is humanly recoverable from these pixels).
