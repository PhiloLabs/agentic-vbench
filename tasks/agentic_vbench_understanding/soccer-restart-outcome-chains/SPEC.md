# Task Spec Card — soccer-restart-outcome-chains

```yaml
task: agentic_vbench_understanding/soccer-restart-outcome-chains

# 1. What kind of thinking does this task need?
cognitive_level: understanding
# Not perception: localizing a restart is the easy part. The scored fields are the
# taking team (kit attribution held consistent across the match) and the outcome
# (following 15-30 s of play to see if a shot or goal results). Both are cross-moment.

# 2. Which modalities are REQUIRED?
modalities_required:
  video: "The taking team, the restart type, and the ensuing shot/goal are only in the
          pixels; no transcript or graphic lists them. Outcome needs 15-30 s of play
          after each restart, i.e. many frames, not one."
  audio: "not used"

# 3. The exact question and output schema.
question: "For every visible ball restart in a full 90-minute broadcast, report (t,
           restart_type, team, outcome)."
output_schema: >
  {"sequence": [{"t": <int seconds from clip start>,
                 "restart_type": 1|2|3|4  (throw-in|corner|direct-FK|indirect-FK),
                 "team": "home"|"away",
                 "outcome": 0|1|2  (none | shot within 15 s | goal within 30 s)}, ...]}
  Scored with |dt| <= 3 s time tolerance; see the scorer.

# 4. Evidence chain: far-apart moments the answer depends on.
evidence:
  - "t~=1362 s: a direct free-kick taken by the away side; the shot it produces arrives
     within 15 s -> outcome 1. Reading the outcome needs the seconds AFTER the restart."
  - "t~=4920 s: a direct free-kick that leads to a goal within 30 s -> outcome 2. A
     different restart, a different chain, ~59 minutes later in the clip."
  - "81 such restarts spread across the whole 90 minutes; the answer is the full ordered
     set, so no single lookup and no single moment suffices."

# 5. Ground truth: value, source, tier, verification.
ground_truth:
  source: "SoccerNet-v2 germany_bundesliga/2016-2017 Mainz 05 - Borussia Dortmund,
           published multi-annotator Labels-v2.json (free, no NDA)."
  tier: machine-truth
  verification: "provenance/build_gt.py transforms Labels-v2.json mechanically (restart
                 events -> t/type/team; outcome by a forward scan of the same log for a
                 Shot/Goal in the 15 s / 30 s window) and asserts verifier(oracle)==1.0.
                 81 visible restarts. Only visibility=='visible'; team=='not applicable'
                 dropped; tie-break (t, label)."

# 6. Scorer: deterministic code only.
scorer:
  metric: "Grounded order-preserving 4-tuple F1 (steps/solve/tests/judge.py, pure
           stdlib). A predicted restart is a true positive only if restart_type, team,
           and outcome all equal a GT restart AND |dt| <= 3 s, under a one-to-one
           order-preserving (LCS) alignment. official_score = F1."
  oracle_reward: 1.0        # measured
  null_reward: 0.0          # measured (empty submission)

# 7. Difficulty: measured with real strong-agent runs.
difficulty:
  strong_agent_reward: "0.0225 (Claude Code, Opus 4.8) / 0.0227 (Codex) / 0.0449
                        (Antigravity), all < 0.10. See calibration/scores.md."
  tool_call_turns: "110 / 120 / 120, all > 50."
  agent_model: "Claude Code (Opus 4.8), Codex, Antigravity"

# 8. Anti-shortcut ablations. Target: each <= 0.15. All measured; artifacts
#    (answer.json + reward.json + raw transcript) in provenance/ablations/measured/.
anti_shortcut:
  single_frame: "0.0 (measured, Claude Fable 5 given one representative frame, t=828).
                 The model read the frame well: it identified the corner and placed it
                 at t=826, 1.7 s from the true restart, with the right outcome, but
                 misattributed the taking team, which needs the match-long kit mapping
                 a single frame cannot give. Score 0.0."
  video_only: "n/a (no audio in this task)"
  audio_only: "n/a (no audio in this task)"
  no_media: "0.0247 (measured), best fixed guess from the answer-distribution prior,
             no video. Random guessing averages 0.0036. Both well under 0.15."
  frame_dump_no_tools: "0.023 (measured, Claude Fable 5 given 120 uniform frames, the
                        same count as the interactive tool budget, one shot, no tools).
                        It grounded 6 restarts in specific frames; 1 of 81 matched.
                        With ~45 s gaps the restart second cannot be pinned to 3 s,
                        so agency (choosing where to look) is what the task pays for."

# 9. Input media.
input:
  url: "PENDING, see the PR open question. SoccerNet's broadcast is NDA-restricted, not
        a pinnable public URL. Intended path is an anonymized >=720p derivative
        re-hosted on a public HF dataset (as in tasks #45/#47), baked per environment/Dockerfile."
  sha256: "PENDING (set when the derivative is hosted)"
  length_min: 90
  resolution: ">= 720 (target; SoccerNet 720p re-encode)"
```

## Open items flagged for review (Draft PR)

1. **Media hosting.** The one design decision, raised in the PR description. Is
   re-hosting an anonymized >= 720p derivative of the match on a public
   `agentic_vbench_understanding` HF dataset the accepted path for an NDA-restricted
   broadcast (the pattern used by the egocentric tasks #45 / #47), or is a fully public
   source preferred? Until settled, `environment/Dockerfile` carries a placeholder URL.
Everything else (prompt, oracle, deterministic verifier, the three-agent calibration
at all < 0.10 over > 50 turns, and all four anti-shortcut ablations, measured) is
complete and reproduces locally.
