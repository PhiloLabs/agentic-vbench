from __future__ import annotations

import csv
import json
import os
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

from pilot_lib import (
    AircraftState,
    FlightGearTelnet,
    GenericControlSender,
    KinematicController,
    dump_json,
    normalize_heading,
    normalize_telemetry,
    synthesize_timeline,
    wait_for_telnet,
)


CODE_ROOT = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("FLIGHTGEAR_OUTPUT_DIR", CODE_ROOT)).resolve()
CONFIG_PATH = Path(os.environ.get("FLIGHTGEAR_CONFIG", CODE_ROOT / "pilot_config.json")).resolve()


def interrupt_for_shutdown(_signum: int, _frame: Any) -> None:
    raise KeyboardInterrupt


def require_available_port(port: int, socket_type: int) -> None:
    with socket.socket(socket.AF_INET, socket_type) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError(f"Required port {port} is already in use") from exc


def terminate(process: subprocess.Popen[Any] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def resolve_commands(
    config: dict[str, Any],
    initial_heading: float,
    initial_altitude: float,
    initial_airspeed: float,
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    previous_heading = normalize_heading(initial_heading)
    previous_altitude = int(round(initial_altitude / 100.0) * 100)
    previous_airspeed = int(round(initial_airspeed))
    for index, command in enumerate(config["commands"], start=1):
        command_type = command["command_type"]
        target = command["target"]
        if "heading" in command_type:
            base = initial_heading if target["mode"] == "delta_from_initial" else previous_heading
            value = normalize_heading(base + target["value"])
            previous_value = previous_heading
            previous_heading = value
            unit = "degrees"
        elif command_type in {"accelerate", "decelerate", "maintain_speed"}:
            base = initial_airspeed if target["mode"] == "delta_from_initial" else previous_airspeed
            value = int(round(base + target["value"]))
            previous_value = previous_airspeed
            previous_airspeed = value
            unit = "knots"
        else:
            base = initial_altitude if target["mode"] == "delta_from_initial" else previous_altitude
            value = int(round((base + target["value"]) / 100.0) * 100)
            previous_value = previous_altitude
            previous_altitude = value
            unit = "feet"
        resolved.append(
            {
                "clearance_index": index,
                "issued_time_s": float(command["issue_time_s"]),
                "command_type": command_type,
                "target_value": value,
                "target_unit": unit,
                "previous_target_value": previous_value,
                "response_delay_s": float(command.get("response_delay_s", 0.0)),
                "behavior": command.get("behavior", "normal"),
                "overshoot_amount": float(command.get("overshoot_amount", 0.0)),
                "overshoot_duration_s": float(command.get("overshoot_duration_s", 0.0)),
                "expected_status": command.get("expected_status"),
                "expected_overshoot": command.get("expected_overshoot"),
            }
        )
    return resolved


def phrase(command: dict[str, Any]) -> str:
    value = command["target_value"]
    if command["command_type"] == "climb":
        return f"November seven two alpha, climb and maintain {value} feet."
    if command["command_type"] == "descend":
        return f"November seven two alpha, descend and maintain {value} feet."
    if command["command_type"] in {"accelerate", "decelerate", "maintain_speed"}:
        return f"November seven two alpha, maintain {value} knots."
    direction = "right" if "right" in command["command_type"] else "left"
    digits = " ".join(str(value).zfill(3))
    return f"November seven two alpha, turn {direction} heading {digits}."


def apply_command(
    controller: KinematicController,
    command: dict[str, Any],
    altitude_instrument_offset_ft: float,
    target_value: float | None = None,
    heading_direction: float | None = None,
) -> None:
    value = command["target_value"] if target_value is None else target_value
    if "heading" in command["command_type"]:
        controller.target_heading_deg = value % 360
        if heading_direction is not None:
            controller.heading_direction = heading_direction
        elif "right" in command["command_type"]:
            controller.heading_direction = 1.0
        elif "left" in command["command_type"]:
            controller.heading_direction = -1.0
        else:
            controller.heading_direction = None
    elif command["target_unit"] == "feet":
        controller.target_altitude_ft = value + altitude_instrument_offset_ft
    else:
        controller.target_airspeed_kt = value


def build_control_actions(commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for command in commands:
        behavior = command["behavior"]
        if behavior == "no_response":
            continue
        activation = command.get("audio_end_time_s", command["issued_time_s"])
        activation += command["response_delay_s"]
        target = float(command["target_value"])
        previous = float(command["previous_target_value"])
        spoken_heading_direction = (
            1.0
            if "right" in command["command_type"]
            else -1.0
            if "left" in command["command_type"]
            else None
        )
        initial_heading_direction = spoken_heading_direction
        if behavior == "wrong_direction":
            if command["target_unit"] == "degrees":
                direction = 1.0 if "right" in command["command_type"] else -1.0
                target = (previous - direction * 25.0) % 360.0
                initial_heading_direction = -direction
            elif command["target_unit"] == "feet":
                direction = 1.0 if command["command_type"] == "climb" else -1.0
                target = previous - direction * 250.0
            else:
                direction = 1.0 if command["command_type"] == "accelerate" else -1.0
                target = previous - direction * 15.0
        elif behavior == "overshoot":
            direction = 1.0
            if command["target_unit"] == "degrees":
                direction = 1.0 if "right" in command["command_type"] else -1.0
                target = (target + direction * command["overshoot_amount"]) % 360.0
            elif command["target_unit"] == "feet":
                direction = 1.0 if command["command_type"] == "climb" else -1.0
                target += direction * command["overshoot_amount"]
            else:
                direction = 1.0 if command["command_type"] == "accelerate" else -1.0
                target += direction * command["overshoot_amount"]
            actions.append(
                {
                    "time_s": activation + command["overshoot_duration_s"],
                    "command": command,
                    "target_value": float(command["target_value"]),
                    "phase": "settle",
                    "heading_direction": (
                        None
                        if spoken_heading_direction is None
                        else -spoken_heading_direction
                    ),
                }
            )
        actions.append(
            {
                "time_s": activation,
                "command": command,
                "target_value": target,
                "phase": "initial",
                "heading_direction": initial_heading_direction,
            }
        )
    return sorted(actions, key=lambda action: (action["time_s"], action["phase"] == "settle"))


def main() -> None:
    signal.signal(signal.SIGTERM, interrupt_for_shutdown)
    ROOT.mkdir(parents=True, exist_ok=True)
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    width = config["resolution"]["width"]
    height = config["resolution"]["height"]
    fps = config["resolution"]["fps"]
    fg = config["flightgear"]
    require_available_port(fg["telnet_port"], socket.SOCK_STREAM)
    require_available_port(fg["control_port"], socket.SOCK_DGRAM)
    display = config["display"]
    env = os.environ.copy()
    env.update({"DISPLAY": display, "LIBGL_ALWAYS_SOFTWARE": "1"})

    for name in ("fgfs", "ffmpeg", "ffprobe", "Xvfb", "espeak-ng"):
        if shutil.which(name) is None:
            raise RuntimeError(f"Missing required executable: {name}")

    raw_video = ROOT / "pilot_video_only.mp4"
    audio_timeline = ROOT / "pilot_audio.wav"
    pilot = ROOT / "pilot.mp4"
    raw_telemetry = ROOT / "telemetry_raw.csv"
    telemetry = ROOT / "telemetry.csv"
    for path in (
        raw_video,
        audio_timeline,
        pilot,
        raw_telemetry,
        telemetry,
        ROOT / "command_log.jsonl",
        ROOT / "controller_trace.csv",
    ):
        path.unlink(missing_ok=True)

    protocol_source = CODE_ROOT / "telemetry_protocol.xml"
    protocol_target = Path("/usr/share/games/flightgear/Protocol/atc-pilot.xml")
    if (
        not protocol_target.exists()
        or protocol_target.read_bytes() != protocol_source.read_bytes()
    ):
        subprocess.run(
            [
                "sudo",
                "install",
                "-m",
                "0644",
                str(protocol_source),
                str(protocol_target),
            ],
            check=True,
        )

    xvfb: subprocess.Popen[Any] | None = None
    flightgear: subprocess.Popen[Any] | None = None
    recorder: subprocess.Popen[Any] | None = None
    client: FlightGearTelnet | None = None
    control_sender: GenericControlSender | None = None
    controller_trace_handle: Any | None = None
    try:
        xvfb = subprocess.Popen(
            ["Xvfb", display, "-screen", "0", f"{width}x{height}x24", "-ac", "+extension", "GLX", "+render", "-noreset"],
            stdout=(ROOT / "xvfb.log").open("wb"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        time.sleep(2)
        fg_command = [
            fg["binary"],
            f"--aircraft={fg['aircraft']}",
            f"--airport={fg['airport']}",
            f"--runway={fg['runway']}",
            f"--altitude={fg['altitude_ft']}",
            f"--heading={fg['heading_deg']}",
            f"--vc={fg['airspeed_kt']}",
            "--timeofday=noon",
            "--disable-ai-models",
            "--disable-random-objects",
            "--disable-real-weather-fetch",
            "--disable-terrasync",
            "--disable-splash-screen",
            "--fdm=null",
            f"--geometry={width}x{height}",
            f"--telnet={fg['telnet_port']}",
            f"--generic=file,out,{config['telemetry_hz']},{raw_telemetry},atc-pilot",
            f"--generic=socket,in,{config['controller']['update_hz']},127.0.0.1,{fg['control_port']},udp,atc-pilot",
            "--prop:/sim/rendering/multi-sample-buffers=0",
            "--prop:/sim/rendering/multi-samples=0",
        ]
        flightgear = subprocess.Popen(
            fg_command,
            env=env,
            stdout=(ROOT / "flightgear.log").open("wb"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        client = wait_for_telnet(fg["telnet_port"], fg["startup_timeout_s"])
        client.set("/instrumentation/heading-indicator/offset-deg", 0)
        client.set("/instrumentation/heading-indicator/spin", 1)
        client.set("/instrumentation/altimeter/setting-inhg", 29.92)
        control_sender = GenericControlSender("127.0.0.1", fg["control_port"])
        controller = KinematicController(
            AircraftState(
                altitude_ft=float(fg["altitude_ft"]),
                heading_deg=float(fg["heading_deg"]),
                airspeed_kt=float(fg["airspeed_kt"]),
            ),
            config["controller"],
        )
        for _ in range(round(fg["stabilization_s"] * config["controller"]["update_hz"])):
            control_sender.send(controller.state)
            time.sleep(1.0 / config["controller"]["update_hz"])
        time.sleep(fg["stabilization_s"])

        initial_heading = client.get_float("/instrumentation/heading-indicator/indicated-heading-deg")
        initial_altitude = client.get_float("/instrumentation/altimeter/indicated-altitude-ft")
        initial_airspeed = client.get_float("/velocities/airspeed-kt")
        altitude_instrument_offset_ft = controller.state.altitude_ft - initial_altitude
        commands = resolve_commands(config, initial_heading, initial_altitude, initial_airspeed)
        clip_paths: list[tuple[float, Path]] = []
        for command in commands:
            clip = ROOT / f"atc_{command['clearance_index']:02d}.wav"
            subprocess.run(
                ["espeak-ng", "-s", "145", "-w", str(clip), phrase(command)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            clip_paths.append((command["issued_time_s"], clip))
        audio_info = synthesize_timeline(clip_paths, audio_timeline, config["duration_s"])
        for command, timing in zip(commands, audio_info, strict=True):
            command.update(timing)
            command["spoken_text"] = phrase(command)
        control_actions = build_control_actions(commands)

        recorder_command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "x11grab",
            "-draw_mouse",
            "0",
            "-framerate",
            str(fps),
            "-video_size",
            f"{width}x{height}",
            "-i",
            display,
            "-t",
            str(config["duration_s"]),
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-y",
            str(raw_video),
        ]
        record_request_monotonic = time.monotonic()
        recorder = subprocess.Popen(recorder_command, stdout=subprocess.DEVNULL, stderr=(ROOT / "ffmpeg.log").open("wb"))
        origin = time.monotonic()
        sim_origin_s = client.get_float("/sim/time/elapsed-sec")
        video_start_offset_s = origin - record_request_monotonic
        controller_trace_handle = (ROOT / "controller_trace.csv").open(
            "w",
            encoding="utf-8",
            newline="",
        )
        controller_trace = csv.DictWriter(
            controller_trace_handle,
            fieldnames=(
                "time_s",
                "altitude_ft",
                "heading_deg",
                "airspeed_kt",
                "vertical_speed_fpm",
                "roll_deg",
                "pitch_deg",
            ),
        )
        controller_trace.writeheader()

        next_command = 0
        next_action = 0
        update_period = 1.0 / config["controller"]["update_hz"]
        next_update = 0.0
        previous_update = 0.0
        while True:
            elapsed = time.monotonic() - origin
            if elapsed >= config["duration_s"]:
                break
            while next_command < len(commands) and elapsed >= commands[next_command]["issued_time_s"]:
                commands[next_command]["issued_actual_time_s"] = round(time.monotonic() - origin, 3)
                next_command += 1
            while next_action < len(control_actions) and elapsed >= control_actions[next_action]["time_s"]:
                action = control_actions[next_action]
                apply_command(
                    controller,
                    action["command"],
                    altitude_instrument_offset_ft,
                    action["target_value"],
                    action["heading_direction"],
                )
                if action["phase"] == "initial":
                    action["command"]["control_applied_time_s"] = round(time.monotonic() - origin, 3)
                next_action += 1
            if elapsed >= next_update:
                dt = elapsed - previous_update if previous_update else update_period
                state = controller.update(dt)
                control_sender.send(state)
                controller_trace.writerow(
                    {
                        "time_s": round(elapsed, 6),
                        "altitude_ft": round(state.altitude_ft, 6),
                        "heading_deg": round(state.heading_deg, 6),
                        "airspeed_kt": round(state.airspeed_kt, 6),
                        "vertical_speed_fpm": round(state.vertical_speed_fpm, 6),
                        "roll_deg": round(state.roll_deg, 6),
                        "pitch_deg": round(state.pitch_deg, 6),
                    }
                )
                previous_update = elapsed
                next_update += update_period
            time.sleep(0.002)
        controller_trace_handle.close()
        controller_trace_handle = None
        control_sender.close()
        control_sender = None
        recorder.wait(timeout=20)
        recorder = None
        time.sleep(1)
        samples = normalize_telemetry(raw_telemetry, telemetry, sim_origin_s, config["duration_s"])
        with (ROOT / "command_log.jsonl").open("w", encoding="utf-8") as handle:
            for command in commands:
                handle.write(json.dumps(command, sort_keys=True) + "\n")
        if not samples:
            raise RuntimeError("FlightGear produced no telemetry samples")
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(raw_video),
                "-i",
                str(audio_timeline),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-map_metadata",
                "-1",
                "-movflags",
                "+faststart",
                "-shortest",
                "-y",
                str(pilot),
            ],
            check=True,
        )
        dump_json(
            ROOT / "alignment_report.json",
            {
                "clock": "Python time.monotonic",
                "video_origin_definition": "immediately after ffmpeg x11grab process launch",
                "estimated_video_start_offset_s": round(video_start_offset_s, 6),
                "sim_time_origin_s": sim_origin_s,
                "audio_events": audio_info,
                "telemetry_first_time_s": samples[0]["time_s"],
                "telemetry_last_time_s": samples[-1]["time_s"],
                "telemetry_samples": len(samples),
                "control_application_offsets_s": [
                    None
                    if "control_applied_time_s" not in command
                    else round(command["control_applied_time_s"] - command["issued_time_s"], 3)
                    for command in commands
                ],
            },
        )
    finally:
        if client is not None:
            client.close()
        if control_sender is not None:
            control_sender.close()
        if controller_trace_handle is not None:
            controller_trace_handle.close()
        terminate(recorder)
        terminate(flightgear)
        terminate(xvfb)


if __name__ == "__main__":
    main()
