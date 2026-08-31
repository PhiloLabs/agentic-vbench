#!/usr/bin/env python3
"""Extract the position evidence used by the ground-truth builder from a Valve replay."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
from typing import Any

from gem.combat.log import CombatLogEntry
from gem.extractors.players import PlayerExtractor
from gem.parser import ReplayParser


TASK_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = TASK_ROOT / "tools" / "source_events.json"
OUTPUT_PATH = TASK_ROOT / "tools" / "replay_positions.json"

MATCH_ID = 8730786393
LAST_CLOCK_S = 50 * 60 + 30
TICKS_PER_SECOND = 30
SAMPLE_INTERVAL_TICKS = 3
WORLD_UNITS_PER_RAW_CELL = 128
REPLAY_URL = "http://replay191.valve.net/570/8730786393_126439567.dem.bz2"
REPLAY_BZ2_SHA256 = "f5797e2cda60eadf125561c4b4221545977fb8d842055df94868e6bb8f4b16c5"


def stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def player_id(player_slot: int) -> int:
    return player_slot if player_slot < 128 else player_slot - 123


def source_deaths(source: dict[str, Any]) -> list[dict[str, Any]]:
    match = source["matches"][0]
    if int(match["match_id"]) != MATCH_ID:
        raise RuntimeError("source snapshot does not describe the pinned match")
    hero_to_player = {
        player["hero_key"]: player["canonical_player"] for player in match["players"]
    }
    deaths = []
    for killer in match["players"]:
        for event in killer["kills_log"]:
            time = int(event["time"])
            if 0 <= time <= LAST_CLOCK_S:
                deaths.append(
                    {
                        "time": time,
                        "victim": hero_to_player[event["victim_hero"]],
                        "victim_hero": event["victim_hero"],
                        "killer": killer["canonical_player"],
                    }
                )
    deaths = sorted(
        deaths,
        key=lambda item: (item["time"], item["victim"], item["killer"]),
    )
    return [
        item
        for item in deaths
        if any(
            int(fight["start"]) <= item["time"] <= int(fight["last_death"])
            for fight in match["teamfights"]
        )
    ]


def nearest_snapshot(
    snapshots: list[Any], target_tick: int
) -> tuple[Any, int]:
    snapshot = min(
        snapshots,
        key=lambda item: (abs(int(item.tick) - target_tick), int(item.tick) > target_tick),
    )
    return snapshot, int(snapshot.tick) - target_tick


def position(snapshot: Any, tick_delta: int) -> dict[str, int | float]:
    if snapshot.x is None or snapshot.y is None:
        raise RuntimeError(f"missing replay position at tick {snapshot.tick}")
    return {
        "sample_tick": int(snapshot.tick),
        "tick_delta": tick_delta,
        "world_x": round(float(snapshot.x), 6),
        "world_y": round(float(snapshot.y), 6),
        "raw_x": round(float(snapshot.x) / WORLD_UNITS_PER_RAW_CELL, 6),
        "raw_y": round(float(snapshot.y) / WORLD_UNITS_PER_RAW_CELL, 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    expected = source_deaths(source)

    replay_parser = ReplayParser(args.replay)
    players = PlayerExtractor(
        sample_interval=SAMPLE_INTERVAL_TICKS,
        minute_snapshots=False,
    )
    players.attach(replay_parser)
    replay_deaths: list[CombatLogEntry] = []

    def collect_death(entry: CombatLogEntry) -> None:
        if (
            entry.log_type == "DEATH"
            and entry.target_is_hero
            and not entry.target_is_illusion
            and not entry.will_reincarnate
            and entry.game_time_s is not None
            and 0 <= entry.game_time_s <= LAST_CLOCK_S
        ):
            replay_deaths.append(entry)

    replay_parser.on_combat_log_entry(collect_death)
    replay_parser.parse()

    all_actual_by_key = {
        (entry.game_time_s, entry.target_name): entry for entry in replay_deaths
    }
    expected_keys = {(item["time"], item["victim_hero"]) for item in expected}
    if not expected_keys <= set(all_actual_by_key) or len(all_actual_by_key) != len(replay_deaths):
        raise RuntimeError("OpenDota kill log and Valve replay death log do not align")

    match = source["matches"][0]
    hero_to_id = {
        player["hero_key"]: player_id(int(player["player_slot"]))
        for player in match["players"]
    }
    snapshots_by_player: dict[int, list[Any]] = {index: [] for index in range(10)}
    for snapshot in players.snapshots:
        if snapshot.player_id in snapshots_by_player:
            snapshots_by_player[snapshot.player_id].append(snapshot)

    events = []
    for item in expected:
        replay_death = all_actual_by_key[(item["time"], item["victim_hero"])]
        snapshots = snapshots_by_player[hero_to_id[item["victim_hero"]]]
        points = {}
        for label, seconds_before in (("minus_10s", 10), ("minus_5s", 5), ("death", 0)):
            target_tick = int(replay_death.tick) - seconds_before * TICKS_PER_SECOND
            snapshot, delta = nearest_snapshot(snapshots, target_tick)
            if abs(delta) > (SAMPLE_INTERVAL_TICKS + 1) // 2:
                raise RuntimeError(
                    f"nearest {label} position is {delta} ticks away for {item['victim']} "
                    f"at {item['time']}"
                )
            points[label] = position(snapshot, delta)
        events.append(
            {
                "time": item["time"],
                "victim": item["victim"],
                "killer": item["killer"],
                "victim_hero": item["victim_hero"],
                "death_tick": int(replay_death.tick),
                "positions": points,
            }
        )

    output = {
        "metadata": {
            "match_id": MATCH_ID,
            "replay_url": REPLAY_URL,
            "replay_bz2_sha256": REPLAY_BZ2_SHA256,
            "replay_dem_sha256": sha256_file(args.replay),
            "parser": "gem-dota",
            "parser_version": importlib.metadata.version("gem-dota"),
            "sample_interval_ticks": SAMPLE_INTERVAL_TICKS,
            "ticks_per_second": TICKS_PER_SECOND,
            "raw_coordinate_transform": "world_coordinate / 128",
            "event_scope": "OpenDota teamfight deaths within HUD 00:00-50:30",
        },
        "events": events,
    }
    args.output.write_text(stable_json(output), encoding="utf-8")
    print(f"wrote {len(events)} death trajectories to {args.output}")


if __name__ == "__main__":
    main()
