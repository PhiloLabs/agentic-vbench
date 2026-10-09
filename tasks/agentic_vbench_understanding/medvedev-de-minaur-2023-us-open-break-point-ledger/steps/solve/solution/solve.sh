#!/bin/bash
set -euo pipefail

MEDVEDEV_OUTPUT_DIR="${MEDVEDEV_OUTPUT_DIR:-/workspace/output}"
export MEDVEDEV_OUTPUT_DIR
mkdir -p "$MEDVEDEV_OUTPUT_DIR"

python3 - <<'PY'
import json
import os
from pathlib import Path

BREAK_POINTS = [
    {"set": 1, "medvedev_games": 1, "de_minaur_games": 1, "medvedev_points": "30", "de_minaur_points": "40", "server": "Daniil Medvedev", "opportunity": 1, "first_serve_in": True, "outcome": "saved", "serve_direction": "down_the_t", "rally_shots": 7, "terminal_player": "Alex De Minaur", "terminal_stroke": "backhand_lob", "terminal_court_position": "baseline", "terminal_result": "forced_error", "terminal_error": "deep"},
    {"set": 1, "medvedev_games": 2, "de_minaur_games": 2, "medvedev_points": "30", "de_minaur_points": "40", "server": "Daniil Medvedev", "opportunity": 1, "first_serve_in": True, "outcome": "converted", "serve_direction": "wide", "rally_shots": 4, "terminal_player": "Alex De Minaur", "terminal_stroke": "backhand_groundstroke", "terminal_court_position": "net", "terminal_result": "winner", "terminal_error": "none"},
    {"set": 1, "medvedev_games": 2, "de_minaur_games": 4, "medvedev_points": "15", "de_minaur_points": "40", "server": "Daniil Medvedev", "opportunity": 1, "first_serve_in": True, "outcome": "converted", "serve_direction": "down_the_t", "rally_shots": 2, "terminal_player": "Daniil Medvedev", "terminal_stroke": "forehand_groundstroke", "terminal_court_position": "baseline", "terminal_result": "forced_error", "terminal_error": "net"},
    {"set": 2, "medvedev_games": 2, "de_minaur_games": 1, "medvedev_points": "40", "de_minaur_points": "15", "server": "Alex De Minaur", "opportunity": 1, "first_serve_in": False, "outcome": "saved", "serve_direction": "body", "rally_shots": 9, "terminal_player": "Daniil Medvedev", "terminal_stroke": "backhand_groundstroke", "terminal_court_position": "baseline", "terminal_result": "unforced_error", "terminal_error": "net"},
    {"set": 2, "medvedev_games": 2, "de_minaur_games": 1, "medvedev_points": "40", "de_minaur_points": "30", "server": "Alex De Minaur", "opportunity": 2, "first_serve_in": True, "outcome": "saved", "serve_direction": "wide", "rally_shots": 3, "terminal_player": "Alex De Minaur", "terminal_stroke": "forehand_volley", "terminal_court_position": "net", "terminal_result": "winner", "terminal_error": "none"},
    {"set": 2, "medvedev_games": 2, "de_minaur_games": 1, "medvedev_points": "AD", "de_minaur_points": "40", "server": "Alex De Minaur", "opportunity": 3, "first_serve_in": False, "outcome": "saved", "serve_direction": "body", "rally_shots": 25, "terminal_player": "Alex De Minaur", "terminal_stroke": "forehand_groundstroke", "terminal_court_position": "baseline", "terminal_result": "winner", "terminal_error": "none"},
    {"set": 2, "medvedev_games": 2, "de_minaur_games": 1, "medvedev_points": "AD", "de_minaur_points": "40", "server": "Alex De Minaur", "opportunity": 4, "first_serve_in": True, "outcome": "saved", "serve_direction": "body", "rally_shots": 1, "terminal_player": "Daniil Medvedev", "terminal_stroke": "backhand_groundstroke", "terminal_court_position": "baseline", "terminal_result": "forced_error", "terminal_error": "deep"},
    {"set": 2, "medvedev_games": 2, "de_minaur_games": 1, "medvedev_points": "AD", "de_minaur_points": "40", "server": "Alex De Minaur", "opportunity": 5, "first_serve_in": True, "outcome": "saved", "serve_direction": "wide", "rally_shots": 1, "terminal_player": "Alex De Minaur", "terminal_stroke": "serve", "terminal_court_position": "serve", "terminal_result": "ace", "terminal_error": "none"},
    {"set": 2, "medvedev_games": 5, "de_minaur_games": 4, "medvedev_points": "40", "de_minaur_points": "15", "server": "Alex De Minaur", "opportunity": 1, "first_serve_in": True, "outcome": "converted", "serve_direction": "body", "rally_shots": 6, "terminal_player": "Alex De Minaur", "terminal_stroke": "forehand_slice", "terminal_court_position": "baseline", "terminal_result": "forced_error", "terminal_error": "deep"},
    {"set": 3, "medvedev_games": 2, "de_minaur_games": 1, "medvedev_points": "AD", "de_minaur_points": "40", "server": "Alex De Minaur", "opportunity": 1, "first_serve_in": True, "outcome": "converted", "serve_direction": "wide", "rally_shots": 12, "terminal_player": "Alex De Minaur", "terminal_stroke": "backhand_groundstroke", "terminal_court_position": "baseline", "terminal_result": "unforced_error", "terminal_error": "deep"},
    {"set": 3, "medvedev_games": 4, "de_minaur_games": 1, "medvedev_points": "40", "de_minaur_points": "30", "server": "Alex De Minaur", "opportunity": 1, "first_serve_in": False, "outcome": "converted", "serve_direction": "wide", "rally_shots": 2, "terminal_player": "Alex De Minaur", "terminal_stroke": "forehand_groundstroke", "terminal_court_position": "baseline", "terminal_result": "unforced_error", "terminal_error": "deep"},
    {"set": 4, "medvedev_games": 0, "de_minaur_games": 1, "medvedev_points": "30", "de_minaur_points": "40", "server": "Daniil Medvedev", "opportunity": 1, "first_serve_in": True, "outcome": "saved", "serve_direction": "wide", "rally_shots": 11, "terminal_player": "Daniil Medvedev", "terminal_stroke": "backhand_groundstroke", "terminal_court_position": "net", "terminal_result": "winner", "terminal_error": "none"},
    {"set": 4, "medvedev_games": 1, "de_minaur_games": 1, "medvedev_points": "40", "de_minaur_points": "0", "server": "Alex De Minaur", "opportunity": 1, "first_serve_in": False, "outcome": "converted", "serve_direction": "body", "rally_shots": 6, "terminal_player": "Alex De Minaur", "terminal_stroke": "backhand_volley", "terminal_court_position": "net", "terminal_result": "unforced_error", "terminal_error": "net"},
    {"set": 4, "medvedev_games": 3, "de_minaur_games": 1, "medvedev_points": "40", "de_minaur_points": "0", "server": "Alex De Minaur", "opportunity": 1, "first_serve_in": False, "outcome": "converted", "serve_direction": "body", "rally_shots": 8, "terminal_player": "Daniil Medvedev", "terminal_stroke": "backhand_groundstroke", "terminal_court_position": "baseline", "terminal_result": "winner", "terminal_error": "none"},
    {"set": 4, "medvedev_games": 4, "de_minaur_games": 1, "medvedev_points": "30", "de_minaur_points": "40", "server": "Daniil Medvedev", "opportunity": 1, "first_serve_in": True, "outcome": "saved", "serve_direction": "down_the_t", "rally_shots": 1, "terminal_player": "Daniil Medvedev", "terminal_stroke": "serve", "terminal_court_position": "serve", "terminal_result": "unreturnable", "terminal_error": "none"},
    {"set": 4, "medvedev_games": 4, "de_minaur_games": 1, "medvedev_points": "40", "de_minaur_points": "AD", "server": "Daniil Medvedev", "opportunity": 2, "first_serve_in": False, "outcome": "saved", "serve_direction": "body", "rally_shots": 5, "terminal_player": "Alex De Minaur", "terminal_stroke": "backhand_groundstroke", "terminal_court_position": "baseline", "terminal_result": "unforced_error", "terminal_error": "deep"},
]

LIVE_RALLY_CODES = (
    "6f28f1f3b3y1f-3m3d#",
    "4+b27h^3b-1*",
    "6b29f2n#",
    "5f28b1f2f2f3b2b3b3b3n@",
    "4+b2v3*",
    "5b29f3b3b3b3b2b3b3b3b3b3b2f2f2f3s3f3b3b3b3b3b3b2f3*",
    "5b2d#",
    "4*",
    "5b38s3b1r2f1r1d#",
    "4b28f3b3b3b3s1f1f2b3b3b3b3d@",
    "4b39f2d@",
    "4b28f1f1f3b1f3u1f-1f2b-3*",
    "5b29f1f1u+3i3z1n@",
    "5b38b2b2b2b2b+2b1*",
    "6#",
    "5f38b1f2f2b1d@",
)

STROKE_CODES = {
    "f": "forehand_groundstroke", "b": "backhand_groundstroke",
    "r": "forehand_slice", "s": "backhand_slice",
    "v": "forehand_volley", "z": "backhand_volley",
    "o": "overhead", "p": "backhand_overhead",
    "u": "forehand_drop_shot", "y": "backhand_drop_shot",
    "l": "forehand_lob", "m": "backhand_lob",
    "h": "forehand_half_volley", "i": "backhand_half_volley",
    "j": "forehand_swinging_volley", "k": "backhand_swinging_volley",
    "t": "trick_shot", "q": "unknown",
}
SERVE_DIRECTIONS = {"0": "unknown", "4": "wide", "5": "body", "6": "down_the_t"}
RALLY_DIRECTIONS = {
    "0": "unknown", "1": "receiver_forehand",
    "2": "middle", "3": "receiver_backhand",
}


def decode_live_rally(code):
    index = 0
    while code[index] == "c":
        index += 1
    shots = [{"stroke": "serve", "direction": SERVE_DIRECTIONS[code[index]]}]
    index += 1
    while index < len(code) and code[index] == "+":
        index += 1
    if index < len(code) and code[index] in "*#":
        return shots

    first_rally_contact = True
    while index < len(code):
        stroke_code = code[index]
        index += 1
        while index < len(code) and code[index] in "+-=;^":
            index += 1
        direction = "unknown"
        if index < len(code) and code[index] in RALLY_DIRECTIONS:
            direction = RALLY_DIRECTIONS[code[index]]
            index += 1
        if first_rally_contact and index < len(code) and code[index] in "789":
            index += 1
        first_rally_contact = False
        shots.append({"stroke": STROKE_CODES[stroke_code], "direction": direction})
        if index < len(code) and code[index] in "nwdxe!":
            index += 1
        if index < len(code) and code[index] in "*@#":
            index += 1
    return shots


for event, code in zip(BREAK_POINTS, LIVE_RALLY_CODES):
    event["shots"] = decode_live_rally(code)

output_path = Path(os.environ["MEDVEDEV_OUTPUT_DIR"]) / "solution.json"
output_path.write_text(json.dumps({"break_points": BREAK_POINTS}, indent=2))
PY
