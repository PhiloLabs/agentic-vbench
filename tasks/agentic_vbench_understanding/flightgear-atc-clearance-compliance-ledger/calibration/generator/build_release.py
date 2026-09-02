from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_SEGMENTS = Path(
    os.environ.get("FLIGHTGEAR_SEGMENTS_ROOT", ROOT / "artifacts/segments")
)
DEFAULT_OUTPUT = Path(
    os.environ.get("FLIGHTGEAR_RELEASE_ROOT", ROOT / "artifacts/release")
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def media_probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=index,codec_type,codec_name,width,height,r_frame_rate",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def command_output(command: list[str]) -> str:
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def offset_event(
    event: dict[str, Any],
    *,
    time_offset_s: float,
    index_offset: int,
) -> dict[str, Any]:
    shifted = dict(event)
    shifted["clearance_index"] += index_offset
    for field in (
        "issued_time_s",
        "execution_start_time_s",
        "completion_time_s",
    ):
        if shifted[field] is not None:
            shifted[field] = round(float(shifted[field]) + time_offset_s, 3)
    if shifted["superseded_by_index"] is not None:
        shifted["superseded_by_index"] += index_offset
    return shifted


def offset_command(
    command: dict[str, Any],
    *,
    time_offset_s: float,
    index_offset: int,
) -> dict[str, Any]:
    shifted = dict(command)
    shifted["clearance_index"] += index_offset
    for field in (
        "issued_time_s",
        "issued_actual_time_s",
        "control_applied_time_s",
        "audio_start_time_s",
        "audio_end_time_s",
    ):
        if field in shifted and shifted[field] is not None:
            shifted[field] = round(float(shifted[field]) + time_offset_s, 3)
    return shifted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--segments-root", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    args.output_root.mkdir(parents=True, exist_ok=True)
    private_dir = args.output_root / "private"
    private_dir.mkdir(exist_ok=True)
    segments = [args.segments_root / f"flight_{index:02d}" for index in range(1, 6)]
    missing = [str(path) for path in segments if not (path / "pilot.mp4").is_file()]
    if missing:
        raise SystemExit(f"missing generated segments: {missing}")

    concat_file = args.output_root / "segments.txt"
    concat_file.write_text(
        "".join(f"file '{(segment / 'pilot.mp4').resolve()}'\n" for segment in segments),
        encoding="utf-8",
    )
    final_video = args.output_root / "flight.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0",
            "-c",
            "copy",
            "-map_metadata",
            "-1",
            "-movflags",
            "+faststart",
            "-y",
            str(final_video),
        ],
        check=True,
    )

    all_events = []
    all_commands = []
    segment_records = []
    index_offset = 0
    time_offset_s = 0.0
    telemetry_fields: list[str] | None = None
    telemetry_path = private_dir / "telemetry.csv"
    with telemetry_path.open("w", encoding="utf-8", newline="") as telemetry_handle:
        telemetry_writer: csv.DictWriter[str] | None = None
        for segment_index, segment in enumerate(segments, start=1):
            probe = media_probe(segment / "pilot.mp4")
            duration_s = float(probe["format"]["duration"])
            validation = json.loads(
                (segment / "validation_results.json").read_text(encoding="utf-8")
            )
            if not validation["passed"]:
                raise RuntimeError(f"{segment.name} failed validation")
            alignment = json.loads(
                (segment / "alignment_report.json").read_text(encoding="utf-8")
            )
            if alignment.get("recovered_after_post_render_cadence_gate"):
                raise RuntimeError(f"{segment.name} used forbidden recovery metadata")
            truth = json.loads(
                (segment / "ground_truth.json").read_text(encoding="utf-8")
            )
            events = [
                offset_event(
                    event,
                    time_offset_s=time_offset_s,
                    index_offset=index_offset,
                )
                for event in truth["clearances"]
            ]
            commands = [
                offset_command(
                    json.loads(line),
                    time_offset_s=time_offset_s,
                    index_offset=index_offset,
                )
                for line in (segment / "command_log.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            ]
            all_events.extend(events)
            all_commands.extend(commands)

            with (segment / "telemetry.csv").open(
                encoding="utf-8", newline=""
            ) as segment_handle:
                reader = csv.DictReader(segment_handle)
                if telemetry_fields is None:
                    telemetry_fields = ["segment_id", *reader.fieldnames]
                    telemetry_writer = csv.DictWriter(
                        telemetry_handle,
                        fieldnames=telemetry_fields,
                    )
                    telemetry_writer.writeheader()
                assert telemetry_writer is not None
                for row in reader:
                    row["time_s"] = round(float(row["time_s"]) + time_offset_s, 6)
                    telemetry_writer.writerow(
                        {"segment_id": f"flight_{segment_index:02d}", **row}
                    )

            segment_records.append(
                {
                    "segment_id": f"flight_{segment_index:02d}",
                    "offset_s": time_offset_s,
                    "duration_s": duration_s,
                    "video_sha256": sha256(segment / "pilot.mp4"),
                    "validation_metrics": validation["metrics"],
                    "clearance_count": len(events),
                    "config_sha256": sha256(segment / "config.json"),
                    "alignment_sha256": sha256(segment / "alignment_report.json"),
                }
            )
            index_offset += len(events)
            time_offset_s += duration_s

    ground_truth = {
        "source": {
            "tier": "logged",
            "generator": "FlightGear 2020.3.18 C172P with external scenario-controlled state",
            "total_duration_s": round(time_offset_s, 3),
            "segments": segment_records,
        },
        "clearances": all_events,
    }
    (private_dir / "ground_truth.json").write_text(
        json.dumps(ground_truth, indent=2) + "\n",
        encoding="utf-8",
    )
    (private_dir / "command_log.jsonl").write_text(
        "".join(json.dumps(command, sort_keys=True) + "\n" for command in all_commands),
        encoding="utf-8",
    )
    (private_dir / "oracle.json").write_text(
        json.dumps({"clearances": all_events}, indent=2) + "\n",
        encoding="utf-8",
    )
    (private_dir / "empty.json").write_text(
        json.dumps({"clearances": []}, indent=2) + "\n",
        encoding="utf-8",
    )
    asr_only = []
    for event in all_events:
        guessed = dict(event)
        guessed["execution_start_time_s"] = None
        guessed["completion_time_s"] = None
        guessed["status"] = "incomplete"
        guessed["superseded_by_index"] = None
        guessed["overshoot_bucket"] = "none"
        guessed["issue_altitude_ft"] = 4000
        guessed["issue_heading_deg"] = 0
        guessed["issue_airspeed_kt"] = 100
        guessed["maximum_commanded_progress"] = 0
        guessed["execution_altitude_ft"] = None
        guessed["execution_heading_deg"] = None
        guessed["execution_airspeed_kt"] = None
        guessed["completion_altitude_ft"] = None
        guessed["completion_heading_deg"] = None
        guessed["completion_airspeed_kt"] = None
        guessed["ending_altitude_ft"] = 4000
        guessed["ending_heading_deg"] = 0
        guessed["ending_airspeed_kt"] = 100
        asr_only.append(guessed)
    (private_dir / "asr_only_upper_bound.json").write_text(
        json.dumps({"clearances": asr_only}, indent=2) + "\n",
        encoding="utf-8",
    )

    probe = media_probe(final_video)
    manifest = {
        "video": "flight.mp4",
        "sha256": sha256(final_video),
        "bytes": final_video.stat().st_size,
        "probe": probe,
        "clearance_count": len(all_events),
        "status_counts": dict(Counter(event["status"] for event in all_events)),
        "overshoot_counts": dict(
            Counter(event["overshoot_bucket"] for event in all_events)
        ),
        "segments": segment_records,
        "generator_files": {
            name: sha256(ROOT / name)
            for name in (
                "build_full_dataset.py",
                "run_pilot.py",
                "pilot_lib.py",
                "telemetry_protocol.xml",
                "derive_ground_truth.py",
                "validate_run.py",
                "build_release.py",
            )
        },
        "generation_environment": {
            "flightgear_package_version": command_output(
                ["dpkg-query", "-W", "-f=${Version}", "flightgear"]
            ),
            "ffmpeg_version": command_output(["ffmpeg", "-version"]).splitlines()[0],
            "espeak_ng_version": command_output(["espeak-ng", "--version"]).splitlines()[0],
            "espeak_ng_package_version": command_output(
                ["dpkg-query", "-W", "-f=${Version}", "espeak-ng"]
            ),
            "espeak_ng_binary_sha256": sha256(Path("/usr/bin/espeak-ng")),
        },
    }
    (args.output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
