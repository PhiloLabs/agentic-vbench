# Over-The-Board Chess Move Reconstruction

You are given one silent video at `/Users/brendaz/Documents/Codex/2026-07-07/tak/work/agentic-vbench/calibration_runs/otb-chess-move-capture-reconstruction/antigravity-local-chess-capped-20260711T030815Z/materials/game.mp4`. It shows a real
over-the-board chess game from the initial position through the end of the game.
Some nonessential on-screen graphics have been masked out. Reconstruct the game
record from the visible physical board.

Write `/Users/brendaz/Documents/Codex/2026-07-07/tak/work/agentic-vbench/calibration_runs/otb-chess-move-capture-reconstruction/antigravity-local-chess-capped-20260711T030815Z/output/solution.json` in exactly this shape:

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
  become visible on the physical board. Use `HH:MM:SS.s`.
- `capture_events`: include every move that captures a piece. Each capture event
  must repeat the move identity and report the square where the capture occurs
  and the color/type of the captured piece.

Rules:

- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online, and do not rely on memory of this game.
- Use the video as evidence for every move and timestamp.
- Do not include comments, prose, or extra top-level fields in the JSON.


Operational cap for this calibration rollout:
- You are running under an external turn watchdog.
- Write /Users/brendaz/Documents/Codex/2026-07-07/tak/work/agentic-vbench/calibration_runs/otb-chess-move-capture-reconstruction/antigravity-local-chess-capped-20260711T030815Z/output/solution.json as soon as you have a best current answer.
- By your 45th meaningful tool/command step, write the best partial solution you have, even if incomplete.
- After writing /Users/brendaz/Documents/Codex/2026-07-07/tak/work/agentic-vbench/calibration_runs/otb-chess-move-capture-reconstruction/antigravity-local-chess-capped-20260711T030815Z/output/solution.json, stop instead of continuing to refine.
- Do not intentionally continue beyond 50 meaningful tool/command steps unless the solution is already likely to score at least 0.5.
- Never exceed 75 meaningful tool/command steps.
