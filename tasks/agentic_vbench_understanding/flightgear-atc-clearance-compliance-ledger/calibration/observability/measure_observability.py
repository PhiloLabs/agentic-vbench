#!/usr/bin/env python3
"""Measure whether the ledger's instrument snapshots are readable at all.

The first revision of this task audited 19 of 65 events. The maintainer asked
for all 65, and this is that audit.

What this file is: a *comparison harness*, not an instrument reader. It loads a
pre-computed 1 Hz reconstruction of the three instruments from ``telemetry.npz``,
samples it at every event time named in the ground truth, and records the
absolute error against the ground-truth snapshot. It contains no video decoding
and cannot regenerate the reconstruction -- read ``--telemetry`` as an input, not
as a cache.

The reconstruction itself came from the instrument reader built during the
Claude Opus 4.8 rollout (per-pixel temporal median background subtraction,
radial brightness profiles for the needles, FFT cross-correlation of polar
patches for the heading card, then a monotonic angle -> value table per gauge).
That reader is not shipped here, so section 1 of README.md reproduces only in
the sense that the *comparison* replays exactly; it is not an independent
re-derivation from the video. README.md states the resulting conflict of
interest, and sections 2 and 3 of that document are the reader-independent
arguments.

Known limitation of the supplied reconstruction: ``spd_kt`` saturates at 72.0
for t=562..719 rather than following the leg-1 deceleration to 57 kt, and
``alt_ft`` flattens at 4399.8 over t=705..719. The three events this audit
reports as failures at 100/8/3 (#9, #12, #13, all the ``ending`` snapshot at
t=719.0) are the tail of that flat-line, so they understate the reader and
should not be read as "the video is unreadable there".

Sampling never interpolates across a leg cut: the five legs are independent
recordings spliced end to end, so a sample that straddles 720/1440/2160/2880
blends two unrelated flights. Getting this wrong is what produced the twelve
"gross outliers" in an earlier draft of this audit -- the same class of
boundary bug the scorer had.

Usage:
    measure_observability.py --telemetry telemetry.npz [--out audit_65_events.json]

The telemetry archive holds alt_ft, hdg_deg and spd_kt at 1 Hz. It is committed
next to this script (21 KB), so the audit re-runs without the 323 MB video.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
GROUND_TRUTH = ROOT / "steps" / "solve" / "tests" / "ground_truth.json"
LEG_DURATION_S = 720.0

TOLERANCE_PACKAGES = (
    (25.0, 2.0, 2.0),
    (50.0, 4.0, 3.0),
    (75.0, 6.0, 3.0),
    (100.0, 8.0, 3.0),
    (150.0, 10.0, 5.0),
    (200.0, 12.0, 6.0),
)


def sample(series: np.ndarray, when: float, *, circular: bool = False) -> float:
    """Linear sample that is clamped inside the event's own leg."""
    leg = int(when // LEG_DURATION_S)
    low = leg * LEG_DURATION_S
    high = min((leg + 1) * LEG_DURATION_S - 1, len(series) - 1)
    when = max(low, min(float(when), high))
    first = int(math.floor(when))
    second = min(first + 1, int(high))
    fraction = when - first
    before, after = float(series[first]), float(series[second])
    if circular:
        step = ((after - before + 180.0) % 360.0) - 180.0
        return (before + fraction * step) % 360.0
    return before + fraction * (after - before)


def circular_error(predicted: float, expected: float) -> float:
    return abs((predicted - expected + 180.0) % 360.0 - 180.0)


def ending_time(events: list[dict], position: int) -> float:
    """When the clearance stops being the live instruction on its dimension."""
    event = events[position]
    leg_end = (int(event["issued_time_s"] // LEG_DURATION_S) + 1) * LEG_DURATION_S
    dimension = event["target_unit"]
    following = None
    for later in events[position + 1 :]:
        if later["issued_time_s"] >= leg_end:
            break
        if later["target_unit"] == dimension:
            following = later["issued_time_s"]
            break
    # One full second inside the leg: never sample the splice itself.
    return min(following if following is not None else leg_end, leg_end) - 1.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--telemetry", required=True)
    parser.add_argument("--out", default=str(Path(__file__).with_name("audit_65_events.json")))
    arguments = parser.parse_args()

    archive = np.load(arguments.telemetry)
    altitude = archive["alt_ft"].astype(float)
    heading = archive["hdg_deg"].astype(float)
    airspeed = archive["spd_kt"].astype(float)
    events = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))["clearances"]

    snapshots = []
    for position, event in enumerate(events):
        moments = (
            ("issue", event["issued_time_s"]),
            ("execution", event["execution_start_time_s"]),
            ("completion", event["completion_time_s"]),
            ("ending", ending_time(events, position)),
        )
        for prefix, when in moments:
            if when is None or event[f"{prefix}_altitude_ft"] is None:
                continue
            snapshots.append(
                {
                    "clearance_index": event["clearance_index"],
                    "snapshot": prefix,
                    "time_s": round(float(when), 3),
                    "altitude_error_ft": round(
                        abs(sample(altitude, when) - event[f"{prefix}_altitude_ft"]), 3
                    ),
                    "heading_error_deg": round(
                        circular_error(
                            sample(heading, when, circular=True), event[f"{prefix}_heading_deg"]
                        ),
                        3,
                    ),
                    "airspeed_error_kt": round(
                        abs(sample(airspeed, when) - event[f"{prefix}_airspeed_kt"]), 3
                    ),
                }
            )

    by_event: dict[int, list[dict]] = {}
    for row in snapshots:
        by_event.setdefault(row["clearance_index"], []).append(row)

    packages = []
    for altitude_tol, heading_tol, airspeed_tol in TOLERANCE_PACKAGES:
        def within(row: dict) -> bool:
            return (
                row["altitude_error_ft"] <= altitude_tol
                and row["heading_error_deg"] <= heading_tol
                and row["airspeed_error_kt"] <= airspeed_tol
            )

        packages.append(
            {
                "altitude_ft": altitude_tol,
                "heading_deg": heading_tol,
                "airspeed_kt": airspeed_tol,
                "snapshots_within": sum(1 for row in snapshots if within(row)),
                "snapshots_total": len(snapshots),
                "events_fully_within": sum(
                    1 for rows in by_event.values() if all(within(row) for row in rows)
                ),
                "events_total": len(by_event),
            }
        )

    report = {
        "method": "independent numpy-only instrument reader, leg-safe sampling",
        "events_audited": len(by_event),
        "snapshots_audited": len(snapshots),
        "tolerance_packages": packages,
        "snapshots": snapshots,
    }
    Path(arguments.out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"audited {len(by_event)} events / {len(snapshots)} snapshots")
    print(f"\n{'alt':>6} {'hdg':>5} {'spd':>5} | {'snapshots':>18} | {'events fully within':>21}")
    for package in packages:
        marker = (
            "  <- task's own capture bands"
            if (package["altitude_ft"], package["heading_deg"], package["airspeed_kt"])
            == (100.0, 8.0, 3.0)
            else ""
        )
        print(
            f"{package['altitude_ft']:6g} {package['heading_deg']:5g} {package['airspeed_kt']:5g} | "
            f"{package['snapshots_within']:4d}/{package['snapshots_total']:<4d} "
            f"({package['snapshots_within'] / package['snapshots_total'] * 100:5.1f}%) | "
            f"{package['events_fully_within']:3d}/{package['events_total']:<3d} "
            f"({package['events_fully_within'] / package['events_total'] * 100:5.1f}%){marker}"
        )


if __name__ == "__main__":
    main()
