# Task Spec Card

```yaml
task: agentic_vbench_understanding/otb-chess-move-capture-reconstruction

cognitive_level: understanding

modalities_required:
  video: The answer requires tracking the physical chessboard through 104 visible plies and 26 capture events.
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
  - t=00:00:42.0-00:01:01.5, video, e4/e5, Nf3/Nc6, and Bb5/Nge7 establish the opening and distinguish the two black-knight routes.
  - t=00:04:12.5-00:05:57.4, video, exd4/Nxd4/Nxd4/Qxd4 followed by Bxb5/Nxb5 anchors the first capture sequence.
  - t=00:19:48.1-00:21:04.5, video, Qxd6/Qxd6, Bd4, Bxe5/Rxe5, and Qxd3/cxd3 establish the queen trade and transition to the rook ending.
  - t=00:22:10.9-00:22:43.4, video, Rxa3, Rxc3, exf6/gxf6, and cxd7 establish the late middlegame material changes.
  - t=00:24:09.3-00:24:48.3, video, the final rook-and-pawn sequence ends with 52...Rh3 and White stopping the clock to concede.

ground_truth:
  source: YouTube video A94oACpgpYo, manually annotated from the physical-board video without using a public PGN.
  tier: human-verified
  verification: Two independent human passes confirmed the complete 104-ply move sequence, Black's win after 52...Rh3 when White stopped the clock, and all annotated move and capture timestamps. The author reconciled shorthand and ambiguous piece identities against perspective-warped board frames, aligned timestamps from the video, and validated all plies and 26 capture events with python-chess. The second reviewer checked the timestamp annotations against the physical-board video with the stated +/- 6s scoring tolerance.

scorer:
  metric: Deterministic per-check accuracy over result, per-ply identity, per-ply timestamp within +/- 6s, capture identity, capture detail, and capture timestamp. Extra moves and extra captures are penalized.
  oracle_reward: 1.0
  null_reward: 0.0

difficulty:
  strong_agent_reward: 0.0379 in the natural-prompt full-media Codex rollout
  tool_call_turns: 237 completed shell calls, with no turn minimum or pacing hint
  agent_model: Codex GPT-5.6 Sol, high reasoning
  status: The replacement source and ground truth pass the numerical hardness gate and the natural long-horizon gate. The fresh rollout used the benchmark instruction with path-only rewriting and passed 13/343 checks; it wrote temporary analysis artifacts outside the requested workspace but did not access ground truth or public game data.

anti_shortcut:
  single_frame: Codex GPT-5.6 Sol (high reasoning) scored 0.0058 from one representative frame at 00:13:00; 2/343 checks passed.
  video_only: not applicable as an ablation distinction because the task material is already silent video
  audio_only: not applicable because the task material has no audio
  no_media: Codex GPT-5.6 Sol (high reasoning) scored 0.0 from prompt and schema only; 0/287 checks passed.
  frame_dump_no_tools: not run yet on replacement source; pending ablation calibration

input:
  url: https://www.youtube.com/watch?v=A94oACpgpYo
  source_sha256: 95326518fee4c5eeba8ecb1b8567087102985b263a7fdbf83af6e8bdd6009060
  processed_material_sha256: b9839b0e67c02ffa4ae9a7662809b25a045f6feff9749844bb66eb19d6a99420
  length_min: 25.8
  resolution: 720
```

## Notes

The agent-facing video is derived from the YouTube source by masking visible
branding/watermarks, stripping audio, and keeping the physical board view.
