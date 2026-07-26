---
title: Spec Card — Super Bowl LI referee-announced player-foul timeline
summary: Reconstruct every referee-announced player foul (quarter, clock, type, jersey number, team) from the full broadcast.
read_when: Reviewing this task.
---

# Spec Card

```yaml
task: agentic_vbench_understanding/ne-atl-2017-super-bowl-li-penalty-timeline

# 1. What kind of thinking does this task need?
cognitive_level: understanding   # relate a spoken announcement to an on-screen clock, across a long game

# 2. Which modalities are REQUIRED (not just present)?
modalities_required:
  video: the game clock exists only in the on-screen score bug; the referee never states it.
  audio: the penalised player's jersey number is stated only by the referee's microphone;
         it appears in no on-screen graphic (verified by frame inspection).

# 3. The exact question and output schema.
question: Reconstruct every referee-announced player foul in Super Bowl LI.
output_schema: >
  {"penalties":[{"quarter":int(1-5), "clock":"mm:ss", "type":<closed vocab>,
  "player_number":int, "team":"NE"|"ATL"}]}; clock tolerance 5 s; compound exact match.

# 4. Evidence chain: far-apart moments in different modalities.
evidence:
  - "t~5190s (Q3 1:30), audio: referee 'holding, number 70, offense' -> #70 / offensive holding"
  - "t~2500s (Q2 5:16), video: score bug shows the quarter and clock for that foul"
  - "t~8420s (OT 11:18), audio+video: PI 'against number 59' + OT clock on the bug"

# 5. Ground truth: value, source, tier, verification.
ground_truth:
  source: NFL official Game Book (nflgsis.com) penalty summary + roster for jersey numbers.
  tier: machine-truth
  verification: >
    cross-checked against nflpenalties.com (13 accepted penalties, 88 yards, 16 flags).
    Four announced jersey numbers independently verified by transcribing the broadcast
    audio: #70 Matthews (Q3), #23 Alford (Q2), #34 Poole (Q2), #59 Campbell (OT PI).

# 6. Scorer: deterministic code only.
scorer:
  metric: F1 over fouls; a TP requires type + jersey number + team + quarter, and clock within 5 s.
  oracle_reward: 1.0            # verified locally (pilot subset)
  null_reward: 0.0             # verified locally

# 7. Difficulty: MEASURED with a real strong-agent run.
difficulty:
  strong_agent_reward: PENDING   # requires GPT 5.6 Sol calibration (not yet run)
  tool_call_turns: PENDING
  agent_model: PENDING

# 8. Anti-shortcut ablations.
anti_shortcut:
  single_frame: PENDING
  video_only: PENDING   # type+team+clock OCR-able, but jersey number is not -> compound match should stay near 0
  audio_only: PENDING   # number+type audible, but no game clock -> cannot place a foul
  no_media: 0.0        # indicative proxy run: a no-media no-tools model recalled 0/13 penalties
  frame_dump_no_tools: PENDING

# 9. Input media.
input:
  url: https://archive.org/download/youtube-noLK78Hgq0A/noLK78Hgq0A.mp4
  sha256: ba2281d6293b3ee6a180decd508bb871de581841e6ea183ac17455c0344ba998   # verified, pinned in Dockerfile
  length_min: 143
  resolution: 1080      # verified: 1920x1080 by ffprobe/frame extraction
```

## Status

This card is filled for the parts that are **verified locally** and marked `PENDING`
where they require the maintainer's calibration stack (GPT 5.6 Sol) or steps not yet run.

**Ground truth is complete:** 13 referee-announced player fouls parsed from the official
NFL Game Book, jersey numbers from the Game Book lineups, kept in lockstep between
`judge.py` GROUND_TRUTH and the oracle `solve.sh`. Scope rule + 3 documented exclusions
in `PROVENANCE.md`. Still `PENDING`: the three-agent calibration (GPT 5.6 Sol) and the
media ablation runs, which require the agent/Harbor stack.
