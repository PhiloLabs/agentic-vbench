# Over-The-Board Chess Move Reconstruction

You are given one representative still frame at
`/Users/brendaz/Documents/Codex/2026-07-07/tak/work/agentic-vbench/calibration_runs/otb-chess-move-capture-reconstruction/codex-ablation-single-frame-20260719T012741Z/materials/game.png`.
It comes from a real over-the-board chess game, but no other frames are available.
Reconstruct the game record from the visible physical board.

Write `/Users/brendaz/Documents/Codex/2026-07-07/tak/work/agentic-vbench/calibration_runs/otb-chess-move-capture-reconstruction/codex-ablation-single-frame-20260719T012741Z/output/solution.json` in exactly this shape:

```json
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
      "captured_piece": "white_pawn | white_knight | white_bishop | white_rook | white_queen | white_king | black_pawn | black_knight | black_bishop | black_rook | black_queen | black_king",
      "video_time": "HH:MM:SS.s"
    }
  ]
}
```

Definitions:

- `ply`: half-move number, starting at 1 for White's first move.
- `move_number`: full chess move number.
- `side`: the side making the move.
- `san`: standard algebraic notation for the move.
- `uci`: coordinate notation from origin square to destination square, with a
  promotion suffix if applicable, such as `e7e8q`.
- `video_time`: the approximate time in the supplied video when the move has
  become visible on the physical board. Use `HH:MM:SS.s`. The verifier accepts
  timestamps within +/- 6 seconds of the reference annotation.
- `capture_events`: include every move that captures a piece. Each capture event
  must repeat the move identity and report the square where the capture occurs
  and the color/type of the captured piece.

Rules:

- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online, and do not rely on memory of this game.
- Use only the still frame as evidence for every move and timestamp.
- Do not include comments, prose, or extra top-level fields in the JSON.
