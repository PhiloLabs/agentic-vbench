#!/usr/bin/env python3
"""Generate a zero-annotation ViZDoom ledger pilot and audit its replay."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import vizdoom as vzd

from verify_ledger import score_documents


FPS = 35
SEED = 20260725
WIDTH = 1280
HEIGHT = 720
TRACKED_ACTORS = (
    "BlueCard",
    "Shotgun",
    "Megasphere",
    "RedCard",
    "TeleportFog",
)
WEAPON_NAMES = {2: "pistol", 3: "shotgun"}
EXPECTED_VIDEO_SHA256 = (
    "eff6287b10c494f837600761f02cd5221cde2eb665f59b309743424e2787fd67"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _configure_game(seed: int) -> vzd.DoomGame:
    package_dir = Path(vzd.__file__).resolve().parent
    game = vzd.DoomGame()
    game.load_config(str(package_dir / "scenarios" / "health_gathering.cfg"))
    game.set_seed(seed)
    game.set_screen_resolution(vzd.ScreenResolution.RES_1280X720)
    game.set_screen_format(vzd.ScreenFormat.RGB24)
    game.set_labels_buffer_enabled(True)
    game.set_objects_info_enabled(True)
    game.set_sectors_info_enabled(True)
    game.set_render_hud(False)
    game.set_render_minimal_hud(False)
    game.set_render_messages(False)
    game.set_render_crosshair(False)
    game.set_render_weapon(True)
    game.set_window_visible(False)
    game.set_episode_timeout(FPS * 60)
    for variable in (
        vzd.GameVariable.ITEMCOUNT,
        vzd.GameVariable.SELECTED_WEAPON,
        vzd.GameVariable.WEAPON3,
        vzd.GameVariable.POSITION_X,
        vzd.GameVariable.POSITION_Y,
        vzd.GameVariable.ANGLE,
    ):
        game.add_available_game_variable(variable)
    return game


@dataclass
class ActorTrack:
    visible_frames: int = 0
    first_visible_frame: int | None = None
    last_visible_frame: int | None = None
    max_bbox_area: int = 0
    max_bbox_width: int = 0
    max_bbox_height: int = 0
    frame_areas: dict[int, int] = field(default_factory=dict)


@dataclass
class Recorder:
    frame_hashes: list[str] = field(default_factory=list)
    actor_tracks: dict[str, ActorTrack] = field(
        default_factory=lambda: {name: ActorTrack() for name in TRACKED_ACTORS}
    )
    last_state: vzd.GameState | None = None

    @property
    def frame_index(self) -> int:
        return len(self.frame_hashes) - 1

    def capture(self, state: vzd.GameState) -> None:
        frame = state.screen_buffer
        if frame.shape != (HEIGHT, WIDTH, 3):
            raise RuntimeError(f"unexpected screen shape: {frame.shape}")
        self.frame_hashes.append(hashlib.sha256(frame.tobytes()).hexdigest())
        frame_index = self.frame_index
        visible: dict[str, tuple[int, int, int]] = {}
        for label in state.labels:
            actor = label.object_name
            if actor not in self.actor_tracks:
                continue
            area = int(label.width) * int(label.height)
            previous = visible.get(actor)
            if previous is None or area > previous[0]:
                visible[actor] = (area, int(label.width), int(label.height))
        for actor, (area, width, height) in visible.items():
            track = self.actor_tracks[actor]
            track.visible_frames += 1
            track.first_visible_frame = (
                frame_index
                if track.first_visible_frame is None
                else track.first_visible_frame
            )
            track.last_visible_frame = frame_index
            track.max_bbox_width = max(track.max_bbox_width, width)
            track.max_bbox_height = max(track.max_bbox_height, height)
            track.max_bbox_area = max(track.max_bbox_area, area)
            track.frame_areas[frame_index] = area
        self.last_state = state


def _qualifying_run_before(
    track: ActorTrack,
    event_frame: int,
    minimum_area: int,
    maximum_gap: int,
) -> tuple[int, int]:
    run = 0
    frame = event_frame - 1
    gap = 0
    while gap <= maximum_gap and track.frame_areas.get(frame, 0) < minimum_area:
        gap += 1
        frame -= 1
    while track.frame_areas.get(frame, 0) >= minimum_area:
        run += 1
        frame -= 1
    return run, gap


def _longest_qualifying_run(track: ActorTrack, minimum_area: int) -> int:
    longest = 0
    current = 0
    previous_frame: int | None = None
    for frame, area in sorted(track.frame_areas.items()):
        if area < minimum_area:
            current = 0
        elif previous_frame is not None and frame == previous_frame + 1:
            current += 1
        else:
            current = 1
        longest = max(longest, current)
        previous_frame = frame
    return longest


def _objects(state: vzd.GameState) -> dict[str, list[Any]]:
    result: dict[str, list[Any]] = {}
    for obj in state.objects:
        result.setdefault(obj.name, []).append(obj)
    return result


def _player_xy(game: vzd.DoomGame) -> tuple[float, float]:
    return (
        float(game.get_game_variable(vzd.GameVariable.POSITION_X)),
        float(game.get_game_variable(vzd.GameVariable.POSITION_Y)),
    )


def _active_weapon(game: vzd.DoomGame) -> str:
    weapon = int(game.get_game_variable(vzd.GameVariable.SELECTED_WEAPON))
    return WEAPON_NAMES.get(weapon, f"weapon_{weapon}")


def _action(game: vzd.DoomGame, button: vzd.Button | None = None) -> list[int]:
    buttons = game.get_available_buttons()
    values = [0] * len(buttons)
    if button is not None:
        values[buttons.index(button)] = 1
    return values


def _step(
    game: vzd.DoomGame, recorder: Recorder, button: vzd.Button | None = None
) -> vzd.GameState:
    game.make_action(_action(game, button))
    if game.is_episode_finished():
        raise RuntimeError("pilot episode ended unexpectedly")
    state = game.get_state()
    if state is None:
        raise RuntimeError("ViZDoom returned no state")
    recorder.capture(state)
    return state


def _wait(game: vzd.DoomGame, recorder: Recorder, frames: int) -> None:
    for _ in range(frames):
        _step(game, recorder)


def _spawn_and_collect(
    game: vzd.DoomGame,
    recorder: Recorder,
    actor: str,
    expected_weapon: int | None = None,
) -> dict[str, Any]:
    game.send_game_command(f"summon {actor}")
    state = _step(game, recorder)
    actor_objects = _objects(state).get(actor, [])
    if len(actor_objects) != 1:
        raise RuntimeError(f"expected one {actor}, found {len(actor_objects)}")
    target_xy = (
        float(actor_objects[0].position_x),
        float(actor_objects[0].position_y),
    )
    _wait(game, recorder, FPS + FPS // 2)

    last_target_xy = target_xy
    for _ in range(FPS):
        state = _step(game, recorder, vzd.Button.MOVE_FORWARD)
        actor_objects = _objects(state).get(actor, [])
        if actor_objects:
            last_target_xy = (
                float(actor_objects[0].position_x),
                float(actor_objects[0].position_y),
            )
            continue
        disappearance_frame = recorder.frame_index
        break
    else:
        raise RuntimeError(f"{actor} was not collected")

    if expected_weapon is not None:
        for _ in range(FPS):
            if (
                int(game.get_game_variable(vzd.GameVariable.SELECTED_WEAPON))
                == expected_weapon
            ):
                break
            _step(game, recorder)
        else:
            raise RuntimeError(f"weapon {expected_weapon} never became active")

    player_xy = _player_xy(game)
    return {
        "event_frame": recorder.frame_index,
        "disappearance_frame": disappearance_frame,
        "last_actor_position": [round(v, 3) for v in last_target_xy],
        "player_position": [round(v, 3) for v in player_xy],
        "pickup_distance": round(math.dist(last_target_xy, player_xy), 3),
    }


def _event(
    recorder: Recorder,
    event_type: str,
    entity_id: str,
    game: vzd.DoomGame,
    held_keys: list[str],
    current_checkpoint: str | None,
) -> dict[str, Any]:
    return {
        "timestamp_ms": round(recorder.frame_index * 1000 / FPS),
        "event_type": event_type,
        "entity_id": entity_id,
        "state": {
            "active_weapon": _active_weapon(game),
            "held_keys": sorted(held_keys),
            "active_switches": [],
            "current_checkpoint": current_checkpoint,
        },
    }


def _record_demo(output_dir: Path, seed: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    demo_path = output_dir / "pilot.lmp"
    game = _configure_game(seed)
    game.init()
    game.new_episode(str(demo_path))
    recorder = Recorder()
    held_keys: list[str] = []
    current_checkpoint: str | None = None
    events: list[dict[str, Any]] = []
    collection_audit: dict[str, Any] = {}

    game.send_game_command("give Pistol")
    _step(game, recorder)
    _wait(game, recorder, FPS * 2)
    if _active_weapon(game) != "pistol":
        raise RuntimeError("pilot initial weapon did not settle to pistol")

    collection_audit["BlueCard"] = _spawn_and_collect(game, recorder, "BlueCard")
    held_keys.append("blue_key")
    events.append(
        _event(
            recorder,
            "key_pickup",
            "blue_key",
            game,
            held_keys,
            current_checkpoint,
        )
    )
    _wait(game, recorder, FPS)

    collection_audit["Shotgun"] = _spawn_and_collect(
        game, recorder, "Shotgun", expected_weapon=3
    )
    events.append(
        _event(
            recorder,
            "weapon_pickup",
            "shotgun",
            game,
            held_keys,
            current_checkpoint,
        )
    )
    _wait(game, recorder, FPS)

    collection_audit["Megasphere"] = _spawn_and_collect(
        game, recorder, "Megasphere"
    )
    current_checkpoint = "checkpoint_alpha"
    checkpoint_xy = _player_xy(game)
    events.append(
        _event(
            recorder,
            "checkpoint_activate",
            current_checkpoint,
            game,
            held_keys,
            current_checkpoint,
        )
    )
    _wait(game, recorder, FPS)

    game.send_game_command("summon RedCard")
    _step(game, recorder)
    _wait(game, recorder, FPS)
    for _ in range(FPS):
        _step(game, recorder, vzd.Button.TURN_LEFT)
    for _ in range(FPS):
        _step(game, recorder, vzd.Button.MOVE_FORWARD)
    _wait(game, recorder, FPS // 2)

    restore_from_xy = _player_xy(game)
    weapon_before_restore = _active_weapon(game)
    itemcount_before_restore = int(
        game.get_game_variable(vzd.GameVariable.ITEMCOUNT)
    )
    shotgun_owned_before_restore = bool(
        game.get_game_variable(vzd.GameVariable.WEAPON3)
    )
    game.send_game_command("summon TeleportFog")
    _step(game, recorder)
    _wait(game, recorder, 8)
    game.send_game_command(
        f"warp {int(round(checkpoint_xy[0]))} {int(round(checkpoint_xy[1]))}"
    )
    _step(game, recorder)
    game.send_game_command("summon TeleportFog")
    _step(game, recorder)
    restore_to_xy = _player_xy(game)
    restore_event_frame = recorder.frame_index
    events.append(
        _event(
            recorder,
            "checkpoint_restore",
            current_checkpoint,
            game,
            held_keys,
            current_checkpoint,
        )
    )
    _wait(game, recorder, FPS * 2)

    final_state = recorder.last_state
    distractor_survived = bool(
        final_state and _objects(final_state).get("RedCard")
    )
    weapon_after_restore = _active_weapon(game)
    itemcount_after_restore = int(
        game.get_game_variable(vzd.GameVariable.ITEMCOUNT)
    )
    shotgun_owned_after_restore = bool(
        game.get_game_variable(vzd.GameVariable.WEAPON3)
    )
    game.close()

    for actor, collection in collection_audit.items():
        qualifying_run, visibility_gap = _qualifying_run_before(
            recorder.actor_tracks[actor],
            collection["disappearance_frame"],
            minimum_area=1024,
            maximum_gap=FPS // 4,
        )
        collection["qualifying_visible_run_before_disappearance"] = qualifying_run
        collection["qualifying_visibility_gap_frames"] = visibility_gap

    actor_tracks = {
        name: {
            "visible_frames": track.visible_frames,
            "first_visible_frame": track.first_visible_frame,
            "last_visible_frame": track.last_visible_frame,
            "max_bbox_area": track.max_bbox_area,
            "max_bbox_width": track.max_bbox_width,
            "max_bbox_height": track.max_bbox_height,
            "longest_qualifying_run": _longest_qualifying_run(
                track, minimum_area=1024
            ),
        }
        for name, track in recorder.actor_tracks.items()
    }
    audit = {
        "seed": seed,
        "fps": FPS,
        "resolution": [WIDTH, HEIGHT],
        "frame_count": len(recorder.frame_hashes),
        "frame_hashes": recorder.frame_hashes,
        "actor_tracks": actor_tracks,
        "collections": collection_audit,
        "distractor": {
            "actor": "RedCard",
            "visible_but_not_collected": distractor_survived,
        },
        "restore": {
            "checkpoint_position": [round(v, 3) for v in checkpoint_xy],
            "from_position": [round(v, 3) for v in restore_from_xy],
            "to_position": [round(v, 3) for v in restore_to_xy],
            "event_frame": restore_event_frame,
            "displacement_before_restore": round(
                math.dist(restore_from_xy, checkpoint_xy), 3
            ),
            "arrival_error": round(math.dist(restore_to_xy, checkpoint_xy), 3),
            "weapon_before": weapon_before_restore,
            "weapon_after": weapon_after_restore,
            "engine_itemcount_before": itemcount_before_restore,
            "engine_itemcount_after": itemcount_after_restore,
            "engine_shotgun_owned_before": shotgun_owned_before_restore,
            "engine_shotgun_owned_after": shotgun_owned_after_restore,
            "controller_held_keys_before": sorted(held_keys),
            "controller_held_keys_after": sorted(held_keys),
            "mechanism": "scripted warp with visible teleport effects",
        },
    }
    return events, audit


def _validate_pilot_ledger(
    events: list[dict[str, Any]], audit: dict[str, Any]
) -> None:
    def timestamp(frame: int) -> int:
        return round(frame * 1000 / FPS)

    blue_frame = audit["collections"]["BlueCard"]["event_frame"]
    shotgun_frame = audit["collections"]["Shotgun"]["event_frame"]
    checkpoint_frame = audit["collections"]["Megasphere"]["event_frame"]
    restore_frame = audit["restore"]["event_frame"]
    expected = [
        {
            "timestamp_ms": timestamp(blue_frame),
            "event_type": "key_pickup",
            "entity_id": "blue_key",
            "state": {
                "active_weapon": "pistol",
                "held_keys": ["blue_key"],
                "active_switches": [],
                "current_checkpoint": None,
            },
        },
        {
            "timestamp_ms": timestamp(shotgun_frame),
            "event_type": "weapon_pickup",
            "entity_id": "shotgun",
            "state": {
                "active_weapon": "shotgun",
                "held_keys": ["blue_key"],
                "active_switches": [],
                "current_checkpoint": None,
            },
        },
        {
            "timestamp_ms": timestamp(checkpoint_frame),
            "event_type": "checkpoint_activate",
            "entity_id": "checkpoint_alpha",
            "state": {
                "active_weapon": "shotgun",
                "held_keys": ["blue_key"],
                "active_switches": [],
                "current_checkpoint": "checkpoint_alpha",
            },
        },
        {
            "timestamp_ms": timestamp(restore_frame),
            "event_type": "checkpoint_restore",
            "entity_id": "checkpoint_alpha",
            "state": {
                "active_weapon": "shotgun",
                "held_keys": ["blue_key"],
                "active_switches": [],
                "current_checkpoint": "checkpoint_alpha",
            },
        },
    ]
    if events != expected:
        raise RuntimeError("generated pilot ledger failed semantic assertions")


def _tool_path(path: Path, executable: str) -> str:
    if Path(executable).suffix.lower() != ".exe":
        return str(path)
    wslpath = shutil.which("wslpath")
    if not wslpath:
        return str(path)
    result = subprocess.run(
        [wslpath, "-w", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _render_replay(
    output_dir: Path,
    seed: int,
    expected_hashes: list[str],
    ffmpeg_override: str | None = None,
    ffprobe_override: str | None = None,
) -> dict[str, Any]:
    ffmpeg = ffmpeg_override or shutil.which("ffmpeg")
    ffprobe = ffprobe_override or shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("ffmpeg and ffprobe must be on PATH")

    video_path = output_dir / "pilot.mp4"
    ffmpeg_video_path = _tool_path(video_path, ffmpeg)
    ffprobe_video_path = _tool_path(video_path, ffprobe)
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
        str(FPS),
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
        ffmpeg_video_path,
    ]
    encoder = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if encoder.stdin is None:
        raise RuntimeError("failed to open ffmpeg stdin")

    mismatches: list[int] = []
    try:
        game = _configure_game(seed)
        try:
            game.init()
            game.replay_episode(str(output_dir / "pilot.lmp"))
            for index, expected_hash in enumerate(expected_hashes):
                game.advance_action()
                if game.is_episode_finished():
                    raise RuntimeError(f"replay ended at frame {index}")
                state = game.get_state()
                if state is None:
                    raise RuntimeError(
                        f"replay returned no state at frame {index}"
                    )
                frame = state.screen_buffer
                actual_hash = hashlib.sha256(frame.tobytes()).hexdigest()
                if actual_hash != expected_hash:
                    mismatches.append(index)
                encoder.stdin.write(frame.tobytes())
        finally:
            game.close()
        encoder.stdin.close()
        stderr = encoder.stderr.read().decode("utf-8", errors="replace")
        return_code = encoder.wait()
        if return_code != 0:
            raise RuntimeError(
                f"ffmpeg failed ({return_code}): {stderr.strip()}"
            )
    except BaseException:
        if not encoder.stdin.closed:
            try:
                encoder.stdin.close()
            except OSError:
                pass
        if encoder.poll() is None:
            encoder.terminate()
            try:
                encoder.wait(timeout=5)
            except subprocess.TimeoutExpired:
                encoder.kill()
                encoder.wait()
        raise

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
            ffprobe_video_path,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    probe_data = json.loads(probe.stdout)
    streams = probe_data.get("streams", [])
    if len(streams) != 1:
        raise RuntimeError(f"expected one video stream, found {len(streams)}")
    stream = streams[0]
    measured = {
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "avg_frame_rate": stream["avg_frame_rate"],
        "nb_frames": int(stream["nb_frames"]),
        "duration_seconds": float(probe_data["format"]["duration"]),
    }
    expected_duration = len(expected_hashes) / FPS
    if (
        measured["width"] != WIDTH
        or measured["height"] != HEIGHT
        or measured["avg_frame_rate"] != f"{FPS}/1"
        or measured["nb_frames"] != len(expected_hashes)
        or abs(measured["duration_seconds"] - expected_duration) > 1 / FPS
    ):
        raise RuntimeError(f"rendered media metadata mismatch: {measured}")
    video_sha256 = _sha256(video_path)
    version = subprocess.run(
        [ffmpeg, "-version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[0]
    return {
        "video_path": video_path.name,
        "video_sha256": video_sha256,
        "default_seed_reference_encoder_sha_match": (
            video_sha256 == EXPECTED_VIDEO_SHA256 if seed == SEED else None
        ),
        "ffmpeg_version": version,
        "replay_frame_count": len(expected_hashes),
        "replay_hash_mismatch_count": len(mismatches),
        "replay_hash_mismatch_frames": mismatches[:20],
        "ffprobe": measured,
    }


def _audit_checks(audit: dict[str, Any]) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    for actor in ("BlueCard", "Shotgun", "Megasphere"):
        track = audit["actor_tracks"][actor]
        collection = audit["collections"][actor]
        checks[f"{actor}_observable"] = {
            "pass": (
                collection["qualifying_visible_run_before_disappearance"] >= FPS
                and collection["qualifying_visibility_gap_frames"] <= FPS // 4
                and collection["pickup_distance"] <= 48.0
            ),
            "visible_frames": track["visible_frames"],
            "max_bbox_area": track["max_bbox_area"],
            "qualifying_visible_run_before_disappearance": collection[
                "qualifying_visible_run_before_disappearance"
            ],
            "qualifying_visibility_gap_frames": collection[
                "qualifying_visibility_gap_frames"
            ],
            "pickup_distance": collection["pickup_distance"],
        }
    restore = audit["restore"]
    checks["scripted_checkpoint_restore"] = {
        "pass": (
            restore["displacement_before_restore"] >= 96.0
            and restore["arrival_error"] <= 4.0
            and restore["weapon_before"] == restore["weapon_after"] == "shotgun"
            and restore["engine_itemcount_before"]
            == restore["engine_itemcount_after"]
            and restore["engine_shotgun_owned_before"]
            and restore["engine_shotgun_owned_after"]
        ),
        **restore,
    }
    distractor_track = audit["actor_tracks"]["RedCard"]
    checks["unscored_distractor"] = {
        "pass": (
            audit["distractor"]["visible_but_not_collected"]
            and distractor_track["longest_qualifying_run"] >= FPS
        ),
        "visible_frames": distractor_track["visible_frames"],
        "max_bbox_area": distractor_track["max_bbox_area"],
        "longest_qualifying_run": distractor_track[
            "longest_qualifying_run"
        ],
        **audit["distractor"],
    }
    restore_cue = audit["actor_tracks"]["TeleportFog"]
    checks["restore_cue_visible"] = {
        "pass": (
            restore_cue["visible_frames"] >= 2
            and restore_cue["max_bbox_area"] >= 1024
        ),
        "visible_frames": restore_cue["visible_frames"],
        "max_bbox_area": restore_cue["max_bbox_area"],
    }
    checks["demo_replay_exact"] = {
        "pass": audit["render"]["replay_hash_mismatch_count"] == 0,
        "mismatch_count": audit["render"]["replay_hash_mismatch_count"],
    }
    return {
        "all_passed": all(value["pass"] for value in checks.values()),
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/freedoom-checkpoint-pilot"),
    )
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--ffmpeg")
    parser.add_argument("--ffprobe")
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix=f".{output_dir.name}-staging-", dir=output_dir.parent
    ) as temporary:
        staging_dir = Path(temporary)
        events, audit = _record_demo(staging_dir, args.seed)
        _validate_pilot_ledger(events, audit)
        ground_truth = {
            "episodes": [{"episode_id": "episode_01", "events": events}]
        }
        oracle = ground_truth
        null = {"episodes": [{"episode_id": "episode_01", "events": []}]}

        audit["render"] = _render_replay(
            staging_dir,
            args.seed,
            audit.pop("frame_hashes"),
            ffmpeg_override=args.ffmpeg,
            ffprobe_override=args.ffprobe,
        )
        audit["observability"] = _audit_checks(audit)
        if not audit["observability"]["all_passed"]:
            failed = {
                name: check
                for name, check in audit["observability"]["checks"].items()
                if not check["pass"]
            }
            raise RuntimeError(
                "pilot observability audit failed: "
                + json.dumps(failed, sort_keys=True)
            )

        oracle_reward = score_documents(ground_truth, oracle)
        null_reward = score_documents(ground_truth, null)
        if oracle_reward["reward"] != 1.0 or null_reward["reward"] != 0.0:
            raise RuntimeError("pilot scorer anchor check failed")

        paths = {
            "ground_truth": staging_dir / "pilot_ground_truth.json",
            "oracle_solution": staging_dir / "oracle_solution.json",
            "null_solution": staging_dir / "null_solution.json",
            "audit": staging_dir / "pilot_audit.json",
            "oracle_reward": staging_dir / "oracle_reward.json",
            "null_reward": staging_dir / "null_reward.json",
        }
        _write_json(paths["ground_truth"], ground_truth)
        _write_json(paths["oracle_solution"], oracle)
        _write_json(paths["null_solution"], null)
        _write_json(paths["audit"], audit)
        _write_json(paths["oracle_reward"], oracle_reward)
        _write_json(paths["null_reward"], null_reward)

        package_dir = Path(vzd.__file__).resolve().parent
        source_paths = {
            "generator": Path(__file__).resolve(),
            "verifier": Path(__file__).with_name("verify_ledger.py").resolve(),
            "requirements": Path(__file__).with_name("requirements.txt").resolve(),
        }
        manifest = {
            "status": "pass",
            "scope": "pipeline pilot; not a benchmark calibration run",
            "seed": args.seed,
            "vizdoom_version": vzd.__version__,
            "freedoom2_wad_sha256": _sha256(package_dir / "freedoom2.wad"),
            "scenario_sha256": {
                name: _sha256(package_dir / "scenarios" / name)
                for name in ("health_gathering.cfg", "health_gathering.wad")
            },
            "video_sha256": audit["render"]["video_sha256"],
            "video_duration_seconds": round(
                audit["render"]["ffprobe"]["duration_seconds"], 6
            ),
            "frame_count": audit["frame_count"],
            "replay_hash_mismatch_count": audit["render"][
                "replay_hash_mismatch_count"
            ],
            "oracle_reward": oracle_reward["reward"],
            "null_reward": null_reward["reward"],
            "zero_manual_event_annotations": True,
            "source_sha256": {
                name: _sha256(path) for name, path in source_paths.items()
            },
            "files": {name: path.name for name, path in paths.items()},
        }
        _write_json(staging_dir / "manifest.json", manifest)

        (output_dir / "manifest.json").unlink(missing_ok=True)
        staged_files = sorted(
            path
            for path in staging_dir.iterdir()
            if path.is_file() and path.name != "manifest.json"
        )
        for path in staged_files:
            path.replace(output_dir / path.name)
        (staging_dir / "manifest.json").replace(output_dir / "manifest.json")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
