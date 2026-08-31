# Human baseline — can the minimap alone carry the full 5-tuple?

Raised in review of PR #75: are `minute_gain` / `leader_before` actually inferable
from a minimap-only video, or does the all-or-nothing scorer punish agents for an
unanswerable question? This is the human pass that answers it.

## Setup

- **Annotators:** 2 volunteer League of Legends players, Emerald rank (~top 15 % of
  the ranked ladder).
- **Input:** `minimap_vod.mp4` only — the exact video the agents get. No GT, no
  event list, no scoreboard, no killfeed, no gold, no clock.
- **Task given:** `steps/solve/instruction.md`, unchanged (the same prompt the
  agents received), including the `minute_gain` ≥300 / `leader_before` ≥1000
  thresholds.
- **Playback control:** the volunteers could pause, step frame by frame, and rewind
  freely — i.e. the same power over the video file that the agents' harness gives
  them (ffmpeg frame extraction, arbitrary seeking, re-inspection of any segment).
  Neither side was limited to a single linear watch, so the comparison isolates
  perception and board reasoning rather than playback affordances.
- **Scoring:** the shipped `steps/solve/tests/judge.py` against
  `gt/timeline_named_gt.json` — the same strict 5-tuple, ±3 s, F1 used for models.
  (GT = 111). (Pass date: 2026-08-25; the 0.79 is the average of the two
  annotators' individual answers, not a merged answer.)

## Result

| | human (Emerald volunteers) | best agent (gpt-5.6-sol @ Codex) |
|---|---|---|
| **strict F1 (`judge.py`)** | **0.79** | 0.058 |
| `type` + `entity` | near-perfect | 0.153 (identity+time only, G3) |
| `minute_gain` correct | ~85 % | — |
| `leader_before` correct | ~85 % | — |

Error structure: the misses are concentrated in the **early game**, before much
fighting has happened — the gold delta sits close to the ±300 / ±1000 thresholds
there, so a small misread flips the label. Once the game opens up, the volunteers
read the economy off tower/jungle control and one-sided teamfight conversions.

For reference, the majority-class priors in the GT are 52 % for `minute_gain`
(red 58 / blue 37 / equal 16) and 36 % for `leader_before` (blue 40 / red 40 /
equal 31), so ~85 % per field is well above prior-following guesswork.

## Why the scorer stays all-or-nothing

Both economy fields are ternary (blue / red / equal). Under a partial-credit
scorer that pays out per correct field, an answer can clear the 0.10 calibration
bar on guessed economy fields alone — the credit is no longer attributable to
perception or board reasoning, which is exactly what this task is meant to measure.
The human result shows the strict bar is reachable (0.79), so the 0.058 best-agent
score reflects a real capability gap rather than an impossible field.

`calibration/relax_eval.py` already isolates the economy fields' contribution as a
diagnostic (G1 → G2 → G3), which keeps that information available without turning
it into reward.
