#!/usr/bin/env python3
import argparse
import json
import math
import random
import re
import subprocess
import tempfile
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16000
HOP_SAMPLES = 320
HOP_SECONDS = HOP_SAMPLES / SAMPLE_RATE
SILENCE_DB = -40.0
MINIMUM_SILENCE_S = 0.4
MAXIMUM_ALLOWED_TOLERANCE_S = 4.0


def decode_audio(media, output):
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(media),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-f",
            "s16le",
            str(output),
        ],
        check=True,
    )


def detect_scene_cuts(media):
    completed = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "info",
            "-i",
            str(media),
            "-an",
            "-vf",
            "scale=320:-2,fps=4,select='gt(scene,0.25)',showinfo",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return np.array(
        sorted(
            {
                float(match)
                for match in re.findall(
                    r"pts_time:([0-9.]+)", completed.stderr
                )
            }
        )
    )


def silence_intervals(samples):
    frame_count = len(samples) // HOP_SAMPLES
    frames = samples[: frame_count * HOP_SAMPLES].reshape(
        frame_count, HOP_SAMPLES
    )
    db = 20 * np.log10(
        np.sqrt(np.mean(frames * frames, axis=1)) + 1e-12
    )
    quiet = db < SILENCE_DB
    changes = np.flatnonzero(np.diff(quiet.astype(np.int8)))
    edges = np.concatenate(([0], changes + 1, [len(quiet)]))
    return [
        (start * HOP_SECONDS, end * HOP_SECONDS)
        for start, end in zip(edges[:-1], edges[1:])
        if quiet[start]
        and (end - start) * HOP_SECONDS >= MINIMUM_SILENCE_S
    ]


def contains(intervals, time_s):
    starts = np.array([start for start, _ in intervals])
    ends = np.array([end for _, end in intervals])
    index = np.searchsorted(starts, time_s) - 1
    return index >= 0 and time_s <= ends[index]


def nearest_transition(transitions, time_s):
    index = int(np.argmin(np.abs(transitions - time_s)))
    return float(transitions[index] - time_s)


def distribution(values):
    absolute = np.abs(values)
    return {
        "median_abs_s": round(float(np.median(absolute)), 3),
        "p90_abs_s": round(float(np.percentile(absolute, 90)), 3),
        "p95_abs_s": round(float(np.percentile(absolute, 95)), 3),
        "max_abs_s": round(float(np.max(absolute)), 3),
        "within_2s": round(float(np.mean(absolute <= 2)), 6),
        "within_4s": round(float(np.mean(absolute <= 4)), 6),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--media", required=True, type=Path)
    parser.add_argument("--ground-truth", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    ground_truth = json.loads(args.ground_truth.read_text())["turns"]
    with tempfile.TemporaryDirectory() as directory:
        raw = Path(directory) / "floor.raw"
        decode_audio(args.media, raw)
        samples = (
            np.fromfile(raw, dtype=np.int16).astype(np.float32) / 32768
        )

    intervals = silence_intervals(samples)
    transitions = np.array(
        sorted({value for interval in intervals for value in interval})
    )
    scene_cuts = detect_scene_cuts(args.media)
    sweep = []
    for shift in np.arange(-10.0, 10.001, 0.05):
        start_rate = np.mean(
            [
                contains(intervals, turn["start_time_s"] + shift)
                for turn in ground_truth
            ]
        )
        end_rate = np.mean(
            [
                contains(intervals, turn["end_time_s"] + shift)
                for turn in ground_truth
            ]
        )
        sweep.append(
            {
                "shift_s": round(float(shift), 2),
                "start_pause_rate": round(float(start_rate), 6),
                "end_pause_rate": round(float(end_rate), 6),
                "joint_rate": round(float(start_rate + end_rate), 6),
            }
        )
    best_start = max(
        sweep,
        key=lambda item: (
            item["start_pause_rate"],
            -abs(item["shift_s"]),
        ),
    )
    best_joint = max(sweep, key=lambda item: item["joint_rate"])
    start_errors = [
        nearest_transition(transitions, turn["start_time_s"])
        for turn in ground_truth
    ]
    end_errors = [
        nearest_transition(transitions, turn["end_time_s"])
        for turn in ground_truth
    ]
    combined_start_errors = [
        min(
            abs(start_error),
            float(
                np.min(np.abs(scene_cuts - turn["start_time_s"]))
            ),
        )
        for turn, start_error in zip(
            ground_truth, start_errors, strict=True
        )
    ]
    combined_end_errors = [
        min(
            abs(end_error),
            float(np.min(np.abs(scene_cuts - turn["end_time_s"]))),
        )
        for turn, end_error in zip(
            ground_truth, end_errors, strict=True
        )
    ]
    derived_tolerance = (
        math.ceil(
            max(
                max(combined_start_errors),
                max(combined_end_errors),
            )
            * 2
        )
        / 2
    )
    duration_s = len(samples) / SAMPLE_RATE
    randomizer = random.Random(20260727)
    random_times = [
        randomizer.uniform(0.0, duration_s) for _ in range(1000)
    ]
    random_combined_errors = [
        min(
            abs(nearest_transition(transitions, time_s)),
            float(np.min(np.abs(scene_cuts - time_s))),
        )
        for time_s in random_times
    ]
    result = {
        "method": {
            "audio_sample_rate": SAMPLE_RATE,
            "analysis_hop_s": HOP_SECONDS,
            "silence_threshold_db": SILENCE_DB,
            "minimum_silence_s": MINIMUM_SILENCE_S,
        },
        "ground_truth_turns": len(ground_truth),
        "silence_intervals": len(intervals),
        "scene_cuts": len(scene_cuts),
        "silence_fraction": round(
            float(
                sum(end - start for start, end in intervals)
                / (len(samples) / SAMPLE_RATE)
            ),
            6,
        ),
        "zero_shift": next(
            item for item in sweep if item["shift_s"] == 0.0
        ),
        "best_start_shift": best_start,
        "best_joint_shift": best_joint,
        "acceptance": {
            "minimum_zero_shift_start_pause_rate": 0.85,
            "maximum_absolute_best_shift_s": 0.5,
            "maximum_allowed_boundary_tolerance_s": (
                MAXIMUM_ALLOWED_TOLERANCE_S
            ),
            "derived_boundary_tolerance_s": derived_tolerance,
            "observed_max_start_error_s": round(
                float(max(combined_start_errors)), 3
            ),
            "observed_max_end_error_s": round(
                float(max(combined_end_errors)), 3
            ),
            "passes": (
                next(
                    item for item in sweep if item["shift_s"] == 0.0
                )["start_pause_rate"]
                >= 0.85
                and abs(best_start["shift_s"]) <= 0.5
                and derived_tolerance <= MAXIMUM_ALLOWED_TOLERANCE_S
            ),
        },
        "start_transition_errors": distribution(start_errors),
        "end_transition_errors": distribution(end_errors),
        "combined_start_errors": distribution(
            combined_start_errors
        ),
        "combined_end_errors": distribution(combined_end_errors),
        "random_time_combined_errors": distribution(
            random_combined_errors
        ),
        "derived_boundary_tolerance_s": derived_tolerance,
        "turns": [
            {
                "turn_index": turn["turn_index"],
                "start_transition_error_s": round(start_error, 3),
                "end_transition_error_s": round(end_error, 3),
            }
            for turn, start_error, end_error in zip(
                ground_truth,
                start_errors,
                end_errors,
                strict=True,
            )
        ],
        "sweep": sweep,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "zero_shift": result["zero_shift"],
                "best_start_shift": result["best_start_shift"],
                "best_joint_shift": result["best_joint_shift"],
                "acceptance": result["acceptance"],
                "derived_boundary_tolerance_s": derived_tolerance,
            }
        )
    )


if __name__ == "__main__":
    main()
