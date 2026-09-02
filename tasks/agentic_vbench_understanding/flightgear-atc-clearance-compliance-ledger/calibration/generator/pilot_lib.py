from __future__ import annotations

import csv
import json
import math
import socket
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROMPT = b"/> "


class FlightGearTelnet:
    def __init__(self, host: str, port: int, timeout: float = 20.0) -> None:
        self._socket = socket.create_connection((host, port), timeout=timeout)
        self._socket.settimeout(timeout)

    def close(self) -> None:
        self._socket.close()

    def command(self, text: str) -> str:
        self._socket.sendall((text + "\r\n").encode("ascii"))
        data = bytearray()
        while PROMPT not in data:
            data.extend(self._socket.recv(65536))
        return data.decode("utf-8", errors="replace")

    def get_float(self, path: str) -> float:
        response = self.command(f"get {path}")
        try:
            return float(response.split("'")[1])
        except (IndexError, ValueError) as exc:
            raise RuntimeError(f"Could not parse {path}: {response!r}") from exc

    def set(self, path: str, value: str | int | float | bool) -> None:
        if isinstance(value, bool):
            encoded = "true" if value else "false"
        else:
            encoded = str(value)
        self.command(f"set {path} {encoded}")


TELEMETRY_FIELDS = (
    "sim_time_s",
    "altitude_ft",
    "indicated_altitude_ft",
    "heading_deg",
    "indicated_heading_deg",
    "airspeed_kt",
    "indicated_airspeed_kt",
    "fdm_vias_kt",
    "vertical_speed_fpm",
    "roll_deg",
    "pitch_deg",
)


@dataclass
class AircraftState:
    altitude_ft: float
    heading_deg: float
    airspeed_kt: float
    vertical_speed_fpm: float = 0.0
    roll_deg: float = 0.0
    pitch_deg: float = 0.0


class KinematicController:
    def __init__(self, state: AircraftState, config: dict[str, float]) -> None:
        self.state = state
        self.config = config
        self.target_heading_deg = state.heading_deg
        self.heading_direction: float | None = None
        self.target_altitude_ft = state.altitude_ft
        self.target_airspeed_kt = state.airspeed_kt

    @staticmethod
    def _approach(value: float, target: float, maximum_step: float) -> float:
        error = target - value
        return target if abs(error) <= maximum_step else value + math.copysign(maximum_step, error)

    def update(self, dt: float) -> AircraftState:
        if angular_error_deg(self.state.heading_deg, self.target_heading_deg) < 1e-9:
            heading_error = 0.0
        elif self.heading_direction == 1.0:
            heading_error = (self.target_heading_deg - self.state.heading_deg) % 360.0
        elif self.heading_direction == -1.0:
            heading_error = -((self.state.heading_deg - self.target_heading_deg) % 360.0)
        else:
            heading_error = angular_delta_deg(
                self.state.heading_deg,
                self.target_heading_deg,
            )
        heading_rate = (
            self.config["heading_capture_rate_deg_s"]
            if abs(heading_error) <= self.config["heading_capture_zone_deg"]
            else self.config["heading_rate_deg_s"]
        )
        heading_step = min(abs(heading_error), heading_rate * dt)
        signed_heading_rate = 0.0 if heading_step == 0 else math.copysign(heading_step / dt, heading_error)
        self.state.heading_deg = (self.state.heading_deg + math.copysign(heading_step, heading_error)) % 360.0
        desired_roll = max(
            -self.config["max_bank_deg"],
            min(self.config["max_bank_deg"], signed_heading_rate * 4.0),
        )
        self.state.roll_deg = self._approach(self.state.roll_deg, desired_roll, 12.0 * dt)

        altitude_error = self.target_altitude_ft - self.state.altitude_ft
        altitude_rate = (
            self.config["altitude_capture_rate_fpm"]
            if abs(altitude_error) <= self.config["altitude_capture_zone_ft"]
            else self.config["altitude_rate_fpm"]
        )
        desired_vertical_speed = math.copysign(altitude_rate, altitude_error) if altitude_error else 0.0
        maximum_altitude_step = abs(desired_vertical_speed) / 60.0 * dt
        self.state.altitude_ft = self._approach(
            self.state.altitude_ft,
            self.target_altitude_ft,
            maximum_altitude_step,
        )
        self.state.vertical_speed_fpm = (
            0.0
            if self.state.altitude_ft == self.target_altitude_ft
            else desired_vertical_speed
        )
        self.state.pitch_deg = max(
            -self.config["max_pitch_deg"],
            min(
                self.config["max_pitch_deg"],
                self.state.vertical_speed_fpm / self.config["altitude_rate_fpm"] * self.config["max_pitch_deg"],
            ),
        )

        speed_error = self.target_airspeed_kt - self.state.airspeed_kt
        speed_rate = (
            self.config["airspeed_capture_rate_kt_s"]
            if abs(speed_error) <= self.config["airspeed_capture_zone_kt"]
            else self.config["airspeed_rate_kt_s"]
        )
        self.state.airspeed_kt = self._approach(
            self.state.airspeed_kt,
            self.target_airspeed_kt,
            speed_rate * dt,
        )
        return self.state


class GenericControlSender:
    def __init__(self, host: str, port: int) -> None:
        self._target = (host, port)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, state: AircraftState) -> None:
        values = (
            state.altitude_ft,
            state.heading_deg,
            1.0,
            state.airspeed_kt,
            state.airspeed_kt,
            state.airspeed_kt,
            state.vertical_speed_fpm / 60.0,
            state.roll_deg,
            state.pitch_deg,
        )
        self._socket.sendto((",".join(f"{value:.6f}" for value in values) + "\n").encode("ascii"), self._target)

    def close(self) -> None:
        self._socket.close()


def load_telemetry(path: Path) -> list[dict[str, float]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [{key: float(value) for key, value in row.items()} for row in csv.DictReader(handle)]


def normalize_telemetry(
    raw_path: Path,
    output_path: Path,
    sim_origin_s: float,
    duration_s: float,
) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for line in raw_path.read_text(encoding="utf-8").splitlines():
        values = line.split(",")
        if len(values) != len(TELEMETRY_FIELDS):
            continue
        try:
            row = {field: float(value) for field, value in zip(TELEMETRY_FIELDS, values, strict=True)}
        except ValueError:
            continue
        row["time_s"] = row["sim_time_s"] - sim_origin_s
        if row["time_s"] < 0 or row["time_s"] > duration_s:
            continue
        rows.append(row)
    fieldnames = ("time_s", *TELEMETRY_FIELDS)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def angular_delta_deg(start: float, end: float) -> float:
    return (end - start + 180.0) % 360.0 - 180.0


def angular_error_deg(value: float, target: float) -> float:
    return abs(angular_delta_deg(value, target))


def normalize_heading(value: float) -> int:
    return int(round(value)) % 360


def consecutive_start(
    samples: list[dict[str, float]],
    predicate: Any,
    hold_s: float,
) -> float | None:
    start: float | None = None
    for sample in samples:
        if predicate(sample):
            if start is None:
                start = sample["time_s"]
            if sample["time_s"] - start >= hold_s:
                return start
        else:
            start = None
    return None


def synthesize_timeline(
    clips: list[tuple[float, Path]],
    output: Path,
    duration_s: float,
    sample_rate: int = 22050,
) -> list[dict[str, float]]:
    total_frames = math.ceil(duration_s * sample_rate)
    mixed = [0] * total_frames
    clip_info: list[dict[str, float]] = []
    for start_s, clip_path in clips:
        with wave.open(str(clip_path), "rb") as source:
            if source.getnchannels() != 1 or source.getsampwidth() != 2:
                raise ValueError(f"Expected mono 16-bit WAV: {clip_path}")
            if source.getframerate() != sample_rate:
                raise ValueError(f"Expected {sample_rate} Hz WAV: {clip_path}")
            frames = source.readframes(source.getnframes())
            values = memoryview(frames).cast("h")
            offset = round(start_s * sample_rate)
            for index, value in enumerate(values):
                target = offset + index
                if target >= total_frames:
                    break
                mixed[target] = max(-32768, min(32767, mixed[target] + int(value)))
            clip_info.append(
                {
                    "audio_start_time_s": start_s,
                    "audio_end_time_s": start_s + len(values) / sample_rate,
                }
            )
    with wave.open(str(output), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(sample_rate)
        target.writeframes(memoryview(bytearray(total_frames * 2)))
    with wave.open(str(output), "rb") as source:
        params = source.getparams()
    raw = bytearray()
    for value in mixed:
        raw.extend(int(value).to_bytes(2, "little", signed=True))
    with wave.open(str(output), "wb") as target:
        target.setparams(params)
        target.writeframes(raw)
    return clip_info


def dump_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def wait_for_telnet(port: int, timeout_s: float) -> FlightGearTelnet:
    deadline = time.monotonic() + timeout_s
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        try:
            client = FlightGearTelnet("127.0.0.1", port)
            client.get_float("/sim/time/elapsed-sec")
            time.sleep(5)
            client.get_float("/instrumentation/altimeter/indicated-altitude-ft")
            return client
        except (OSError, TimeoutError) as exc:
            last_error = exc
            time.sleep(1)
    raise TimeoutError(f"FlightGear telnet did not become ready: {last_error}")
