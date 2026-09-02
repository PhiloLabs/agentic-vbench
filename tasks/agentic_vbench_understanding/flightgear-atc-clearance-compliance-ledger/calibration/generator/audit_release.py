from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_RELEASE = Path(
    os.environ.get("FLIGHTGEAR_RELEASE_ROOT", ROOT / "artifacts/release")
)


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-root", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    video = args.release_root / "flight.mp4"
    private = args.release_root / "private"
    manifest = json.loads((args.release_root / "manifest.json").read_text())
    truth = json.loads((private / "ground_truth.json").read_text())
    commands = [
        json.loads(line)
        for line in (private / "command_log.jsonl").read_text().splitlines()
        if line.strip()
    ]
    with (private / "telemetry.csv").open(newline="", encoding="utf-8") as handle:
        telemetry = [
            {key: value for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]

    probe = json.loads(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:format_tags:stream=index,codec_type,codec_name,width,height,r_frame_rate:chapter",
                "-of",
                "json",
                str(video),
            ]
        ).stdout
    )
    streams = probe["streams"]
    video_streams = [stream for stream in streams if stream["codec_type"] == "video"]
    audio_streams = [stream for stream in streams if stream["codec_type"] == "audio"]
    other_streams = [
        stream
        for stream in streams
        if stream["codec_type"] not in {"video", "audio"}
    ]
    duration_s = float(probe["format"]["duration"])

    telemetry_times = [float(row["time_s"]) for row in telemetry]
    telemetry_gaps = [
        later - earlier
        for earlier, later in zip(telemetry_times, telemetry_times[1:])
        if later >= earlier
    ]
    heading_errors = [
        abs(
            (
                float(row["indicated_heading_deg"])
                - float(row["heading_deg"])
                + 180.0
            )
            % 360.0
            - 180.0
        )
        for row in telemetry
    ]
    airspeed_errors = [
        abs(float(row["fdm_vias_kt"]) - float(row["airspeed_kt"]))
        for row in telemetry
    ]
    control_offsets = [
        abs(
            float(command["control_applied_time_s"])
            - float(command["audio_end_time_s"])
            - float(command.get("response_delay_s", 0.0))
        )
        for command in commands
        if "control_applied_time_s" in command
    ]
    events = truth["clearances"]
    statuses = Counter(event["status"] for event in events)
    overshoots = Counter(event["overshoot_bucket"] for event in events)

    volume = run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(video),
            "-vn",
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ]
    ).stderr
    mean_match = re.search(r"mean_volume: (-?[0-9.]+) dB", volume)
    max_match = re.search(r"max_volume: (-?[0-9.]+) dB", volume)

    checks = {
        "duration": abs(duration_s - 3600.0) <= 0.5,
        "single_h264_video": (
            len(video_streams) == 1
            and video_streams[0]["codec_name"] == "h264"
            and int(video_streams[0]["width"]) == 1280
            and int(video_streams[0]["height"]) == 720
            and video_streams[0]["r_frame_rate"] == "15/1"
        ),
        "single_aac_audio": (
            len(audio_streams) == 1 and audio_streams[0]["codec_name"] == "aac"
        ),
        "no_extra_streams_or_chapters": not other_streams and not probe.get("chapters"),
        "clearance_count": len(events) == 65 and len(commands) == 65,
        "contiguous_indices": [
            event["clearance_index"] for event in events
        ] == list(range(1, 66)),
        "all_status_classes": all(
            statuses[status] > 0
            for status in (
                "complied",
                "complied_late",
                "superseded",
                "violated",
                "incomplete",
            )
        ),
        "small_and_large_overshoots": (
            overshoots["small"] > 0 and overshoots["large"] > 0
        ),
        "telemetry_covers_video": (
            telemetry_times[0] <= 0.25
            and abs(telemetry_times[-1] - duration_s) <= 0.5
        ),
        "telemetry_gap": max(telemetry_gaps) <= 1.0,
        "heading_indicator_visibility": max(heading_errors) <= 2.0,
        "airspeed_indicator_visibility": max(airspeed_errors) <= 1.0,
        "control_after_speech": max(control_offsets) <= 0.1,
        "audio_present": (
            mean_match is not None
            and max_match is not None
            and float(mean_match.group(1)) > -45.0
        ),
        "manifest_matches": (
            manifest["clearance_count"] == len(events)
            and manifest["status_counts"] == dict(statuses)
            and manifest["overshoot_counts"] == dict(overshoots)
        ),
    }

    contact_sheet = args.release_root / "contact_sheet.png"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-vf",
            "fps=1/300,scale=640:-1,tile=4x3",
            "-frames:v",
            "1",
            "-y",
            str(contact_sheet),
        ],
        check=True,
    )
    frame_dump = args.release_root / "frame_dump"
    frame_dump.mkdir(exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-vf",
            "fps=1/10,scale=320:-1,tile=6x6",
            "-frames:v",
            "10",
            "-y",
            str(frame_dump / "sheet_%02d.jpg"),
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            "1800",
            "-i",
            str(video),
            "-frames:v",
            "1",
            "-y",
            str(args.release_root / "single_frame.png"),
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-map",
            "0:v:0",
            "-c",
            "copy",
            "-an",
            "-map_metadata",
            "-1",
            "-y",
            str(args.release_root / "flight_video_only.mp4"),
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            "-map_metadata",
            "-1",
            "-y",
            str(args.release_root / "flight_audio_only.wav"),
        ],
        check=True,
    )

    result: dict[str, Any] = {
        "passed": all(checks.values()),
        "checks": checks,
        "metrics": {
            "duration_s": duration_s,
            "video_bytes": video.stat().st_size,
            "telemetry_samples": len(telemetry),
            "maximum_telemetry_gap_s": max(telemetry_gaps),
            "maximum_heading_indicator_error_deg": max(heading_errors),
            "maximum_airspeed_indicator_error_kt": max(airspeed_errors),
            "maximum_control_timing_error_s": max(control_offsets),
            "audio_mean_db": None if mean_match is None else float(mean_match.group(1)),
            "audio_peak_db": None if max_match is None else float(max_match.group(1)),
            "status_counts": dict(statuses),
            "overshoot_counts": dict(overshoots),
            "format_tags": probe["format"].get("tags", {}),
        },
    }
    report = args.report or args.release_root / "release_audit.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
