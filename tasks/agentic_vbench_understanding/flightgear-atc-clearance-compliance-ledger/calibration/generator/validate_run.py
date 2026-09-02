from __future__ import annotations

import bisect
import csv
import json
import os
from pathlib import Path
from typing import Any

from pilot_lib import angular_error_deg, dump_json


CODE_ROOT = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("FLIGHTGEAR_OUTPUT_DIR", CODE_ROOT)).resolve()
CONFIG_PATH = Path(os.environ.get("FLIGHTGEAR_CONFIG", CODE_ROOT / "pilot_config.json")).resolve()


def dimension(event: dict[str, Any]) -> str:
    if event["target_unit"] == "degrees":
        return "heading"
    if event["target_unit"] == "feet":
        return "altitude"
    return "airspeed"


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * fraction)]


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    commands = [
        json.loads(line)
        for line in (ROOT / "command_log.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ground_truth = json.loads((ROOT / "ground_truth.json").read_text(encoding="utf-8"))
    with (ROOT / "telemetry.csv").open(encoding="utf-8", newline="") as handle:
        telemetry = [{key: float(value) for key, value in row.items()} for row in csv.DictReader(handle)]
    with (ROOT / "controller_trace.csv").open(encoding="utf-8", newline="") as handle:
        controller_trace = [
            {key: float(value) for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]

    gaps = [
        current["time_s"] - previous["time_s"]
        for previous, current in zip(telemetry, telemetry[1:])
    ]
    duration_s = config["duration_s"]
    observed_span = telemetry[-1]["time_s"] - telemetry[0]["time_s"]
    telemetry_rate_hz = (len(telemetry) - 1) / observed_span
    control_latencies = [
        abs(
            command["control_applied_time_s"]
            - command["audio_end_time_s"]
            - command.get("response_delay_s", 0.0)
        )
        for command in commands
        if "control_applied_time_s" in command
    ]

    event_checks = []
    events = ground_truth["clearances"]
    for index, event in enumerate(events):
        current_dimension = dimension(event)
        next_same = next(
            (
                later
                for later in events[index + 1 :]
                if dimension(later) == current_dimension
            ),
            None,
        )
        hold_start = event["completion_time_s"]
        hold_end = next_same["issued_time_s"] if next_same else duration_s
        field = {
            "heading": "indicated_heading_deg",
            "altitude": "indicated_altitude_ft",
            "airspeed": "fdm_vias_kt",
        }[current_dimension]
        samples = [
            sample
            for sample in telemetry
            if hold_start is not None and hold_start <= sample["time_s"] < hold_end
        ]
        if current_dimension == "heading":
            errors = [angular_error_deg(sample[field], event["target_value"]) for sample in samples]
            tolerance = config["derivation"]["heading_completion_tolerance_deg"]
        elif current_dimension == "altitude":
            errors = [abs(sample[field] - event["target_value"]) for sample in samples]
            tolerance = config["derivation"]["altitude_completion_tolerance_ft"]
        else:
            errors = [abs(sample[field] - event["target_value"]) for sample in samples]
            tolerance = 3.0
        maximum_error = max(errors) if errors else None
        event_checks.append(
            {
                "clearance_index": event["clearance_index"],
                "status": event["status"],
                "completion_time_s": hold_start,
                "hold_samples": len(samples),
                "maximum_hold_error": maximum_error,
                "tolerance": tolerance,
                "passed": (
                    event["status"] in {"complied", "complied_late"}
                    and hold_start is not None
                    and bool(errors)
                    and maximum_error <= tolerance
                ),
            }
        )

    expected_outcomes = [
        {
            "clearance_index": event["clearance_index"],
            "expected_status": command.get("expected_status"),
            "actual_status": event["status"],
            "expected_overshoot": command.get("expected_overshoot"),
            "actual_overshoot": event["overshoot_bucket"],
            "passed": (
                command.get("expected_status") == event["status"]
                and command.get("expected_overshoot") == event["overshoot_bucket"]
            ),
        }
        for command, event in zip(commands, events, strict=True)
    ]
    indicated_heading_errors = [
        angular_error_deg(
            sample["indicated_heading_deg"],
            sample["heading_deg"],
        )
        for sample in telemetry
    ]
    trace_times = [sample["time_s"] for sample in controller_trace]
    fdm_airspeed_errors = [
        abs(sample["fdm_vias_kt"] - sample["airspeed_kt"])
        for sample in telemetry
    ]
    trace_errors = {"heading_deg": [], "altitude_ft": [], "airspeed_kt": []}
    for sample in telemetry:
        insertion = bisect.bisect_left(trace_times, sample["time_s"])
        candidates = [
            index
            for index in (insertion - 1, insertion)
            if 0 <= index < len(controller_trace)
        ]
        nearest = min(
            candidates,
            key=lambda index: abs(
                controller_trace[index]["time_s"] - sample["time_s"]
            ),
        )
        controller_sample = controller_trace[nearest]
        trace_errors["heading_deg"].append(
            angular_error_deg(
                sample["heading_deg"],
                controller_sample["heading_deg"],
            )
        )
        trace_errors["altitude_ft"].append(
            abs(sample["altitude_ft"] - controller_sample["altitude_ft"])
        )
        trace_errors["airspeed_kt"].append(
            abs(sample["airspeed_kt"] - controller_sample["airspeed_kt"])
        )

    checks = {
        "telemetry_rate": telemetry_rate_hz
        >= config.get("validation", {}).get("telemetry_min_hz", 15.0),
        "telemetry_max_gap": max(gaps)
        <= config.get("validation", {}).get("telemetry_max_gap_s", 0.5),
        "telemetry_end_coverage": abs(telemetry[-1]["time_s"] - duration_s) <= 0.25,
        "control_latency": not control_latencies or max(control_latencies) <= 0.1,
        "all_complied_events_held": all(
            item["passed"]
            for item in event_checks
            if item["status"] in {"complied", "complied_late"}
        ),
        "scenario_intent": all(item["passed"] for item in expected_outcomes),
        "heading_indicator_tracks_state": max(indicated_heading_errors) <= 2.0,
        "airspeed_indicator_tracks_state": (
            max(fdm_airspeed_errors) <= 1.0
        ),
        "controller_trace_matches_telemetry": (
            percentile(trace_errors["heading_deg"], 0.99) <= 2.0
            and percentile(trace_errors["altitude_ft"], 0.99) <= 5.0
            and percentile(trace_errors["airspeed_kt"], 0.99) <= 1.0
        ),
    }
    result = {
        "passed": all(checks.values()),
        "checks": checks,
        "metrics": {
            "telemetry_samples": len(telemetry),
            "telemetry_rate_hz": telemetry_rate_hz,
            "telemetry_max_gap_s": max(gaps),
            "telemetry_last_time_s": telemetry[-1]["time_s"],
            "maximum_control_latency_s": max(control_latencies) if control_latencies else None,
            "maximum_heading_indicator_error_deg": max(indicated_heading_errors),
            "maximum_airspeed_indicator_error_kt": max(fdm_airspeed_errors),
            "controller_trace_p99_heading_error_deg": percentile(
                trace_errors["heading_deg"],
                0.99,
            ),
            "controller_trace_p99_altitude_error_ft": percentile(
                trace_errors["altitude_ft"],
                0.99,
            ),
            "controller_trace_p99_airspeed_error_kt": percentile(
                trace_errors["airspeed_kt"],
                0.99,
            ),
        },
        "events": event_checks,
        "expected_outcomes": expected_outcomes,
    }
    dump_json(ROOT / "validation_results.json", result)
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
