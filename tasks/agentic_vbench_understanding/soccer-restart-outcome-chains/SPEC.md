# Task Spec Card

```yaml
task: agentic_vbench_understanding/soccer-restart-outcome-chains

# 1. What kind of thinking does this task need?
cognitive_level: understanding
# Spotting one action in one shot is perception. The ledger is not: 216 entries across 107
# minutes, each with the team that performs it held consistent for the whole match, and
# classes told apart by what surrounds the moment. A free kick is direct only with a shot at
# goal or a wall, a foul belongs to the side that commits it, a card follows a foul and a
# goal is followed by a kick-off.

# 2. Which modalities are REQUIRED?
modalities_required:
  video: "Every action, its moment and the team that performs it are only in the pixels.
          The only on-screen text is the clock, the score and the occasional caption."
  audio: "not used. The baked file is YouTube's video-only stream, so there is no
          commentary to leak an answer."

# 3. The exact question and output schema.
question: "For every visible action of the seventeen SoccerNet-v2 classes in the full
           broadcast of one Bundesliga match, report (t, action, team)."
output_schema: >
  {"sequence": [{"t": <seconds from clip start>,
                 "action": one of the seventeen SoccerNet-v2 class names,
                 "team": "home"|"away", or "none" for "Ball out of play"}, ...]}
  Scored with a 1 s time tolerance, stated in the prompt; see the scorer.

# 4. Evidence chain: far-apart moments the answer depends on.
evidence:
  - "t ~ 1894.8 s: a home corner, two home shots on target at 1896.1 and 1897.4, and the
     goal at 1897.7. Four entries inside three seconds, each a different class, each needing
     the frames around it."
  - "t ~ 5121.3 s: an away direct free-kick that is also a shot on target, and the goal at
     5122.2, 54 minutes of clip later. The kick counts as direct because it is a shot, the
     fact the prompt's definition turns on."
  - "All five yellow cards go to the away side, each within 14 s of an away foul, so the
     team field follows the offender and not the side that benefits."
  - "216 such actions across both halves, about 2.3 per minute of play. The answer is the
     full set, so no single lookup and no single moment suffices."

# 5. Ground truth: value, source, tier, verification.
ground_truth:
  source: "SoccerNet-v2 germany_bundesliga/2016-2017 '2017-03-04 - 17-30 Dortmund 6 - 2 Bayer
           Leverkusen', the published multi-annotator Labels-v2.json, pinned at
           SoccerNet/SN-Labels revision 8e01649fe968da9f541c91019b65b3028b2425fc. The labels
           are public and need no NDA."
  tier: machine-truth
  verification: "provenance/build_gt.py keeps every annotation marked visible, 216 of the
                 match's 260 and 62 of them Ball out of play, as (clip time, label, team),
                 with 'not applicable' written 'none'. It asserts that the derived key equals
                 judge.py's and solve.sh's, that the oracle scores 1.0 and an empty submission
                 0.0, that the judge's greedy matcher equals brute force, and that the prompt's
                 two examples sit at least 54 s from every key entry. The prompt's class
                 definitions follow SoccerNet-v2's annotation guidelines. Its team rule was
                 checked against this match's own labels: every free kick within a minute of
                 a foul, 22 of the 29, went to the other side, and the goals split 6-2 as the
                 result did."
  timeline: "SoccerNet positions are milliseconds inside each half video, and the baked clip
             is a different recording of the same broadcast, so each half gets one offset,
             measured by provenance/align_halves.py from SoccerNet's own public shot-change
             log (Labels-cameras.json) against ffmpeg's scene score: half 1 at 350.006 s,
             half 2 at 3396.705 s. At a scene threshold of 0.12 all 74 annotated logo
             transitions land on a detected change, with the median residual inside 0.02 s
             in the early, middle and late third of each half. Moving either offset by 2 s
             drops the matches from 33 and 43 to between 1 and 4. Annotated hard cuts sit a
             consistent 0.30-0.35 s before the detected cut, an annotation convention well
             inside the 1 s tolerance. At the mapped frames the on-screen match clock reads
             the annotated game time."

# 6. Scorer: deterministic code only.
scorer:
  metric: "F1 for each action class, averaged over the fourteen classes in the key, the way
           SoccerNet averages its spotting metric over classes (steps/solve/tests/judge.py, pure
           stdlib). A prediction is a true positive when a key entry of the same action and
           team lies within 1 s, one to one, and inside each (action, team) group a greedy pass
           in time order finds a largest matching. official_score = the class mean."
  oracle_reward: 1.0        # measured, inside the built image
  null_reward: 0.0          # measured, inside the built image (empty submission)

# 7. Difficulty: measured with real strong-agent runs.
difficulty:
  strong_agent_reward: "0.0663 Codex, 0.0901 Claude Code, 0.0333 Antigravity, see calibration/scores.md"
  tool_call_turns: "185 Codex, 405 Claude Code, 351 Antigravity"
  agent_model: "Codex (GPT 5.6 Sol), Claude Code (Opus 4.8), Antigravity (Gemini 3.6 Flash)"

# 8. Anti-shortcut ablations. Target: each <= 0.15.
anti_shortcut:
  single_frame: "0.0000, measured with GPT 5.6 Sol at xhigh given one still at t = 1786 and
                 no tools. It listed one action."
  video_only: "n/a (no audio in this task)"
  audio_only: "n/a (no audio in this task)"
  no_media: "0.0000, measured with GPT 5.6 Sol at xhigh given the prompt alone. It listed two
             actions. Blind submissions as long as the key do no better than 0.0511, the best
             of 400 random draws from the key's own distribution, which average 0.0039. The
             key's most common pair repeated 216 times evenly over the halves scores 0.0041."
  frame_dump_no_tools: "0.0000, measured with GPT 5.6 Sol at xhigh given 128 frames on 8
                        contact sheets and no tools. It listed eight actions."

# 9. Input media.
input:
  url: "https://www.youtube.com/watch?v=U-Glif5abSY, the Bundesliga's own full-game upload,
        format 136, baked by environment/Dockerfile with a pinned yt-dlp"
  sha256: "7648b622c196ca5c844eb6162dfda2532d8e46ced99728f720f62fb6d3d695e2"
  length_min: 107.1
  resolution: 720
```

## Why the match changed

The version merged in #51 used Mainz 05 1-1 Borussia Dortmund. Its only full-length copy
is SoccerNet's, and SoccerNet distributes its broadcasts under an NDA that forbids sharing
them, so that version could never carry a public URL and its Dockerfile kept a placeholder.
This version moves to a SoccerNet-v2 match whose full broadcast the league itself has
published.

## Why the question changed, and why the tolerance is 1 s

The first contract on this match asked for every visible restart as
`(t, restart_type, team, outcome)` and did not survive calibration inside the built image. A
Codex run scored 0.3529 against the family's 0.10 ceiling, almost all of it on throw-ins, and
its prompt gave direct and indirect free kicks their rulebook meaning where SoccerNet's labels
mean shot intent. The action ledger replaced it.

The ledger's tolerance is 1 s, the tightest window SoccerNet's own tight average-mAP uses,
tightened after the ledger's first runs. Every artifact from the restart contract and from
those first runs is archived under `provenance/superseded-restart-contract/`,
`provenance/superseded-2s-tolerance/` and the matching folders in `calibration/rollouts/`,
and `calibration/verify_scores.py` regrades each of them with the scorer it was run under.
