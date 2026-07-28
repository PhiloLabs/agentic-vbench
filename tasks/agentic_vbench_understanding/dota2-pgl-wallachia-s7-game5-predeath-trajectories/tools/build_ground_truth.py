#!/usr/bin/env python3
"""Rebuild the pre-death trajectories from pinned OpenDota and Valve replay data."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import urllib.request
from bisect import bisect_right
from pathlib import Path
from typing import Any


TASK_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = TASK_ROOT / "tools" / "source_events.json"
POSITIONS_PATH = TASK_ROOT / "tools" / "replay_positions.json"
AUDIT_PATH = TASK_ROOT / "tools" / "ground_truth_audit.json"
GROUND_TRUTH_PATH = TASK_ROOT / "steps" / "solve" / "tests" / "ground_truth.json"
SOLUTION_PATH = TASK_ROOT / "steps" / "solve" / "solution" / "solution.json"

MATCH_ID = 8730786393
GAME_NUMBER = 5
SERIES_ID = 1074881
YANDX_TEAM_ID = 9823272
LIQUID_TEAM_ID = 2163
LAST_CLOCK_S = 50 * 60 + 30
GRID_SIZE = 14
RAW_MAP_MIN = 64.0
RAW_MAP_SPAN = 127.0
GRID_BOUNDARIES = tuple(
    RAW_MAP_MIN + RAW_MAP_SPAN * index / GRID_SIZE
    for index in range(1, GRID_SIZE)
)
EXPECTED_EVENTS = 39
MAX_CONSECUTIVE_DEATH_GAP_S = 15
SLOT_TO_PLAYER = {
    0: "watson",
    1: "CHIRA_JUNIOR",
    2: "DM",
    3: "Malady",
    4: "Saksa",
    128: "tOfu",
    129: "Ace",
    130: "Nisha",
    131: "Boxi",
    132: "m1CKe",
}
USER_AGENT = "agentic-vbench-ground-truth-builder/6.0"


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_json(path: Path, value: Any) -> None:
    path.write_text(stable_json(value), encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def refresh_source() -> dict[str, Any]:
    hero_constants = fetch_json("https://api.opendota.com/api/constants/heroes")
    hero_names = {
        int(hero_id): hero["name"] for hero_id, hero in hero_constants.items()
    }
    match = fetch_json(f"https://api.opendota.com/api/matches/{MATCH_ID}")
    if match.get("series_id") != SERIES_ID:
        raise RuntimeError(f"match {MATCH_ID} is no longer in series {SERIES_ID}")
    if match.get("radiant_team_id") != YANDX_TEAM_ID:
        raise RuntimeError(f"match {MATCH_ID} does not have Team Yandex as Radiant")
    if match.get("dire_team_id") != LIQUID_TEAM_ID:
        raise RuntimeError(f"match {MATCH_ID} does not have Team Liquid as Dire")

    players = []
    for player in match["players"]:
        slot = int(player["player_slot"])
        if slot not in SLOT_TO_PLAYER:
            raise RuntimeError(f"unexpected player slot {slot} in match {MATCH_ID}")
        hero_id = int(player["hero_id"])
        players.append(
            {
                "player_slot": slot,
                "canonical_player": SLOT_TO_PLAYER[slot],
                "hero_id": hero_id,
                "hero_key": hero_names[hero_id],
                "kills_log": [
                    {"time": int(event["time"]), "victim_hero": event["key"]}
                    for event in (player.get("kills_log") or [])
                ],
            }
        )

    teamfights = []
    for source_index, fight in enumerate(match.get("teamfights") or []):
        fight_players = []
        for player_index, player in enumerate(fight["players"]):
            positions = []
            for x_text, y_values in (player.get("deaths_pos") or {}).items():
                for y_text, count in y_values.items():
                    positions.extend(
                        {"x": int(x_text), "y": int(y_text)}
                        for _ in range(int(count))
                    )
            if positions:
                fight_players.append(
                    {
                        "player_index": player_index,
                        "death_positions": sorted(
                            positions, key=lambda item: (item["x"], item["y"])
                        ),
                    }
                )
        teamfights.append(
            {
                "source_index": source_index,
                "start": int(fight["start"]),
                "last_death": int(fight["last_death"]),
                "deaths": int(fight["deaths"]),
                "players": fight_players,
            }
        )

    source = {
        "source": "OpenDota automated Valve replay parsing",
        "api_match_url_template": "https://api.opendota.com/api/matches/{match_id}",
        "series_id": SERIES_ID,
        "matches": [
            {
                "game": GAME_NUMBER,
                "match_id": MATCH_ID,
                "series_id": int(match["series_id"]),
                "duration": int(match["duration"]),
                "radiant_team_id": int(match["radiant_team_id"]),
                "dire_team_id": int(match["dire_team_id"]),
                "players": sorted(players, key=lambda item: item["player_slot"]),
                "teamfights": teamfights,
            }
        ],
    }
    write_json(SOURCE_PATH, source)
    return source


def clock_text(seconds: int) -> str:
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def grid_axis(raw_coordinate: float) -> int:
    if not RAW_MAP_MIN <= raw_coordinate <= RAW_MAP_MIN + RAW_MAP_SPAN:
        raise RuntimeError(f"position lies outside the Dota map: {raw_coordinate}")
    return min(GRID_SIZE - 1, bisect_right(GRID_BOUNDARIES, raw_coordinate))


def grid_cell(raw_x: float, raw_y: float) -> str:
    column = chr(ord("A") + grid_axis(raw_x))
    row = grid_axis(raw_y) + 1
    return f"{column}{row}"


def source_kills(match: dict[str, Any]) -> list[dict[str, Any]]:
    hero_to_player = {
        player["hero_key"]: player["canonical_player"] for player in match["players"]
    }
    kills = []
    for killer in match["players"]:
        for item in killer["kills_log"]:
            time = int(item["time"])
            if 0 <= time <= LAST_CLOCK_S:
                kills.append(
                    {
                        "time": time,
                        "victim": hero_to_player[item["victim_hero"]],
                        "killer": killer["canonical_player"],
                    }
                )
    return sorted(kills, key=lambda item: (item["time"], item["victim"], item["killer"]))


def major_teamfight_kills(match: dict[str, Any]) -> list[dict[str, Any]]:
    kills = source_kills(match)
    clusters: list[list[dict[str, Any]]] = []
    for item in kills:
        if (
            not clusters
            or item["time"] - clusters[-1][-1]["time"]
            >= MAX_CONSECUTIVE_DEATH_GAP_S
        ):
            clusters.append([item])
        else:
            clusters[-1].append(item)
    operational_fights = [cluster for cluster in clusters if len(cluster) >= 3]
    parsed_fights = [
        [
            item
            for item in kills
            if int(fight["start"]) <= item["time"] <= int(fight["last_death"])
        ]
        for fight in match["teamfights"]
    ]
    if operational_fights != parsed_fights:
        raise RuntimeError("OpenDota teamfights differ from the task's death-gap rule")
    return [item for fight in operational_fights for item in fight]


def crosscheck_open_dota_positions(
    match: dict[str, Any], replay_by_key: dict[tuple[int, str], dict[str, Any]]
) -> dict[str, int]:
    kills = major_teamfight_kills(match)
    compared = 0
    rounded_raw_exact = 0
    rounded_raw_neighbor = 0
    exact_grid_cell = 0
    max_rounded_distance = 0

    for fight in match["teamfights"]:
        fight_kills = [
            item
            for item in kills
            if int(fight["start"]) <= item["time"] <= int(fight["last_death"])
        ]
        kill_by_victim = {item["victim"]: item for item in fight_kills}
        if len(kill_by_victim) != len(fight_kills):
            raise RuntimeError("crosscheck requires unique victims within each teamfight")
        for player_entry in fight["players"]:
            victim = match["players"][int(player_entry["player_index"])]["canonical_player"]
            positions = player_entry["death_positions"]
            if victim not in kill_by_victim or len(positions) != 1:
                raise RuntimeError("OpenDota teamfight position does not map to one death")
            source_position = positions[0]
            kill = kill_by_victim[victim]
            replay_position = replay_by_key[(kill["time"], victim)]["positions"]["death"]
            replay_x = float(replay_position["raw_x"])
            replay_y = float(replay_position["raw_y"])
            distance = max(
                abs(round(replay_x) - int(source_position["x"])),
                abs(round(replay_y) - int(source_position["y"])),
            )
            compared += 1
            rounded_raw_exact += distance == 0
            rounded_raw_neighbor += distance <= 1
            exact_grid_cell += grid_cell(replay_x, replay_y) == grid_cell(
                float(source_position["x"]), float(source_position["y"])
            )
            max_rounded_distance = max(max_rounded_distance, distance)

    return {
        "events_compared": compared,
        "rounded_raw_coordinate_exact": rounded_raw_exact,
        "rounded_raw_coordinate_within_one": rounded_raw_neighbor,
        "exact_14x14_cell": exact_grid_cell,
        "maximum_rounded_chebyshev_distance": max_rounded_distance,
    }


def derive(
    source: dict[str, Any], replay_positions: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    if len(source["matches"]) != 1:
        raise RuntimeError("expected one source match")
    match = source["matches"][0]
    if int(match["match_id"]) != MATCH_ID or int(match["game"]) != GAME_NUMBER:
        raise RuntimeError("source snapshot does not match the pinned Game 5")
    if int(replay_positions["metadata"]["match_id"]) != MATCH_ID:
        raise RuntimeError("replay position snapshot does not match the pinned match")

    kills = major_teamfight_kills(match)
    replay_events = replay_positions["events"]
    if len(kills) != EXPECTED_EVENTS or len(replay_events) != EXPECTED_EVENTS:
        raise RuntimeError(
            f"expected {EXPECTED_EVENTS} deaths, got {len(kills)} source and "
            f"{len(replay_events)} replay events"
        )
    replay_by_key = {
        (int(item["time"]), item["victim"]): item for item in replay_events
    }
    if len(replay_by_key) != EXPECTED_EVENTS:
        raise RuntimeError("replay snapshot contains duplicate death keys")

    events = []
    tick_deltas = []
    for kill in kills:
        key = (kill["time"], kill["victim"])
        if key not in replay_by_key:
            raise RuntimeError(f"missing replay trajectory for {key}")
        replay_event = replay_by_key[key]
        if replay_event["killer"] != kill["killer"]:
            raise RuntimeError(f"killer mismatch for {key}")
        positions = replay_event["positions"]
        tick_deltas.extend(abs(int(item["tick_delta"])) for item in positions.values())
        events.append(
            {
                "game": GAME_NUMBER,
                "clock": clock_text(kill["time"]),
                "victim": kill["victim"],
                "killer": kill["killer"],
                "cell_10s_before": grid_cell(
                    float(positions["minus_10s"]["raw_x"]),
                    float(positions["minus_10s"]["raw_y"]),
                ),
                "cell_5s_before": grid_cell(
                    float(positions["minus_5s"]["raw_x"]),
                    float(positions["minus_5s"]["raw_y"]),
                ),
                "death_cell": grid_cell(
                    float(positions["death"]["raw_x"]),
                    float(positions["death"]["raw_y"]),
                ),
            }
        )

    trajectories = collections.Counter(
        (
            item["cell_10s_before"],
            item["cell_5s_before"],
            item["death_cell"],
        )
        for item in events
    )
    death_cells = collections.Counter(item["death_cell"] for item in events)
    ground_truth = {"events": events}
    audit = {
        "source_sha256": sha256_bytes(SOURCE_PATH.read_bytes()),
        "replay_positions_sha256": sha256_bytes(POSITIONS_PATH.read_bytes()),
        "source": {
            "match_id": MATCH_ID,
            "source": source["source"],
            "replay": replay_positions["metadata"],
        },
        "event_definition": {
            "game": GAME_NUMBER,
            "hud_clock_range_inclusive": "00:00-50:30",
            "population": (
                "deaths in maximal sequences of at least three deaths where each "
                "consecutive gap is under 15 seconds"
            ),
            "trajectory_offsets_s": [-10, -5, 0],
            "grid": (
                "14x14; OpenDota game coordinates use (raw-64)/127; "
                "A-N west-east and 1-14 south-north; an internal boundary "
                "belongs to its east or north cell"
            ),
        },
        "sampling": {
            "maximum_absolute_tick_delta": max(tick_deltas),
            "maximum_absolute_time_delta_s": round(
                max(tick_deltas) / int(replay_positions["metadata"]["ticks_per_second"]),
                6,
            ),
        },
        "open_dota_position_crosscheck": crosscheck_open_dota_positions(
            match, replay_by_key
        ),
        "totals": {
            "events": len(events),
            "position_labels": len(events) * 3,
            "unique_trajectories": len(trajectories),
            "stationary_trajectories": sum(
                count for path, count in trajectories.items() if len(set(path)) == 1
            ),
            "death_cells_used": len(death_cells),
            "events_by_death_cell": dict(sorted(death_cells.items())),
        },
    }
    return ground_truth, audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-source", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.refresh_source:
        source = refresh_source()
    elif SOURCE_PATH.is_file():
        source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    else:
        raise SystemExit("source_events.json is missing; run with --refresh-source")
    if not POSITIONS_PATH.is_file():
        raise SystemExit("replay_positions.json is missing; run extract_replay_positions.py")
    replay_positions = json.loads(POSITIONS_PATH.read_text(encoding="utf-8"))

    ground_truth, audit = derive(source, replay_positions)
    if args.check:
        expected_gt = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
        expected_solution = json.loads(SOLUTION_PATH.read_text(encoding="utf-8"))
        expected_audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        if ground_truth != expected_gt or ground_truth != expected_solution:
            raise SystemExit("generated answer differs from checked-in ground truth")
        if audit != expected_audit:
            raise SystemExit("generated audit differs from checked-in audit")
        print("ground truth and audit are reproducible")
        return

    write_json(GROUND_TRUTH_PATH, ground_truth)
    write_json(SOLUTION_PATH, ground_truth)
    write_json(AUDIT_PATH, audit)
    print(stable_json(audit["totals"]).strip())


if __name__ == "__main__":
    main()
