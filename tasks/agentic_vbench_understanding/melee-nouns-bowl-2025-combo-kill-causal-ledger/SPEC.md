---
title: Melee combo-and-kill causal ledger task spec
summary: Evidence, machine ground truth, scoring, media, and measured calibration for the Nouns Bowl Melee task.
read_when: Reviewing or calibrating the Melee causal-ledger task.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/melee-nouns-bowl-2025-combo-kill-causal-ledger
cognitive_level: understanding

modalities_required:
  video: Hits, grabs, actionable resets, overlapping reversals, stock losses, and game boundaries require temporal gameplay analysis.
  audio: not used; the selected public representations are video-only adaptive streams.

question: Across ten games, reconstruct every Slippi-style conversion with at least four hits or a stock loss, including its attacker, starting victim stock, hit count, damage band, and terminal cause.
output_schema: '{"events": [{"game": 1-10, "attacker": "player tag", "victim_stock_before": 1-4, "hit_count": "integer >= 1", "damage_band": "light|heavy|devastating", "terminal": "escape|reversal|kill"}]}'

evidence:
  - t=00:00-06:22, games 1-3, Ferriswheel vs Zain; establishes the opening global game numbers and includes long punish strings and low-hit kills.
  - t=06:22-13:53, games 4-6, JoJo vs Bard; includes overlapping Captain Falcon/Fox conversions needed to distinguish reversal from escape.
  - t=13:53-25:09, games 7-10, Axe vs SRM13; includes a character switch, multi-hit moves, pummels, and the final stock/game boundary.

ground_truth:
  source: Ten public Slippi replay files from the Lunar Melee Database, matched to three public Nouns Bowl 2025 set VODs.
  tier: machine-truth
  verification: '@slippi/slippi-js 9.1.2 ConversionComputer plus deterministic post-processing; replay SHA256, player tags, characters, game count, and stage sequence are audited against the VODs.'

scorer:
  metric: Event-level F1 using exact order-preserving one-to-one matching over game, attacker, victim_stock_before, hit_count, damage_band, and terminal.
  oracle_reward: 1.0
  null_reward: 0.0

difficulty:
  strong_agent_reward: 0.0899
  tool_call_turns: 145
  agent_model: gpt-5.6-sol with high reasoning via Codex Desktop 0.144.2; local run, no Harbor rerun claimed

anti_shortcut:
  single_frame: not measured in the current submission
  video_only: not applicable as a degradation because the full task input is video-only
  audio_only: not applicable because audio is absent
  no_media: not measured in the current submission
  ocr_only: not measured in the current submission
  frame_dump_no_tools: not measured in the current submission

input:
  urls:
    - https://www.youtube.com/watch?v=3VJYGJ3KrZM
    - https://www.youtube.com/watch?v=tmZTwrLVceI
    - https://www.youtube.com/watch?v=44jQnPR24zM
  sha256: 02f18fd7f4796800eece0400b1b1f315a36778b57b9ef4a64d1b30aa3b539749
  length_min: 25.1531
  resolution: 720p
  frame_rate: 60 fps
```

## Ground-truth population

The verifier contains 104 events: 55 `kill`, 26 `reversal`, and 23 `escape`.
The accepted population spans all ten games and both players in each set. Exact
damage, move contacts, source replay hashes, frame ranges, and inclusion decisions
are retained in `tools/ground_truth_audit.json`.

## OCR resistance

The overlay exposes tags, timer, stocks, and current percent. It does not expose the
45-frame actionable reset, conversion boundaries, damaging-contact count, pummels,
multi-hit parts, summed conversion damage, or whether the victim began an
overlapping counter-conversion. OCR can help navigate the footage but cannot produce
the scored ledger without temporal gameplay analysis.

## Calibration qualification

Three local agent outputs have been measured below 0.10; see
`calibration/scores.md`. They are reported as the final current calibration. The
runs were outside Harbor and degraded-input ablations were not measured; no stronger
claim is made.
