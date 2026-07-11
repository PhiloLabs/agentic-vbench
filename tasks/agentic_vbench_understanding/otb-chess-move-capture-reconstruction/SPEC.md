# Task Spec Card

```yaml
task: agentic_vbench_understanding/otb-chess-move-capture-reconstruction

cognitive_level: understanding

modalities_required:
  video: The answer requires tracking the physical chessboard through 115 visible plies and 22 capture events.
  audio: not used; the benchmark material is silent.

question: Reconstruct the complete over-the-board chess game record, move timestamps, capture events, and final result from the supplied masked physical-board video.
output_schema: |
  {
    "game_type": "chess",
    "result": "white_win | black_win | draw | unknown",
    "moves": [
      {
        "ply": 1,
        "move_number": 1,
        "side": "white | black",
        "san": "Nf3",
        "uci": "g1f3",
        "video_time": "HH:MM:SS.s"
      }
    ],
    "capture_events": [
      {
        "ply": 32,
        "move_number": 16,
        "side": "white | black",
        "san": "Nxg3",
        "uci": "e4g3",
        "capture_square": "g3",
        "captured_piece": "white_knight",
        "video_time": "HH:MM:SS.s"
      }
    ]
  }

evidence:
  - t=00:00:59.5, video, first visible move Nf3 establishes the game start.
  - t=00:06:47.5-00:06:48.8, video, Nxg3/hxg3 capture-and-recapture sequence.
  - t=00:09:49.0-00:09:53.2, video, rapid f7 capture chain with multiple rooks and king.
  - t=00:10:24.8, video, final move Bxb6 and no following black move.

ground_truth:
  source: YouTube video xwoRCwMRE54 and its description PGN, with timestamps aligned from the video overlay before masking.
  tier: mixed; move identities are PGN-derived machine truth, timestamps/result are video-verified annotations.
  verification: Parsed the description PGN into 115 legal plies with python-chess, aligned all plies to detected overlay-highlight transitions, spot-checked physical-board frames, and separately listed all 22 capture events.

scorer:
  metric: Deterministic per-check accuracy over result, per-ply identity, per-ply timestamp within +/- 6s, capture identity, capture detail, and capture timestamp. Extra moves and extra captures are penalized.
  oracle_reward: 1.0
  null_reward: 0.0

difficulty:
  strong_agent_reward: 0.033
  tool_call_turns: 54
  agent_model: Codex CLI (`codex-local-chess-gt50-20260710T213945Z`)

anti_shortcut:
  single_frame: not run yet; pending ablation calibration
  video_only: not applicable as an ablation distinction because the task material is already silent video
  audio_only: not applicable because the task material has no audio
  no_media: empty/null baseline scores 0.0
  frame_dump_no_tools: not run yet; pending ablation calibration

input:
  url: https://www.youtube.com/watch?v=xwoRCwMRE54
  source_sha256: 91d05bdf6138e232894cf826b18de91824c2bd9b1dc5045f0fbe40ac4aceb4b8
  processed_material_sha256: 49c5afe38f0c5086ccc9f867b31994344e38db7dec3718931a17ebf521cc7a5a
  length_min: 11.8
  resolution: 720
```

## Notes

The agent-facing video is derived from the YouTube source by masking the digital
board overlay and visible branding, stripping audio, and keeping the physical board
view. The unmasked overlay was used only for author-side timestamp annotation.
