from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_ROOT = Path(
    os.environ.get(
        "FLIGHTGEAR_DATASET_ROOT",
        ROOT / "artifacts/segments",
    )
)
ISSUE_SCHEDULES = {
    1: [20, 70, 120, 170, 225, 300, 360, 378, 430, 485, 540, 600, 650],
    2: [28, 84, 139, 183, 201, 265, 325, 382, 440, 500, 558, 620, 680],
    3: [18, 65, 126, 176, 238, 292, 350, 400, 455, 473, 530, 592, 655],
    4: [32, 92, 145, 205, 266, 284, 350, 410, 468, 525, 580, 635, 690],
    5: [24, 76, 134, 194, 248, 310, 370, 430, 480, 525, 543, 610, 670],
}


def command(
    issue_time_s: float,
    command_type: str,
    value: float,
    *,
    response_delay_s: float = 0.0,
    behavior: str = "normal",
    overshoot_amount: float = 0.0,
    overshoot_duration_s: float = 0.0,
    expected_status: str = "complied",
    expected_overshoot: str = "none",
) -> dict[str, Any]:
    return {
        "issue_time_s": issue_time_s,
        "command_type": command_type,
        "target": {"mode": "delta_from_previous", "value": value},
        "response_delay_s": response_delay_s,
        "behavior": behavior,
        "overshoot_amount": overshoot_amount,
        "overshoot_duration_s": overshoot_duration_s,
        "expected_status": expected_status,
        "expected_overshoot": expected_overshoot,
    }


def make_config(index: int) -> dict[str, Any]:
    schedule = ISSUE_SCHEDULES[index]
    heading_sign = 1 if index % 2 else -1
    altitude_sign = 1 if index in {1, 3, 5} else -1
    speed_sign = -1 if index in {1, 2, 4} else 1

    def heading(position: int, delta: float, **kwargs: Any) -> dict[str, Any]:
        command_type = "turn_right_heading" if delta > 0 else "turn_left_heading"
        bucket = kwargs.pop("overshoot_bucket", None)
        if bucket:
            kwargs.update(
                {
                    "behavior": "overshoot",
                    "overshoot_amount": 25 if bucket == "large" else 12,
                    "overshoot_duration_s": 28 if bucket == "large" else 20,
                    "expected_overshoot": bucket,
                }
            )
        return command(schedule[position], command_type, delta, **kwargs)

    def altitude(position: int, delta: float, **kwargs: Any) -> dict[str, Any]:
        command_type = "climb" if delta > 0 else "descend"
        bucket = kwargs.pop("overshoot_bucket", None)
        if bucket:
            kwargs.update(
                {
                    "behavior": "overshoot",
                    "overshoot_amount": 360 if bucket == "large" else 180,
                    "overshoot_duration_s": 85 if bucket == "large" else 62,
                    "expected_overshoot": bucket,
                }
            )
        return command(schedule[position], command_type, delta, **kwargs)

    def speed(position: int, delta: float, **kwargs: Any) -> dict[str, Any]:
        command_type = "accelerate" if delta > 0 else "decelerate"
        bucket = kwargs.pop("overshoot_bucket", None)
        if bucket:
            kwargs.update(
                {
                    "behavior": "overshoot",
                    "overshoot_amount": 12 if bucket == "large" else 7,
                    "overshoot_duration_s": 28 if bucket == "large" else 20,
                    "expected_overshoot": bucket,
                }
            )
        return command(schedule[position], command_type, delta, **kwargs)

    if index == 1:
        commands = [
            heading(0, heading_sign * 26),
            altitude(1, altitude_sign * 300),
            speed(2, speed_sign * 18),
            heading(
                3,
                -heading_sign * 35,
                response_delay_s=18,
                expected_status="complied_late",
            ),
            altitude(4, altitude_sign * 350, overshoot_bucket="large"),
            speed(5, speed_sign * 15, overshoot_bucket="small"),
            heading(6, heading_sign * 100, expected_status="superseded"),
            heading(7, -heading_sign * 35),
            altitude(
                8,
                altitude_sign * 400,
                behavior="no_response",
                expected_status="incomplete",
            ),
            heading(9, heading_sign * 45),
            speed(10, speed_sign * 12),
            heading(11, -heading_sign * 55),
            speed(
                12,
                -speed_sign * 15,
                behavior="wrong_direction",
                expected_status="violated",
            ),
        ]
    elif index == 2:
        commands = [
            altitude(0, altitude_sign * 300),
            speed(
                1,
                speed_sign * 18,
                response_delay_s=18,
                expected_status="complied_late",
            ),
            heading(2, heading_sign * 30),
            speed(3, speed_sign * 35, expected_status="superseded"),
            speed(4, -speed_sign * 22),
            altitude(5, altitude_sign * 350, overshoot_bucket="small"),
            heading(6, -heading_sign * 45, overshoot_bucket="large"),
            altitude(7, -altitude_sign * 300),
            speed(8, speed_sign * 12),
            heading(9, heading_sign * 50),
            altitude(10, altitude_sign * 250),
            heading(
                11,
                -heading_sign * 60,
                behavior="no_response",
                expected_status="incomplete",
            ),
            altitude(
                12,
                -altitude_sign * 300,
                behavior="wrong_direction",
                expected_status="violated",
            ),
        ]
    elif index == 3:
        commands = [
            speed(0, speed_sign * 18),
            heading(1, heading_sign * 28),
            altitude(
                2,
                altitude_sign * 300,
                response_delay_s=18,
                expected_status="complied_late",
            ),
            speed(3, speed_sign * 15, overshoot_bucket="large"),
            heading(4, -heading_sign * 45, overshoot_bucket="small"),
            altitude(5, -altitude_sign * 300),
            speed(6, -speed_sign * 12),
            heading(7, heading_sign * 50),
            altitude(8, altitude_sign * 600, expected_status="superseded"),
            altitude(9, -altitude_sign * 500),
            heading(10, -heading_sign * 55),
            speed(
                11,
                speed_sign * 15,
                behavior="no_response",
                expected_status="incomplete",
            ),
            altitude(
                12,
                altitude_sign * 300,
                behavior="wrong_direction",
                expected_status="violated",
            ),
        ]
    elif index == 4:
        commands = [
            heading(
                0,
                heading_sign * 28,
                response_delay_s=18,
                expected_status="complied_late",
            ),
            altitude(1, altitude_sign * 300),
            speed(2, speed_sign * 18),
            heading(3, -heading_sign * 45, overshoot_bucket="large"),
            altitude(4, altitude_sign * 600, expected_status="superseded"),
            altitude(5, -altitude_sign * 600),
            speed(6, speed_sign * 15, overshoot_bucket="small"),
            heading(7, heading_sign * 50),
            altitude(8, altitude_sign * 250),
            speed(9, -speed_sign * 12),
            heading(10, -heading_sign * 55),
            speed(
                11,
                speed_sign * 15,
                behavior="no_response",
                expected_status="incomplete",
            ),
            altitude(
                12,
                -altitude_sign * 300,
                behavior="wrong_direction",
                expected_status="violated",
            ),
        ]
    else:
        commands = [
            altitude(0, altitude_sign * 300),
            heading(1, heading_sign * 28),
            speed(
                2,
                speed_sign * 18,
                response_delay_s=18,
                expected_status="complied_late",
            ),
            altitude(3, altitude_sign * 350, overshoot_bucket="large"),
            heading(4, -heading_sign * 45, overshoot_bucket="small"),
            speed(5, -speed_sign * 15),
            altitude(6, -altitude_sign * 300),
            heading(7, heading_sign * 50),
            speed(8, speed_sign * 12),
            heading(9, heading_sign * 100, expected_status="superseded"),
            heading(10, -heading_sign * 35),
            altitude(
                11,
                altitude_sign * 400,
                behavior="no_response",
                expected_status="incomplete",
            ),
            speed(
                12,
                -speed_sign * 15,
                behavior="wrong_direction",
                expected_status="violated",
            ),
        ]

    return {
        "seed": 2026081000 + index,
        "duration_s": 720.0,
        "telemetry_hz": 20.0,
        "display": f":{120 + index}",
        "resolution": {"width": 1280, "height": 720, "fps": 15},
        "flightgear": {
            "binary": "fgfs",
            "aircraft": "c172p",
            "airport": "KSFO",
            "runway": "28R",
            "altitude_ft": 3600 + index * 200,
            "heading_deg": (250 + index * 17) % 360,
            "airspeed_kt": 115 + index * 2,
            "telnet_port": 5699 + index * 2,
            "control_port": 5700 + index * 2,
            "startup_timeout_s": 180,
            "stabilization_s": 5,
        },
        "controller": {
            "update_hz": 10.0,
            "heading_rate_deg_s": 4.0,
            "heading_capture_rate_deg_s": 1.0,
            "heading_capture_zone_deg": 8.0,
            "altitude_rate_fpm": 600.0,
            "altitude_capture_rate_fpm": 300.0,
            "altitude_capture_zone_ft": 100.0,
            "airspeed_rate_kt_s": 2.0,
            "airspeed_capture_rate_kt_s": 0.5,
            "airspeed_capture_zone_kt": 8.0,
            "max_bank_deg": 18.0,
            "max_pitch_deg": 6.0,
        },
        "commands": commands,
        "derivation": {
            "heading_execution_rate_deg_s": 0.5,
            "heading_completion_tolerance_deg": 8.0,
            "altitude_execution_rate_fpm": 100.0,
            "altitude_completion_tolerance_ft": 100.0,
            "execution_hold_s": 2.0,
            "completion_hold_s": 3.0,
            "late_response_s": 12.0,
            "issued_time_tolerance_s": 2.0,
            "event_time_tolerance_s": 4.0,
        },
        "validation": {
            "telemetry_min_hz": 6.0,
            "telemetry_max_gap_s": 1.0,
        },
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_segment(
    index: int,
    output_dir: Path,
    config_path: Path,
    slots: queue.Queue[str],
) -> dict[str, Any]:
    cpu_set = slots.get()
    try:
        environment = os.environ.copy()
        environment["FLIGHTGEAR_CONFIG"] = str(config_path)
        environment["FLIGHTGEAR_OUTPUT_DIR"] = str(output_dir)
        flightgear_home = output_dir / ".fgfs"
        flightgear_home.mkdir(exist_ok=True)
        environment["FG_HOME"] = str(flightgear_home)
        log_path = output_dir / "orchestrator.log"
        with log_path.open("w", encoding="utf-8") as log:
            for script in ("run_pilot.py", "derive_ground_truth.py", "validate_run.py"):
                command_line = [
                    "taskset",
                    "-c",
                    cpu_set,
                    sys.executable,
                    str(ROOT / script),
                ]
                log.write("$ " + " ".join(command_line) + "\n")
                log.flush()
                subprocess.run(
                    command_line,
                    cwd=ROOT,
                    env=environment,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=True,
                )
        ground_truth = json.loads(
            (output_dir / "ground_truth.json").read_text(encoding="utf-8")
        )
        validation = json.loads(
            (output_dir / "validation_results.json").read_text(encoding="utf-8")
        )
        return {
            "flight_id": f"flight_{index:02d}",
            "video_sha256": sha256(output_dir / "pilot.mp4"),
            "clearances": len(ground_truth["clearances"]),
            "statuses": dict(
                Counter(event["status"] for event in ground_truth["clearances"])
            ),
            "overshoots": dict(
                Counter(
                    event["overshoot_bucket"] for event in ground_truth["clearances"]
                )
            ),
            "validation": validation,
            "cpu_set": cpu_set,
        }
    finally:
        slots.put(cpu_set)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--max-parallel", type=int, default=5, choices=range(1, 6))
    parser.add_argument(
        "--flights",
        nargs="+",
        type=int,
        choices=range(1, 6),
        default=list(range(1, 6)),
    )
    args = parser.parse_args()

    args.output_root.mkdir(parents=True, exist_ok=True)
    jobs = []
    for index in args.flights:
        output_dir = args.output_root / f"flight_{index:02d}"
        output_dir.mkdir(parents=True, exist_ok=True)
        config_path = output_dir / "config.json"
        config_path.write_text(
            json.dumps(make_config(index), indent=2) + "\n",
            encoding="utf-8",
        )
        jobs.append((index, output_dir, config_path))

    slots: queue.Queue[str] = queue.Queue()
    for cpu_start in range(0, args.max_parallel * 16, 16):
        slots.put(f"{cpu_start}-{cpu_start + 15}")

    results = []
    failures = []
    with ThreadPoolExecutor(max_workers=args.max_parallel) as executor:
        futures = {
            executor.submit(run_segment, index, output_dir, config_path, slots): index
            for index, output_dir, config_path in jobs
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append({"flight_id": f"flight_{index:02d}", "error": str(exc)})

    summary = {
        "output_root": str(args.output_root),
        "max_parallel": args.max_parallel,
        "results": sorted(results, key=lambda item: item["flight_id"]),
        "failures": failures,
    }
    (args.output_root / "generation_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    if failures:
        raise SystemExit(f"segment generation failed: {failures}")


if __name__ == "__main__":
    main()
