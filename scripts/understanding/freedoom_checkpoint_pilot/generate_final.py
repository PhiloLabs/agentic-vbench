#!/usr/bin/env python3
"""Generate the final six-episode Doom checkpoint-state benchmark media."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import vizdoom as vzd

import generate_pilot as pilot
from full_common import build_package


FPS = 35
OUTPUT_FRAME_STRIDE = 3
OUTPUT_FPS = f"{FPS}/{OUTPUT_FRAME_STRIDE}"
EPISODE_COUNT = 6
GAP_FRAMES = 2 * FPS
SEED = 20260728
WIDTH = 1280
HEIGHT = 720
TARGET_MIN_SECONDS = 420
TARGET_MAX_SECONDS = 455
EVENT_TYPES = {
    1: "key_pickup",
    2: "weapon_pickup",
    3: "switch_activate",
    4: "checkpoint_activate",
    5: "locked_door_open",
    6: "checkpoint_restore",
    7: "level_exit",
}
KEYS = {1: "blue_key", 2: "yellow_key", 3: "red_key"}
WEAPONS = {
    1: "pistol",
    2: "shotgun",
    3: "chaingun",
    4: "rocket_launcher",
    5: "plasma_rifle",
}
SWITCHES = {
    1: "switch_amber",
    2: "switch_cyan",
    3: "switch_violet",
    4: "switch_white",
}
CHECKPOINTS = {1: "checkpoint_alpha", 2: "checkpoint_beta"}
DOORS = {1: "door_blue", 2: "door_yellow", 3: "door_red"}
ENTITIES = {
    "key_pickup": KEYS,
    "weapon_pickup": WEAPONS,
    "switch_activate": SWITCHES,
    "checkpoint_activate": CHECKPOINTS,
    "locked_door_open": DOORS,
    "checkpoint_restore": CHECKPOINTS,
    "level_exit": {1: "episode_exit"},
}
ACTORS = {
    (1, 1): "AVBlueKey",
    (1, 2): "AVYellowKey",
    (1, 3): "AVRedKey",
    (2, 2): "AVShotgun",
    (2, 3): "AVChaingun",
    (2, 4): "AVRocketLauncher",
    (2, 5): "AVPlasmaRifle",
    (3, 1): "AVAmberSwitch",
    (3, 2): "AVCyanSwitch",
    (3, 3): "AVVioletSwitch",
    (3, 4): "AVWhiteSwitch",
    (4, 1): "AVCheckpointAlpha",
    (4, 2): "AVCheckpointBeta",
    (5, 1): "AVBlueDoor",
    (5, 2): "AVYellowDoor",
    (5, 3): "AVRedDoor",
    (7, 1): "AVEpisodeExit",
}
DISTRACTORS = ("HealthBonus", "ArmorBonus", "Stimpack", "Clip")
TRACKED_ACTORS = tuple(ACTORS.values()) + DISTRACTORS + ("TeleportFog",)
USER_VARIABLES = tuple(
    getattr(vzd.GameVariable, f"USER{index}") for index in range(41, 55)
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _configure_game(seed: int, package_path: Path) -> vzd.DoomGame:
    game = pilot._configure_game(seed)
    game.set_episode_timeout(FPS * 520)
    game.add_game_args(f"-file {package_path}")
    game.add_available_button(vzd.Button.USE)
    for variable in USER_VARIABLES:
        game.add_available_game_variable(variable)
    return game


def _mask_names(mask: int, vocabulary: dict[int, str]) -> list[str]:
    return [
        name
        for identifier, name in vocabulary.items()
        if mask & (1 << (identifier - 1))
    ]


class LedgerRecorder:
    def __init__(self, game: vzd.DoomGame) -> None:
        pilot.TRACKED_ACTORS = TRACKED_ACTORS
        self.video = pilot.Recorder()
        self.game = game
        self.events: list[dict[str, Any]] = []
        self.last_sequence = 0

    @property
    def frame_index(self) -> int:
        return self.video.frame_index

    def users(self) -> list[int]:
        return [
            int(self.game.get_game_variable(variable))
            for variable in USER_VARIABLES
        ]

    def step(
        self,
        button: vzd.Button | None = None,
    ) -> vzd.GameState:
        state = pilot._step(self.game, self.video, button)
        values = self.users()
        sequence = values[0]
        if sequence == self.last_sequence:
            return state
        if sequence != self.last_sequence + 1:
            raise RuntimeError(
                f"non-atomic event sequence {self.last_sequence}->{sequence}"
            )
        event_type = EVENT_TYPES.get(values[1])
        if event_type is None:
            raise RuntimeError(f"unknown ACS event type {values[1]}")
        entity = ENTITIES[event_type].get(values[2])
        if entity is None:
            raise RuntimeError(
                f"unknown ACS entity {values[2]} for {event_type}"
            )
        active_weapon = WEAPONS.get(values[9])
        if active_weapon is None:
            raise RuntimeError(f"unknown ACS weapon {values[9]}")
        checkpoint = (
            None
            if values[13] == 0
            else CHECKPOINTS.get(values[13])
        )
        if values[13] and checkpoint is None:
            raise RuntimeError(f"unknown ACS checkpoint {values[13]}")
        self.events.append(
            {
                "timestamp_ms": round(self.frame_index * 1000 / FPS),
                "event_type": event_type,
                "entity_id": entity,
                "state": {
                    "active_weapon": active_weapon,
                    "held_keys": _mask_names(values[10], KEYS),
                    "active_switches": _mask_names(values[11], SWITCHES),
                    "open_doors": _mask_names(values[12], DOORS),
                    "current_checkpoint": checkpoint,
                },
            }
        )
        self.last_sequence = sequence
        return state

    def wait(self, frames: int) -> None:
        for _ in range(frames):
            self.step()

    def command(self, command: str) -> None:
        self.game.send_game_command(command)
        self.step()


def _spawn(
    recorder: LedgerRecorder,
    kind: int,
    entity_id: int,
    actor_tid: int,
) -> None:
    actor = ACTORS[(kind, entity_id)]
    for _ in range(12):
        recorder.command(f"pukename AVSpawn {kind} {entity_id} {actor_tid}")
        state = recorder.video.last_state
        if state is not None and any(
            obj.name == actor for obj in state.objects
        ):
            recorder.wait(FPS * 2)
            return
        recorder.command(f"pukename AVRemove {actor_tid}")
        for _ in range(7):
            recorder.step(vzd.Button.TURN_LEFT)
    raise RuntimeError(f"could not spawn {actor} in reachable space")


def _collect(
    recorder: LedgerRecorder,
    kind: int,
    entity_id: int,
    actor_tid: int,
) -> dict[str, Any]:
    actor = ACTORS[(kind, entity_id)]
    before = recorder.last_sequence
    _spawn(recorder, kind, entity_id, actor_tid)
    for _ in range(FPS * 2):
        recorder.step(vzd.Button.MOVE_FORWARD)
        if recorder.last_sequence == before + 1:
            break
    else:
        raise RuntimeError(f"{actor} did not emit a pickup event")
    event_frame = recorder.frame_index
    recorder.wait(FPS)
    return {
        "actor": actor,
        "event_frame": event_frame,
        "event_sequence": recorder.last_sequence,
    }


def _use(
    recorder: LedgerRecorder,
    kind: int,
    entity_id: int,
    actor_tid: int,
    scored: bool,
) -> dict[str, Any]:
    actor = ACTORS[(kind, entity_id)]
    before = recorder.last_sequence
    _spawn(recorder, kind, entity_id, actor_tid)
    for _ in range(8):
        recorder.step(vzd.Button.USE)
        if recorder.last_sequence != before:
            break
    emitted = recorder.last_sequence == before + 1
    if emitted != scored:
        raise RuntimeError(
            f"{actor} scored={emitted}, expected scored={scored}"
        )
    event_frame = recorder.frame_index if emitted else None
    recorder.wait(FPS)
    recorder.command(f"pukename AVRemove {actor_tid}")
    return {
        "actor": actor,
        "event_frame": event_frame,
        "event_sequence": recorder.last_sequence if emitted else None,
        "scored": emitted,
    }


def _restore(recorder: LedgerRecorder) -> dict[str, Any]:
    before_sequence = recorder.last_sequence
    before_position = pilot._player_xy(recorder.game)
    before_weapon = int(
        recorder.game.get_game_variable(vzd.GameVariable.SELECTED_WEAPON)
    )
    recorder.command("pukename AVRestore")
    if recorder.last_sequence != before_sequence + 1:
        raise RuntimeError("restore did not emit exactly one event")
    after_position = pilot._player_xy(recorder.game)
    after_weapon = int(
        recorder.game.get_game_variable(vzd.GameVariable.SELECTED_WEAPON)
    )
    recorder.wait(FPS * 2)
    return {
        "event_frame": recorder.frame_index - FPS * 2,
        "event_sequence": recorder.last_sequence,
        "from_position": [round(value, 3) for value in before_position],
        "to_position": [round(value, 3) for value in after_position],
        "displacement": round(math.dist(before_position, after_position), 3),
        "weapon_before": before_weapon,
        "weapon_after": after_weapon,
    }


def _route(
    recorder: LedgerRecorder,
    rng: random.Random,
    frames: int,
) -> None:
    remaining = frames
    turn = rng.choice((vzd.Button.TURN_LEFT, vzd.Button.TURN_RIGHT))
    while remaining:
        segment = min(remaining, rng.randint(12, 28))
        choice = rng.choices((turn, None), weights=(6, 1))[0]
        for _ in range(segment):
            recorder.step(choice)
        remaining -= segment
        if rng.random() < 0.35:
            turn = (
                vzd.Button.TURN_RIGHT
                if turn == vzd.Button.TURN_LEFT
                else vzd.Button.TURN_LEFT
            )


def _move_away(
    recorder: LedgerRecorder,
    rng: random.Random,
    minimum_distance: float = 96,
) -> None:
    start = pilot._player_xy(recorder.game)
    for _ in range(12):
        turn = rng.choice((vzd.Button.TURN_LEFT, vzd.Button.TURN_RIGHT))
        for _ in range(rng.randint(5, 18)):
            recorder.step(turn)
        for _ in range(FPS * 2):
            recorder.step(vzd.Button.MOVE_FORWARD)
            if math.dist(start, pilot._player_xy(recorder.game)) >= minimum_distance:
                return
    raise RuntimeError("could not move away from checkpoint")


def _show_distractor(
    recorder: LedgerRecorder,
    rng: random.Random,
) -> str:
    actor = rng.choice(DISTRACTORS)
    recorder.game.send_game_command(f"summon {actor}")
    recorder.step()
    _route(recorder, rng, rng.randint(FPS * 2, FPS * 4))
    return actor


def _episode_plan(rng: random.Random) -> list[tuple[str, int]]:
    keys = list(KEYS)
    weapons = [2, 3, 4, 5]
    switches = list(SWITCHES)
    rng.shuffle(keys)
    rng.shuffle(weapons)
    rng.shuffle(switches)

    first = [
        ("key", keys[0]),
        ("weapon", weapons[0]),
        ("switch", switches[0]),
    ]
    rng.shuffle(first)
    first_after = [
        ("switch", switches[1]),
        ("door", keys[0]),
    ]
    rng.shuffle(first_after)

    second = [
        ("key", keys[1]),
        ("weapon", weapons[1]),
        ("switch", switches[2]),
    ]
    rng.shuffle(second)
    second_after = [
        ("switch", switches[3]),
        ("door", keys[1]),
    ]
    rng.shuffle(second_after)

    third_prefix = [("key", keys[2]), ("weapon", weapons[2])]
    rng.shuffle(third_prefix)
    third_suffix = [("door", keys[2]), ("weapon", weapons[3])]
    rng.shuffle(third_suffix)
    return [
        *first,
        ("checkpoint", 1),
        *first_after,
        ("restore", 1),
        ("switch", switches[1]),
        *second,
        ("checkpoint", 2),
        *second_after,
        ("restore", 2),
        ("switch", switches[3]),
        *third_prefix,
        *third_suffix,
        ("restore", 2),
        ("switch", switches[3]),
        ("exit", 1),
    ]


def _validate_events(events: list[dict[str, Any]]) -> None:
    if len(events) != 23:
        raise RuntimeError(f"expected 23 events, found {len(events)}")
    weapon = "pistol"
    keys: set[str] = set()
    switches: set[str] = set()
    doors: set[str] = set()
    checkpoint: str | None = None
    snapshots: dict[str, set[str]] = {}
    previous_timestamp = -1

    def ordered(
        values: set[str],
        vocabulary: dict[int, str],
    ) -> list[str]:
        return [value for value in vocabulary.values() if value in values]

    for index, event in enumerate(events):
        timestamp = event["timestamp_ms"]
        if timestamp <= previous_timestamp:
            raise RuntimeError("event timestamps are not strictly increasing")
        previous_timestamp = timestamp
        event_type = event["event_type"]
        entity = event["entity_id"]
        if event_type == "key_pickup":
            if entity in keys:
                raise RuntimeError("duplicate key pickup")
            keys.add(entity)
        elif event_type == "weapon_pickup":
            weapon = entity
        elif event_type == "switch_activate":
            if entity in switches:
                raise RuntimeError("switch activated without rollback")
            switches.add(entity)
        elif event_type == "checkpoint_activate":
            checkpoint = entity
            snapshots[entity] = set(switches)
        elif event_type == "locked_door_open":
            required_key = entity.removeprefix("door_") + "_key"
            if required_key not in keys or entity in doors:
                raise RuntimeError("invalid locked-door transition")
            doors.add(entity)
        elif event_type == "checkpoint_restore":
            if entity != checkpoint or checkpoint not in snapshots:
                raise RuntimeError("invalid checkpoint restore")
            switches = set(snapshots[checkpoint])
        elif event_type == "level_exit":
            if index != len(events) - 1:
                raise RuntimeError("level exit is not final")
        expected = {
            "active_weapon": weapon,
            "held_keys": ordered(keys, KEYS),
            "active_switches": ordered(switches, SWITCHES),
            "open_doors": ordered(doors, DOORS),
            "current_checkpoint": checkpoint,
        }
        if event["state"] != expected:
            raise RuntimeError(
                f"event {index + 1} state mismatch: "
                f"{event['state']} != {expected}"
            )


def _validate_observability(
    recorder: LedgerRecorder,
    actor_events: list[dict[str, Any]],
    restores: list[dict[str, Any]],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for event in actor_events:
        if not event["scored"]:
            continue
        track = recorder.video.actor_tracks[event["actor"]]
        run, gap = pilot._qualifying_run_before(
            track,
            event["event_frame"],
            minimum_area=256,
            maximum_gap=FPS // 3,
        )
        passed = run >= FPS and gap <= FPS // 3
        checks.append(
            {
                "actor": event["actor"],
                "event_sequence": event["event_sequence"],
                "visible_run": run,
                "visibility_gap": gap,
                "max_bbox_area": track.max_bbox_area,
                "pass": passed,
            }
        )
        if not passed:
            raise RuntimeError(f"actor observability failed: {checks[-1]}")
    for restore in restores:
        passed = (
            restore["displacement"] >= 48
            and restore["weapon_before"] == restore["weapon_after"]
        )
        restore["pass"] = passed
        if not passed:
            raise RuntimeError(f"restore observability failed: {restore}")
    fog = recorder.video.actor_tracks["TeleportFog"]
    if fog.visible_frames < len(restores) * 2:
        raise RuntimeError("restore teleport effects were not visible")
    return {
        "actor_checks": checks,
        "restore_checks": restores,
        "teleport_fog_visible_frames": fog.visible_frames,
        "all_passed": True,
    }


def _record_episode(
    episode_dir: Path,
    episode_index: int,
    seed: int,
    package_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    rng = random.Random(seed)
    pilot.WEAPON_NAMES.update(
        {
            4: "chaingun",
            5: "rocket_launcher",
            6: "plasma_rifle",
        }
    )
    game = _configure_game(seed, package_path)
    game.init()
    demo_path = episode_dir / "episode.lmp"
    game.new_episode(str(demo_path))
    game.send_game_command("god")
    game.send_game_command("give Pistol")
    recorder = LedgerRecorder(game)
    recorder.step()
    recorder.command("pukename AVReset")
    recorder.wait(FPS * 3)

    actor_events: list[dict[str, Any]] = []
    restores: list[dict[str, Any]] = []
    distractors: list[str] = []
    failed_interactions: list[dict[str, Any]] = []
    plan = _episode_plan(rng)
    distractor_steps = set(rng.sample(range(len(plan) - 1), 6))
    for step_index, (kind, entity_id) in enumerate(plan[:-1]):
        if kind == "key":
            failed_interactions.append(
                _use(
                    recorder,
                    5,
                    entity_id,
                    200 + entity_id,
                    scored=False,
                )
            )
            actor_events.append(
                {
                    **_collect(
                        recorder,
                        1,
                        entity_id,
                        310 + entity_id,
                    ),
                    "scored": True,
                }
            )
        elif kind == "weapon":
            actor_events.append(
                {
                    **_collect(
                        recorder,
                        2,
                        entity_id,
                        320 + entity_id,
                    ),
                    "scored": True,
                }
            )
        elif kind == "switch":
            actor_events.append(
                _use(
                    recorder,
                    3,
                    entity_id,
                    100 + entity_id,
                    scored=True,
                )
            )
        elif kind == "checkpoint":
            actor_events.append(
                {
                    **_collect(
                        recorder,
                        4,
                        entity_id,
                        400 + entity_id,
                    ),
                    "scored": True,
                }
            )
        elif kind == "door":
            actor_events.append(
                _use(
                    recorder,
                    5,
                    entity_id,
                    200 + entity_id,
                    scored=True,
                )
            )
        elif kind == "restore":
            _move_away(recorder, rng)
            restores.append(_restore(recorder))
        else:
            raise RuntimeError(f"unknown plan step {kind}")

        _route(
            recorder,
            rng,
            rng.randint(FPS * 9, FPS * 14),
        )
        if step_index in distractor_steps:
            distractors.append(_show_distractor(recorder, rng))

    target_frames = rng.randint(
        TARGET_MIN_SECONDS * FPS,
        (TARGET_MAX_SECONDS - 3) * FPS,
    )
    while recorder.frame_index < target_frames:
        _route(
            recorder,
            rng,
            min(
                target_frames - recorder.frame_index,
                rng.randint(FPS * 2, FPS * 5),
            ),
        )

    actor_events.append(
        _use(recorder, 7, 1, 701, scored=True)
    )
    recorder.wait(FPS * 2)
    game.close()

    _validate_events(recorder.events)
    observability = _validate_observability(
        recorder,
        actor_events,
        restores,
    )
    duration_seconds = len(recorder.video.frame_hashes) / FPS
    if not TARGET_MIN_SECONDS <= duration_seconds <= TARGET_MAX_SECONDS:
        raise RuntimeError(
            f"episode duration outside final target: {duration_seconds}"
        )
    episode_id = f"episode_{episode_index:02d}"
    return (
        {"episode_id": episode_id, "events": recorder.events},
        {
            "episode_id": episode_id,
            "seed": seed,
            "duration_seconds": duration_seconds,
            "frame_count": len(recorder.video.frame_hashes),
            "frame_hashes": recorder.video.frame_hashes,
            "demo_path": str(demo_path),
            "event_count": len(recorder.events),
            "plan": plan,
            "distractors": distractors,
            "failed_interaction_count": len(failed_interactions),
            "observability": observability,
        },
    )


def _render_replays(
    output_dir: Path,
    episode_audits: list[dict[str, Any]],
    package_path: Path,
    ffmpeg: str,
    ffprobe: str,
) -> dict[str, Any]:
    video_path = output_dir / "doom-checkpoint-state-tracking.mp4"
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pixel_format",
        "rgb24",
        "-video_size",
        f"{WIDTH}x{HEIGHT}",
        "-framerate",
        OUTPUT_FPS,
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        pilot._tool_path(video_path, ffmpeg),
    ]
    encoder = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if encoder.stdin is None:
        raise RuntimeError("failed to open ffmpeg input")
    black = bytes(WIDTH * HEIGHT * 3)
    output_frames = 0
    mismatches: list[dict[str, int]] = []
    episode_offsets: list[int] = []
    try:
        for episode_index, audit in enumerate(episode_audits):
            episode_offsets.append(output_frames)
            game = _configure_game(audit["seed"], package_path)
            try:
                game.init()
                game.replay_episode(audit["demo_path"])
                for frame_index, expected_hash in enumerate(
                    audit["frame_hashes"]
                ):
                    game.advance_action()
                    if game.is_episode_finished():
                        raise RuntimeError(
                            f"replay ended early in episode {episode_index + 1}"
                        )
                    state = game.get_state()
                    if state is None:
                        raise RuntimeError("replay returned no state")
                    frame = state.screen_buffer
                    actual_hash = hashlib.sha256(
                        frame.tobytes()
                    ).hexdigest()
                    if actual_hash != expected_hash:
                        mismatches.append(
                            {
                                "episode": episode_index + 1,
                                "frame": frame_index,
                            }
                        )
                    if frame_index % OUTPUT_FRAME_STRIDE == 0:
                        encoder.stdin.write(frame.tobytes())
                        output_frames += 1
            finally:
                game.close()
            if episode_index + 1 < len(episode_audits):
                for frame_index in range(GAP_FRAMES):
                    if frame_index % OUTPUT_FRAME_STRIDE == 0:
                        encoder.stdin.write(black)
                        output_frames += 1
        encoder.stdin.close()
        stderr = encoder.stderr.read().decode("utf-8", errors="replace")
        return_code = encoder.wait()
        if return_code:
            raise RuntimeError(f"ffmpeg failed: {stderr.strip()}")
    except BaseException:
        if not encoder.stdin.closed:
            encoder.stdin.close()
        if encoder.poll() is None:
            encoder.terminate()
            encoder.wait(timeout=10)
        raise
    if mismatches:
        raise RuntimeError(f"replay mismatches: {mismatches[:10]}")

    probe = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,avg_frame_rate,nb_frames:format=duration",
            "-of",
            "json",
            pilot._tool_path(video_path, ffprobe),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(probe.stdout)
    stream = data["streams"][0]
    measured = {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "avg_frame_rate": stream["avg_frame_rate"],
        "nb_frames": int(stream["nb_frames"]),
        "duration_seconds": float(data["format"]["duration"]),
    }
    if (
        measured["width"] != WIDTH
        or measured["height"] != HEIGHT
        or measured["nb_frames"] != output_frames
        or not 42 * 60 <= measured["duration_seconds"] <= 48 * 60
    ):
        raise RuntimeError(f"rendered video failed final gates: {measured}")
    return {
        "path": str(video_path),
        "sha256": _sha256(video_path),
        "output_frame_stride": OUTPUT_FRAME_STRIDE,
        "replay_hash_mismatch_count": 0,
        "episode_output_frame_offsets": episode_offsets,
        "ffprobe": measured,
    }


def _publish_task_artifacts(
    task_dir: Path,
    video_path: Path,
    ground_truth: dict[str, Any],
) -> None:
    media_path = task_dir / "environment" / video_path.name
    media_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(video_path, media_path)
    (media_path.parent / f"{video_path.name}.sha256").write_text(
        f"{_sha256(media_path)}  {media_path.name}\n",
        encoding="utf-8",
    )
    _write_json(
        task_dir / "steps" / "solve" / "tests" / "ground_truth.json",
        ground_truth,
    )
    _write_json(
        task_dir / "steps" / "solve" / "solution" / "oracle.json",
        ground_truth,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/doom-checkpoint-state-tracking"),
    )
    parser.add_argument("--task-dir", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--ffprobe", required=True)
    parser.add_argument("--acc", required=True, type=Path)
    parser.add_argument("--acc-include", required=True, type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix=".doom-final-staging-",
        dir=output_dir.parent,
    ) as temporary:
        staging = Path(temporary)
        package_path = staging / "avbench.pk3"
        build_package(package_path, args.acc, args.acc_include)
        episodes: list[dict[str, Any]] = []
        audits: list[dict[str, Any]] = []
        for episode_index in range(1, EPISODE_COUNT + 1):
            episode_dir = staging / f"episode_{episode_index:02d}"
            episode_dir.mkdir()
            episode, audit = _record_episode(
                episode_dir,
                episode_index,
                args.seed + episode_index * 1009,
                package_path,
            )
            episodes.append(episode)
            audits.append(audit)
            print(
                f"recorded {episode['episode_id']}: "
                f"{audit['duration_seconds']:.3f}s, "
                f"{audit['event_count']} events",
                flush=True,
            )

        ground_truth = {"episodes": episodes}
        render = _render_replays(
            staging,
            audits,
            package_path,
            args.ffmpeg,
            args.ffprobe,
        )
        final_video = output_dir / "doom-checkpoint-state-tracking.mp4"
        shutil.copyfile(render["path"], final_video)
        audit_document = {
            "status": "pass",
            "scope": "final benchmark media",
            "ground_truth_tier": "logged",
            "manual_event_annotations": 0,
            "event_count": sum(
                len(episode["events"]) for episode in episodes
            ),
            "episodes": [
                {
                    key: value
                    for key, value in audit.items()
                    if key not in {"frame_hashes", "demo_path"}
                }
                for audit in audits
            ],
            "render": {**render, "path": final_video.name},
            "source_sha256": {
                "generator": _sha256(Path(__file__)),
                "acs": _sha256(
                    Path(__file__).with_name("full_assets") / "avbench.acs"
                ),
                "decorate": _sha256(
                    Path(__file__).with_name("full_assets") / "DECORATE"
                ),
            },
        }
        _write_json(output_dir / "ground_truth.json", ground_truth)
        _write_json(output_dir / "generation_audit.json", audit_document)
        _publish_task_artifacts(
            args.task_dir.resolve(),
            final_video,
            ground_truth,
        )
        print(json.dumps(audit_document["render"], indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        raise
