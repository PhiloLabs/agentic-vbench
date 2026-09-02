from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pilot_lib import (
    angular_delta_deg,
    angular_error_deg,
    dump_json,
    load_telemetry,
)


CODE_ROOT = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("FLIGHTGEAR_OUTPUT_DIR", CODE_ROOT)).resolve()
CONFIG_PATH = Path(os.environ.get("FLIGHTGEAR_CONFIG", CODE_ROOT / "pilot_config.json")).resolve()


def window(
    samples: list[dict[str, float]],
    start_s: float,
    end_s: float | None,
) -> list[dict[str, float]]:
    return [
        sample
        for sample in samples
        if sample["time_s"] >= start_s and (end_s is None or sample["time_s"] < end_s)
    ]


def stable_completion(
    samples: list[dict[str, float]],
    predicate: Any,
    minimum_hold_s: float,
) -> float | None:
    for index, sample in enumerate(samples):
        remaining = samples[index:]
        if remaining[-1]["time_s"] - sample["time_s"] < minimum_hold_s:
            return None
        if all(predicate(candidate) for candidate in remaining):
            return sample["time_s"]
    return None


def sustained_rate_start(
    samples: list[dict[str, float]],
    value: Any,
    delta: Any,
    direction: float,
    minimum_rate: float,
    hold_s: float,
) -> float | None:
    for index, start in enumerate(samples):
        middle = next(
            (
                candidate
                for candidate in samples[index + 1 :]
                if candidate["time_s"] - start["time_s"] >= hold_s / 2.0
            ),
            None,
        )
        finish = next(
            (
                candidate
                for candidate in samples[index + 1 :]
                if candidate["time_s"] - start["time_s"] >= hold_s
                and middle is not None
                and candidate["time_s"] > middle["time_s"]
            ),
            None,
        )
        if middle is None or finish is None:
            return None
        intervals = ((start, middle), (middle, finish), (start, finish))
        rates = [
            delta(value(first), value(last))
            / (last["time_s"] - first["time_s"])
            for first, last in intervals
        ]
        if all(direction * rate >= minimum_rate for rate in rates):
            return start["time_s"]
    return None


def derive_event(
    command: dict[str, Any],
    next_same_dimension: dict[str, Any] | None,
    samples: list[dict[str, float]],
    rules: dict[str, float],
) -> dict[str, Any]:
    issue = command["issued_time_s"]
    control_applied = command.get("control_applied_time_s", issue)
    end = next_same_dimension["issued_time_s"] if next_same_dimension else None
    full_window = window(samples, issue, end)
    relevant = window(samples, control_applied, end)
    if not full_window or not relevant:
        raise ValueError(f"No telemetry for clearance {command['clearance_index']}")
    command_type = command["command_type"]
    target = command["target_value"]

    if "heading" in command_type:
        field = "indicated_heading_deg"
        initial = full_window[0][field]
        direction = 1.0 if "right" in command_type else -1.0

        def completed(sample: dict[str, float]) -> bool:
            return angular_error_deg(sample[field], target) <= rules["heading_completion_tolerance_deg"]

        execution = sustained_rate_start(
            relevant,
            lambda sample: sample[field],
            angular_delta_deg,
            direction,
            rules["heading_execution_rate_deg_s"],
            rules["execution_hold_s"],
        )
        wrong_execution = sustained_rate_start(
            relevant,
            lambda sample: sample[field],
            angular_delta_deg,
            -direction,
            rules["heading_execution_rate_deg_s"],
            rules["execution_hold_s"],
        )
        completion_samples = relevant if execution is None else window(relevant, execution, end)
        completion = None if execution is None else stable_completion(
            completion_samples,
            completed,
            rules["completion_hold_s"],
        )
        crossed = [
            direction * angular_delta_deg(target, sample[field])
            for sample in full_window
            if direction * angular_delta_deg(initial, sample[field]) > 0
        ]
        excursion = max([0.0, *crossed])
        maximum_progress = max(
            [0.0, *[
                direction * angular_delta_deg(initial, sample[field])
                for sample in full_window
            ]]
        )
        overshoot = "large" if excursion > 15 else "small" if excursion > 8 else "none"
    elif command["target_unit"] == "feet":
        field = "indicated_altitude_ft"
        initial = full_window[0][field]
        direction = 1.0 if command_type == "climb" else -1.0

        def completed(sample: dict[str, float]) -> bool:
            return abs(sample[field] - target) <= rules["altitude_completion_tolerance_ft"]

        execution = sustained_rate_start(
            relevant,
            lambda sample: sample[field],
            lambda start, finish: (finish - start) * 60.0,
            direction,
            rules["altitude_execution_rate_fpm"],
            rules["execution_hold_s"],
        )
        wrong_execution = sustained_rate_start(
            relevant,
            lambda sample: sample[field],
            lambda start, finish: (finish - start) * 60.0,
            -direction,
            rules["altitude_execution_rate_fpm"],
            rules["execution_hold_s"],
        )
        completion_samples = relevant if execution is None else window(relevant, execution, end)
        completion = None if execution is None else stable_completion(
            completion_samples,
            completed,
            rules["completion_hold_s"],
        )
        excursion = max([0.0, *[direction * (sample[field] - target) for sample in full_window]])
        maximum_progress = max(
            [0.0, *[direction * (sample[field] - initial) for sample in full_window]]
        )
        overshoot = "large" if excursion > 250 else "small" if excursion > 100 else "none"
    else:
        field = "fdm_vias_kt"
        initial = full_window[0][field]
        direction = 1.0 if command_type == "accelerate" else -1.0

        def completed(sample: dict[str, float]) -> bool:
            return abs(sample[field] - target) <= 3.0

        execution = sustained_rate_start(
            relevant,
            lambda sample: sample[field],
            lambda start, finish: finish - start,
            direction,
            0.5,
            rules["execution_hold_s"],
        )
        wrong_execution = sustained_rate_start(
            relevant,
            lambda sample: sample[field],
            lambda start, finish: finish - start,
            -direction,
            0.5,
            rules["execution_hold_s"],
        )
        completion_samples = relevant if execution is None else window(relevant, execution, end)
        completion = None if execution is None else stable_completion(
            completion_samples,
            completed,
            rules["completion_hold_s"],
        )
        excursion = max([0.0, *[direction * (sample[field] - target) for sample in full_window]])
        maximum_progress = max(
            [0.0, *[direction * (sample[field] - initial) for sample in full_window]]
        )
        overshoot = "large" if excursion > 10 else "small" if excursion > 3 else "none"

    if completion is not None:
        status = "complied_late" if execution is None or execution - issue > rules["late_response_s"] else "complied"
        superseded_by = None
    elif next_same_dimension is not None:
        status = "superseded"
        superseded_by = next_same_dimension["clearance_index"]
    elif wrong_execution is not None:
        status = "violated"
        superseded_by = None
    else:
        status = "incomplete"
        superseded_by = None

    def state_at(timestamp: float | None) -> tuple[float | None, float | None, float | None]:
        if timestamp is None:
            return None, None, None
        sample = next(
            (candidate for candidate in full_window if candidate["time_s"] >= timestamp),
            full_window[-1],
        )
        return (
            round(sample["indicated_altitude_ft"], 3),
            round(sample["indicated_heading_deg"], 3),
            round(sample["fdm_vias_kt"], 3),
        )

    execution_state = state_at(execution)
    completion_state = state_at(completion)
    return {
        "clearance_index": command["clearance_index"],
        "issued_time_s": round(issue, 3),
        "command_type": command_type,
        "target_value": command["target_value"],
        "target_unit": command["target_unit"],
        "issue_altitude_ft": round(full_window[0]["indicated_altitude_ft"], 3),
        "issue_heading_deg": round(full_window[0]["indicated_heading_deg"], 3),
        "issue_airspeed_kt": round(full_window[0]["fdm_vias_kt"], 3),
        "maximum_commanded_progress": round(maximum_progress, 3),
        "execution_altitude_ft": execution_state[0],
        "execution_heading_deg": execution_state[1],
        "execution_airspeed_kt": execution_state[2],
        "completion_altitude_ft": completion_state[0],
        "completion_heading_deg": completion_state[1],
        "completion_airspeed_kt": completion_state[2],
        "ending_altitude_ft": round(full_window[-1]["indicated_altitude_ft"], 3),
        "ending_heading_deg": round(full_window[-1]["indicated_heading_deg"], 3),
        "ending_airspeed_kt": round(full_window[-1]["fdm_vias_kt"], 3),
        "execution_start_time_s": None if execution is None else round(execution, 3),
        "completion_time_s": None if completion is None else round(completion, 3),
        "status": status,
        "superseded_by_index": superseded_by,
        "overshoot_bucket": overshoot,
    }


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    commands = [
        json.loads(line)
        for line in (ROOT / "command_log.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    samples = load_telemetry(ROOT / "telemetry.csv")
    dimensions = {}
    for command in commands:
        if "heading" in command["command_type"]:
            dimension = "heading"
        elif command["target_unit"] == "feet":
            dimension = "altitude"
        else:
            dimension = "airspeed"
        dimensions[command["clearance_index"]] = dimension
    events = []
    for index, command in enumerate(commands):
        next_same = next(
            (
                later
                for later in commands[index + 1 :]
                if dimensions[later["clearance_index"]] == dimensions[command["clearance_index"]]
            ),
            None,
        )
        events.append(derive_event(command, next_same, samples, config["derivation"]))
    ground_truth = {
        "source": {
            "tier": "logged",
            "flightgear_version": "2020.3.18",
            "aircraft": config["flightgear"]["aircraft"],
            "seed": config["seed"],
            "duration_s": config["duration_s"],
            "video_clock_offset_s": 0.0,
        },
        "clearances": events,
    }
    dump_json(ROOT / "ground_truth.json", ground_truth)
    dump_json(ROOT / "oracle.json", {"clearances": events})
    dump_json(ROOT / "empty.json", {"clearances": []})
    noisy_events = [dict(events[0])]
    if len(events) > 1:
        noisy = dict(events[1])
        noisy["status"] = "violated" if noisy["status"] != "violated" else "incomplete"
        noisy_events.append(noisy)
    dump_json(ROOT / "noisy.json", {"clearances": noisy_events})


if __name__ == "__main__":
    main()
