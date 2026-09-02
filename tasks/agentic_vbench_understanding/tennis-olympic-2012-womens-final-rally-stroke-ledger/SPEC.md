---
title: Task Spec Card
summary: Verifiable claims for the TenniSet V006 tennis rally-stroke-ledger task.
read_when: Reviewing the task's media, scorer, ground truth, or calibration evidence.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/tennis-olympic-2012-womens-final-rally-stroke-ledger

# 1. What kind of thinking does this task need?
cognitive_level: understanding
# Spotting that a player swung is perception, and the task does not stop there. The
# scored anchor is the take-back, ~10 frames BEFORE contact - contact is the salient
# moment (it is what the audio marks and what a sampled frame shows) and logging it
# scores zero, so the agent has to reason backwards from the salient event to the one
# being asked for. Player identity is not readable from screen position: the camera
# never moves and the two trade ends through the match, so identity has to be carried
# across changeovers. And the ledger must exclude two things that look like rally
# strokes - the 112 serves, and every stroke the broadcast shows again in replay -
# which are separable only from surrounding context, not from the swing itself.

# 2. Which modalities are REQUIRED?
modalities_required:
  video: "Every scored field - player, forehand vs backhand, and the take-back frame -
          lives only in the pixels, and the take-back is a ~10-frame window that has to
          be found by stepping frames rather than by sampling."
  audio: "Not required, but load-bearing in practice: the racquet strike is an audible
          transient and is by far the cheapest way to locate candidate strokes in
          a 123875-frame video. It cannot answer any scored field on its own - it gives
          neither player nor side, and it marks contact, which is ~10 frames after the
          frame being asked for."

# 3. The exact question and output schema.
question: "For every rally stroke played in an 82.6-minute broadcast of a women's
           singles tennis final, report (player, stroke, start_frame), where
           start_frame is the first frame of the take-back."
output_schema: >
  {"strokes": [{"player": <"Sharapova" | "Williams">,
                "stroke": <"forehand" | "backhand">,
                "start_frame": <int, 0-123874>}, ...]}
  Ordered by non-decreasing start_frame; frame 0 is the first frame, 25 fps.
  Scored with a +/-8-frame (0.32 s) tolerance on start_frame; see the scorer.

# 4. Evidence chain: far-apart moments the answer depends on.
evidence:
  - "frames 30749-30828, video: a 4-stroke rally in game 2. Sharapova is the NEAR player
     here although she was the far player in game 1 - the players change ends on the
     odd-game schedule - so player identity cannot be read off screen position and has
     to be re-established after every changeover. Verified frame by frame."
  - "frame 30773 vs frame 30784, video: the same stroke's take-back and its contact.
     30773 is the answer; 30784 is where the ball is struck and where the audio
     transient falls. The 11-frame difference exceeds the whole tolerance, so the
     distinction decides whether the entry scores at all."
  - "frames 36045-36120, video: a serve. It must NOT appear in the ledger, and it is a
     full swing at the ball by a player standing at her baseline - distinguishable from
     a rally stroke only by the surrounding point structure, not by the swing."
  - "frames 25857 (first rally stroke) to 117170 (last), video: 211 strokes spread over
     91313 frames, roughly 61 minutes apart end to end. The answer is the full ordered
     ledger, so no single lookup and no single moment suffices."

# 5. Ground truth: value, source, tier, verification.
ground_truth:
  source: "TenniSet, video V006 - the published event annotation (`annotation.json`,
           schema in `classes.txt`) for the London 2012 Olympic women's singles final.
           Kept verifier-side under steps/solve/tests/ with the builder that reads it.
           The scored key is 211 live-point strokes derived from its Hit track."
  tier: published-annotation (not independently human-verified)
  # The published Hit track contains 220 frame-level windows. The builder applies the
  # documented filter below and checks the resulting 211-entry key. These checks expose
  # structural contradictions; they do not constitute an independent manual relabel.
  verification: >
    (1) LIVE-POINT FILTER (asserted at build time): 9 Hit rows overlap Serve windows
        labelled Fault (8) or Let (1). Those rows describe the server's non-live swing,
        not a rally stroke, and are excluded. Every one of the 211 retained hits belongs
        to exactly one Point interval.
    (2) POINT STRUCTURE (asserted at build time): all 63 non-empty points begin with the
        receiver and alternate strictly between players, with zero violations.
    (3) COMPLETENESS SANITY CHECK (asserted at build time): 18 of 81 points contain no
        retained rally stroke. The longest is 165 frames against a median point duration
        of 168. This rules out a long empty point, but does not prove that every individual
        stroke was annotated.
    (4) SCORELINE: the 13 Game.Score values run 1-0..6-0 then 1-0..6-1 - a 6-0 6-1
        scoreline, the real result of this match - and Game.Server alternates strictly
        across all 13 games, so the annotation is anchored to the actual match.
    (5) OBSERVABILITY SPOT CHECK: two adjacent strokes were checked frame by frame
        against the video (frames 30773-30801 near, 30804-30820 far). In both, start
        lands on the first frame of the take-back, ~10-11 frames before contact. This is
        a two-stroke spot check, not full human verification of the ledger.
  # gt.json is not a verbatim copy of the published labels. Five transforms are applied
  # by calibration/build_ground_truth.py and documented at their definitions there:
  #   1. 9 Hit rows whose start lies inside a Fault/Let Serve window are EXCLUDED. They
  #      annotate non-live serve swings, including two inside double-fault Point windows.
  #   2. the 112 serves are EXCLUDED. Serve.start is not a repeatable physical instant:
  #      the interval from Serve.start to the return it draws is median 55 with sd 15.9
  #      (range 22-95), against sd 6.6 for the rally strokes. With an annotator-side
  #      spread of ~+/-16 frames, no viewer could hit a +/-8-frame tolerance on them,
  #      so scoring serves would charge the agent for guessing an annotator's habit.
  #      The Serve track stays in annotation.json and drives transform 1.
  #   3. the published `end` frame is dropped - a Hit window ends a median of 3 frames
  #      before the OPPONENT's next window begins, so it marks where the annotator handed
  #      the ball on, not an event of the stroke. Only `start` is scored.
  #   4. Hit.Type is dropped - 86% of the raw Hit track is one value (Topspin) and 12
  #      rows are
  #      labelled `Unsure`, which has no answer for an agent to find.
  #   5. the retained Hit rows are re-sorted chronologically with a total tie-break.

# 6. Scorer: deterministic code only.
scorer:
  metric: >
    F1 over strokes under an order-preserving one-to-one alignment (LCS-style DP).
    A true positive requires the exact player, the exact stroke class, AND
    |predicted start_frame - true start_frame| <= 8 frames (0.32 s at 25 fps).
    Pure Python stdlib; no model, no VLM judge.
    Tolerance safety: the tightest gap between any two consecutive strokes in the match
    is 17 frames, and the closest two strokes of the SAME class start 47 frames apart,
    so the alignment is well defined with a wide margin. Asserted at build time against
    the judge's own constant.
  oracle_reward: 1.0
  null_reward: 0.0        # measured, empty submission {"strokes": []}

# 7. Difficulty: measured with a real strong-agent run.
difficulty:
  strong_agent_reward: 0.083832
  tool_call_turns: 61
  agent_model: gpt-5.6-sol (high reasoning; Codex CLI 0.150.1; Harbor 0.22.0)

# 8. Anti-shortcut ablations.
anti_shortcut:
  # Measured 2026-08-26/27 with Codex CLI 0.149.1 / gpt-5.6-sol, high reasoning, same
  # harness as the calibration row. Reproduce with calibration/runpack/.
  single_frame: 0.0       # submitted 1 stroke, at the very frame it was handed, and got
                          # its CLASS wrong (key: Sharapova forehand @30773; said backhand)
  no_media: 0.0           # agent declined to fabricate and submitted {"strokes": []};
                          # see the caveat in calibration/scores.md
  video_only: 0.090909    # audio stripped; 207 strokes over 77 tool-call turns and 19
                          # true positives -- ABOVE the full-media calibration row
                          # (0.083832); see calibration/scores.md
  audio_only: 0.150685    # on the edge of the <= 0.15 bar (over by 0.000685), and beats
                          # the full-media row (0.083832). Audio onset detection minus a
                          # CONSTANT 10 frames clears the take-back tolerance; player and
                          # class are then guessed from alternation and a 3:2 forehand
                          # prior. See calibration/scores.md.
  frame_dump_no_tools: 0.0  # 83 frames (one per 60 s) in the prompt, read-only sandbox,
                            # 0 tool calls; returned {"strokes": []} without attempting.
                            # Structurally unwinnable at this sampling -- see scores.md

# 9. Input media.
input:
  url: "https://drive.usercontent.google.com/download?id=1w1R6R6BAa_9K-he5nqygT5Bvb5CsyKhT&export=download&confirm=t"
  sha256: 76e3fa2d0905555e084b9bfd003add1c855a8fb4e8da49c60d5795f0c2e4e620
  length_min: 82.6        # 4955.000 s, 123875 frames at 25.000 fps
  resolution: 720         # 1280x720, H.264; AAC stereo 44.1 kHz audio
```

## Open items for reviewers
1. **Agent calibration is incomplete.** Codex CLI with `gpt-5.6-sol` at high reasoning
   scored 0.083832 in 61 tool-call turns: enough interaction, and below the required
   `< 0.10` real-agent ceiling. That row scored 0.107784 and missed the ceiling under the
   old +/-10-frame tolerance; it clears at the +/-8-frame tolerance the task now ships,
   because four of its 18 matched strokes were pinned 9 frames after the take-back.
   All five ablations in section 8 are now measured.

   **Claude Code CLI with `claude-opus-4-8` at high reasoning scored `reward = 0.0` in 88
   tool-call turns** — well clear of the `> 50` effort floor, and the lowest score any
   real agent has recorded on this task. Read that number with its cause attached: the run
   hit the 45-minute agent cap (`AgentTimeoutError`) while still mid-pipeline and never
   wrote `output/solution.json`, so the zero is the verifier's response to a missing file
   rather than to a bad ledger. Across 88 turns it built a genuine detection stack — audio
   onset detection, ball tracking, frame montages for player identification, end/side
   classification — and emitted zero stroke entries. Two earlier attempts also produced no
   ledger: one where no credential reached the container, one aborted on a provider rate
   limit (HTTP 429, org monthly spend cap) at 32m 20s. A reviewer who wants a *scored*
   Claude row should repeat the run with a larger `--agent-timeout-multiplier` than the
   0.25 used here to match the Codex row; the task's own `timeout_sec` is 10800.

   **Antigravity / `gemini-3.5-flash` is unrun: we do not hold credentials for it.** This
   is a gap in the evidence, not a result — no inference should be drawn about how that
   harness would score. A reviewer with Antigravity access is asked to run it through
   Harbor against the shipped image and fill the row in `calibration/scores.md`.

   The deterministic scorer anchors in section 6 are measured and reproducible from this
   repo with no video.

2. **Serves are excluded, and that is a real narrowing.** Dropping the Serve track cost
   the task its cleanest cross-event field (`serve_in` vs `serve_fault` is decided by
   later frames) and weakened the case for audio being *required* rather than merely
   useful. It was still the right call — see transform 2 above; the alternative was
   shipping 112 events that no viewer could hit. If a reviewer wants the serve content
   back, the honest route is a second annotation pass placing serve contact frames, not
   a looser tolerance on the published `Serve.start`.
