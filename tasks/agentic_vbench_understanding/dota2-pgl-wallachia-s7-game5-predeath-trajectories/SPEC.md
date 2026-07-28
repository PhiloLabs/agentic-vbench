---
title: Dota 2 Game 5 pre-death trajectory task spec
summary: Evidence, logged ground truth, scoring, media, and calibration for the one-game task.
read_when: Reviewing or calibrating the Dota 2 Game 5 pre-death trajectory task.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/dota2-pgl-wallachia-s7-game5-predeath-trajectories
cognitive_level: understanding

modalities_required:
  video: Live-versus-replay context, HUD time, kill-feed attribution, hero identity, and three temporally separated minimap positions must be integrated.
  audio: not required

question: Reconstruct every victim's minimap trajectory during the ten seconds before each major-teamfight death in Game 5.
output_schema: '{"events": [{"game": 5, "clock": "MM:SS", "victim": "<player>", "killer": "<player>", "cell_10s_before": "A1-N14", "cell_5s_before": "A1-N14", "death_cell": "A1-N14"}]}'

ground_truth:
  source: OpenDota kill logs plus Valve replay 8730786393 parsed by gem-dota 0.5.0
  tier: logged
  event_rule: Deaths in maximal sequences of at least three deaths where every consecutive gap is below 15 seconds
  population: 39 deaths and 117 position labels
  sampling: Replay snapshots every 3 ticks; maximum requested-tick distance is 2 ticks or 0.067 seconds
  mapping: OpenDota game-coordinate normalization (coordinate - 64) / 127, quantized to 14x14; internal boundaries belong to the east/north cell
  crosscheck: All 39 deaths with independent OpenDota deaths_pos data agree at 14x14 cell level

scorer:
  metric: One-to-one F1 over the exact game/time/victim/killer/three-cell trajectory tuple
  clock_tolerance: 2 seconds
  diagnostics: Event, victim, killer, each position, and neighboring-trajectory F1
  oracle_reward: 1.0
  null_reward: 0.0

difficulty:
  current_codex_reward: 0.0
  current_claude_reward: 0.0256
  current_gemini_reward: 0.0
  target: less than 0.10 with more than 50 tool-call turns
  anti_shortcut: All 39 trajectories are distinct; only 5 events remain in one cell at all three times
  ablations:
    no_media: 0.0
    single_frame: 0.0
    frame_dump_no_tools: 0.0
    audio_video_split: not applicable because the task input is silent video
  codex_run: GPT-5.6 Sol, high reasoning, 195 tool calls, 37 minutes agent runtime
  claude_run: Claude Opus 4.8, xhigh reasoning, 762 tool calls including subagents, 3 hours 58 minutes total runtime
  gemini_run: Gemini 3.5 Flash, high reasoning, 137 tool calls, 17 minutes 39 seconds total runtime
  calibration_status: Oracle, null, identity-only, all required anti-shortcut ablations, and clean exact-prompt runs for Codex, Claude, and Antigravity pass

input:
  url: https://www.youtube.com/watch?v=EjVZaHmDPlw
  source_range_s: 10973-14088
  source_sha256: 0a190d96fbef22d6c2b9da40097820b63f90eea5956925c8f09d486cd84f7d86
  length_min: 51.917
  resolution: 720p
  frame_rate: 30 fps
  codec: H.264
```

## Verifier contract

Only a complete three-point trajectory contributes to reward. Per-field components
are diagnostics and do not add partial reward. Invalid objects remain in the
prediction denominator, preventing schema errors from improving precision.

For either raw game-coordinate axis, the thirteen internal boundaries are
`64 + 127k/14` for `k = 1..13`. Intervals are closed on their west/south edge and
open on their east/north edge, so a coordinate exactly on an internal boundary
belongs to the higher-index east or north cell. The outer maximum remains in index
13 (`N` or `14`).

## Ground-truth audit

`tools/replay_positions.json` is generated from the decompressed replay whose SHA256
is `6d3917453024844349c8935536964c3bd925d5c3958b2946b82ab9b09ad6a9ac`.
The compressed replay SHA256 is
`f5797e2cda60eadf125561c4b4221545977fb8d842055df94868e6bb8f4b16c5`.
`tools/build_ground_truth.py --check` reproduces the verifier truth, oracle, and
audit byte-for-structure from the two pinned snapshots.

The predecessor task incorrectly treated replay coordinates as a `0..255` image.
OpenDota actually subtracts 64 and normalizes by 127. Its historical calibration is
retired and is not evidence for this task.

The broadcast was also spot-checked at early, middle, and late fight windows. Those
windows show the full minimap at all three requested times and agree with the replay
trajectory's direction and quantized cell placement. Native 720p crops and enlarged
grid overlays for early and late stacked fights are checked in under
`calibration/minimap-evidence/`.
