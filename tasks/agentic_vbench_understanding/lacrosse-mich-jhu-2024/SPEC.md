# Task Spec Card — `mich-jhu-2024-lacrosse-goal-ledger`

```yaml
task: agentic_vbench_understanding/mich-jhu-2024-lacrosse-goal-ledger

# 1. What kind of thinking does this task need?
cognitive_level: understanding
# The scored unit is not "find an event" but "reconstruct the ordered sequence".
# Each goal is graded on the running score after it, which is derived from every
# goal that came before, so the agent must order and relate events across the
# whole 102 minutes, not classify them locally.

# 2. Which modalities are REQUIRED?
modalities_required:
  video: The only source of the answer. The scoreboard, score cards and player-bio
    graphics are blacked out for the entire broadcast, so the team, the scorer's
    jersey number, whether a pass preceded the shot, and the goal count all exist
    only in the play on the field.
  audio: not used - the shipped encode is silent (audio stream stripped at build).

# 3. The exact question and output schema.
question: Reconstruct the ordered goal ledger of this lacrosse game - every goal in
  sequence with the scoring team, the scorer's jersey number, and whether the goal
  was assisted.
output_schema: |
  {"goals": [{"team": "NAVY"|"WHITE", "scorer": <int>, "assister": <int>|null}, ...],
   "penalties": [{"team": "NAVY"|"WHITE", "offender": <int>|null, "type": <enum>}, ...]}
  goals are chronological; jersey numbers must appear in roster.json for that team;
  assister null means unassisted. No clock times are required. Exact match, no
  numeric tolerance: a scored goal must match on team, scorer, assisted-flag, and
  the running score after it.

# 4. Evidence chain: far-apart moments the answer depends on.
evidence:
  - t=215s, video, goal 1 (NAVY #89) - fixes the start of the running score.
  - t=2812s, video, goal 14 celebration - scorer "34" is legible only in this
    post-goal close-up, not in live play.
  - t=5456s, video, goal 24 - "MICHIGAN 19" read in the celebration line.
  - t=5861s, video, goal 26 - its scored tuple carries the running score 11-15,
    which is only correct if all 25 earlier goals were found and attributed
    correctly; a single miss or extra anywhere before it invalidates this goal.

# 5. Ground truth.
ground_truth:
  source: the game's official NCAA box score / play-by-play (goals in order, scorer,
    assister, quarter + clock), with jersey numbers mapped via both teams' official
    2024 rosters.
  tier: machine-truth
  verification: all 26 logged goals were located frame-by-frame in this exact masked
    encode, in key order, with inter-goal video spacing matching the key's game-clock
    gaps; 26/26 scorers independently certified readable from the pixels; 19/20
    box-score assists have a visible assisting pass, and goal 18 (no visible pass,
    crease scramble, no replay) is recorded unassisted under a stated mechanical
    visibility rule, with assister_boxscore preserved in ground_truth.json.

# 6. Scorer: deterministic code only.
scorer:
  metric: F1 over the ordered goal ledger. A true positive requires the full tuple
    (team, scorer number, assisted-flag, running-score-after) to match, aligned by an
    order-preserving one-to-one LCS match so one miss desyncs the running score from
    that point without zeroing earlier matches. Pure stdlib, no LLM/VLM, no network.
  oracle_reward: 1.0
  null_reward: 0.0        # empty {} = 0.0; constant-guess (most common team+scorer x26) = 0.0

# 7. Difficulty: measured with real strong-agent runs.
difficulty:
  strong_agent_reward: 0.0        # Codex gpt-5.6-sol (xhigh); Claude opus-4-8 = 0.0339; Antigravity gemini-3.6-flash = 0.0
  tool_call_turns: 112            # Codex; Claude = 1263; Antigravity = 87 - all recomputable from the committed trajectories
  agent_model: codex-cli 0.144.6 / gpt-5.6-sol xhigh (primary); Claude Code CLI 2.1.216 / claude-opus-4-8; Antigravity 2.0 / gemini-3.6-flash

# 8. Anti-shortcut ablations.
anti_shortcut:
  single_frame: 0.0
  video_only: 1.0   # the task IS video-only by construction (silent encode); audio is not load-bearing
  audio_only: n/a   # no audio stream in the shipped file
  no_media: 0.0     # prompt + roster only. Also measured in a stronger adversarial form:
                    # handed the exact game identity ("Michigan at Johns Hopkins,
                    # 2024-03-30, Homewood Field") and told to answer from recall, a
                    # strong model produced a complete roster-valid ledger with the
                    # exact right goal count (26) and still scored 0.0 - it also called
                    # the winner backwards, confirming no lookup occurred.
  frame_dump_no_tools: 0.0   # 102 frames @ 1/60s, no tools - finds only celebration
                             # aftermaths (11-goal ledger vs 26); agency is load-bearing

# 9. Input media.
input:
  url: https://huggingface.co/datasets/yingshuow/agentic_vbench_lacrosse/resolve/main/game.mp4
  sha256: 7e53feeb327da479448203385e3b76016bf9c78f78422bb715a7f906b0429a34
  length_min: 102
  resolution: 720
```

## Notes

- **Masking.** The entire lower third is blacked out for all 102 minutes; the game was
  scanned at 10 s sampling across all four quarters, halftime and every quarter break
  to confirm no score-bearing graphic appears outside the band and the stadium
  scoreboard is never in shot. The only timing display outside the band is a
  field-level 80-second shot clock, a possession timer carrying no score or goal
  information.
- **Recognizability.** Team identity is painted on the field and printed on the
  jerseys and cannot be masked without destroying the task. The no-recall defense is
  the measured `no_media = 0.0` above (including the adversarial form where the game
  is named outright) plus the no-web calibration rule, verified by raw-trajectory
  audit of every calibration run.
- **Assister number.** Deliberately not required: the key-aware audit found the
  passer's number unreadable for roughly half the assisted goals, so requiring it
  would break oracle-1.0. `assisted?` is scored as a binary; the passer number is
  reported as a diagnostic only.
