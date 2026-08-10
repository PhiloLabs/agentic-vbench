#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


def dimension(event: dict[str, Any]) -> str:
    return {
        "feet": "altitude",
        "degrees": "heading",
        "knots": "airspeed",
    }[event["target_unit"]]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def extract(media: Path, timestamp: float, output: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(media),
            "-frames:v",
            "1",
            "-vf",
            "crop=500:320:390:300,scale=1000:640",
            "-y",
            str(output),
        ],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--media", required=True, type=Path)
    parser.add_argument("--ground-truth", required=True, type=Path)
    parser.add_argument("--telemetry", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()

    truth = json.loads(args.ground_truth.read_text(encoding="utf-8"))
    events = truth["clearances"]
    with args.telemetry.open(encoding="utf-8", newline="") as handle:
        telemetry = [
            {key: float(value) if key != "segment_id" else value for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for offset, event in enumerate(events):
        next_same = next(
            (
                later
                for later in events[offset + 1 :]
                if dimension(later) == dimension(event)
                and int(later["issued_time_s"] // 720)
                == int(event["issued_time_s"] // 720)
            ),
            None,
        )
        leg_end = (int(event["issued_time_s"] // 720) + 1) * 720
        window_end = (
            next_same["issued_time_s"] - 0.1
            if next_same is not None
            else leg_end - 0.1
        )
        moments = {
            "issue": event["issued_time_s"],
            "window_end": window_end,
        }
        samples = [
            sample
            for sample in telemetry
            if event["issued_time_s"] <= sample["time_s"] <= window_end
        ]
        if event["target_unit"] == "degrees":
            field = "indicated_heading_deg"
            initial = event["issue_heading_deg"]
            direction = 1.0 if "right" in event["command_type"] else -1.0

            def progress(sample: dict[str, Any]) -> float:
                delta = (sample[field] - initial + 180.0) % 360.0 - 180.0
                return direction * delta
        elif event["target_unit"] == "feet":
            field = "indicated_altitude_ft"
            initial = event["issue_altitude_ft"]
            direction = 1.0 if event["command_type"] == "climb" else -1.0

            def progress(sample: dict[str, Any]) -> float:
                return direction * (sample[field] - initial)
        else:
            field = "fdm_vias_kt"
            initial = event["issue_airspeed_kt"]
            direction = 1.0 if event["command_type"] == "accelerate" else -1.0

            def progress(sample: dict[str, Any]) -> float:
                return direction * (sample[field] - initial)
        peak_sample = max(samples, key=progress)
        peak_progress = max(0.0, progress(peak_sample))
        moments["maximum_progress"] = peak_sample["time_s"]
        if event["execution_start_time_s"] is not None:
            moments["execution"] = event["execution_start_time_s"]
        if event["completion_time_s"] is not None:
            moments["completion"] = event["completion_time_s"]
        frames = {}
        for label, timestamp in moments.items():
            output = args.output_dir / (
                f"c{event['clearance_index']:02d}_{label}_{timestamp:.3f}.png"
            )
            extract(args.media, timestamp, output)
            frames[label] = {
                "time_s": round(timestamp, 3),
                "file": output.name,
                "sha256": sha256(output),
            }
        records.append(
            {
                "clearance_index": event["clearance_index"],
                "leg": int(event["issued_time_s"] // 720) + 1,
                "command_type": event["command_type"],
                "target_value": event["target_value"],
                "target_unit": event["target_unit"],
                "status": event["status"],
                "overshoot_bucket": event["overshoot_bucket"],
                "state_snapshots": {
                    key: event[key]
                    for key in event
                    if key.startswith(("issue_", "execution_", "completion_", "ending_"))
                },
                "telemetry_maximum_commanded_progress": round(peak_progress, 3),
                "progress_error": round(
                    peak_progress - event["maximum_commanded_progress"],
                    3,
                ),
                "frames": frames,
            }
        )
    manifest = {
        "media_sha256": sha256(args.media),
        "ground_truth_sha256": sha256(args.ground_truth),
        "clearances": len(records),
        "records": records,
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
