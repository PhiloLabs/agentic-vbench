import chess
import json
import re

moves_data = """
00:16 g1f3
00:18 d7d5
00:20 b2b3
00:22 g8f6
00:23 c1b2
00:24 c7c5
00:25 e2e3
00:26 e7e6
00:28 d2d4
00:29 b8c6
00:30 f1d3
00:32 f8d6
00:33 e1g1
00:34 e8g8
00:36 c2c4
00:37 b7b6
00:38 b1d2
00:39 c8b7
00:42 a2a3
00:44 d8e7
00:46 d1c2
00:48 a8c8
00:49 a1c1
00:51 c5d4
00:52 e3d4
00:54 d5c4
00:56 b3c4
00:58 c6a5
01:04 f3e5
01:11 g7g6
01:12 d2f3
01:13 f6h5
01:17 c2d2
01:18 f7f6
01:27 e5g4
01:40 d6f4
01:41 g4e3
01:45 f4h6
01:46 f1e1
01:53 e7d6
01:54 c1d1
01:55 f8d8
02:02 b2c1
02:06 h5f4
02:07 d3f1
02:37 a5b3
02:38 d2c3
02:49 b3a5
02:50 c4c5
03:03 d6c7
03:05 f3g5
03:28 h6g7
03:30 e3c4
03:44 f4d5
03:45 c3b2
04:01 b6c5
04:02 d4c5
04:20 c8b8
04:22 b2c2
04:52 b7a8
04:54 f1a6
04:55 b8b6
05:27 a3a4
05:31 d8b8
05:32 a6b5
05:40 h7h6
05:41 g5f3
05:55 f6f5
05:56 h2h3
06:15 g6g5
06:17 e1e2
06:20 g8f7
06:23 d1e1
06:33 c7f4
06:39 c2d1
06:47 d5f6
06:48 c4e5
06:49 f7g8
06:50 g2g3
06:58 f4e4
07:24 e4c2
07:25 d1d2
07:31 c2d2
07:32 e2d2
07:41 b8b7
07:43 d2e2
07:54 a5c4
07:56 e5d7
07:59 b7d7
08:02 b5d7
08:03 f6d7
08:05 f3d2
08:06 c4d2
08:07 e2d2
08:14 g8f7
08:16 g1g2
08:18 f7f6
08:20 g2f3
08:21 b6b7
08:22 d2e2
08:24 b7e7
08:25 h3h4
08:27 g5h4
08:29 g3h4
08:32 e7g7
08:37 e2e5
08:39 g7g1
08:44 e1e3
08:45 g1f1
08:47 f3g2
08:48 f1a1
08:55 e3e5
08:58 a1a4
08:59 e5d5
09:00 a4a2
09:02 g2f3
09:04 a2a3
09:06 e2e3
09:12 a3a4
09:15 d5d6
09:16 f6f7
09:21 d6h6
09:22 d7f6
09:23 h6h8
09:25 a4a2
09:29 h8b8
09:31 f6g4
09:32 b8b7
09:33 f7f6
09:35 e3e2
09:37 a2a3
09:39 f3g2
09:40 g4e3
09:41 g2f2
09:42 e3g4
09:45 f2g2
09:46 g4e3
09:48 e2e3
09:49 a3e3
09:51 b7b6
09:52 e3e4
09:54 g2f3
09:55 e4d4
09:56 h4h5
09:58 d4h4
10:00 f3g3
10:02 h4h5
10:04 b6e6
10:06 f6e6
10:08 g3g4
10:10 h5h1
10:12 g4f4
10:13 h1e1
10:16 f4f3
10:18 e6e5
10:20 f3f2
10:21 e1e4
10:24 f2f3
10:26 e5f5
10:27 f3g3
10:33 e4e3
10:35 g3f2
10:37 f5f4
10:41 f2g2
10:44 e3e2
10:46 g2h3
10:48 e2f2
10:52 h3h4
10:53 f2h2
"""

board = chess.Board()

out_moves = []
out_captures = []

piece_name_map = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king"
}

for i, line in enumerate(moves_data.strip().split('\n')):
    if not line.strip(): continue
    time_str, uci = line.split()
    
    time_formatted = f"00:{time_str}.0"
    
    move = chess.Move.from_uci(uci)
    
    if not board.is_legal(move):
        print(f"ILLEGAL MOVE AT {time_str} {uci}: {move} in fen {board.fen()}")
        break
        
    san = board.san(move)
    is_capture = board.is_capture(move)
    
    captured_piece_str = None
    if is_capture:
        if board.is_en_passant(move):
            captured_piece = chess.PAWN
            cap_color = not board.turn
        else:
            captured_piece = board.piece_at(move.to_square).piece_type
            cap_color = board.piece_at(move.to_square).color
            
        color_str = "white" if cap_color == chess.WHITE else "black"
        captured_piece_str = f"{color_str}_{piece_name_map[captured_piece]}"

    ply = board.ply() + 1
    move_number = board.fullmove_number
    side = "white" if board.turn == chess.WHITE else "black"
    
    move_entry = {
        "ply": ply,
        "move_number": move_number,
        "side": side,
        "san": san,
        "uci": uci,
        "video_time": time_formatted
    }
    out_moves.append(move_entry)
    
    if is_capture:
        cap_entry = {
            "ply": ply,
            "move_number": move_number,
            "side": side,
            "san": san,
            "uci": uci,
            "capture_square": chess.square_name(move.to_square),
            "captured_piece": captured_piece_str,
            "video_time": time_formatted
        }
        out_captures.append(cap_entry)
        
    board.push(move)

if board.is_checkmate():
    result = "black_win" if board.turn == chess.WHITE else "white_win"
elif board.is_game_over():
    result = "draw"
else:
    result = "unknown"
    
# check if it's checkmate at the end
# but Parham won, so black_win
result = "black_win"

output = {
    "game_type": "chess",
    "result": result,
    "moves": out_moves,
    "capture_events": out_captures
}

with open("/Users/brendaz/Documents/Codex/2026-07-07/tak/work/agentic-vbench/calibration_runs/otb-chess-move-capture-reconstruction/antigravity-local-chess-capped-20260711T030815Z/output/solution.json", "w") as f:
    json.dump(output, f, indent=2)

print("Done. Last fen:", board.fen())
