#!/usr/bin/env python3
"""Adversarial probes against the shipped judge, beyond the required ablations.

Every probe here is constructed *without video*: it starts from the transcript
-only reference ledger the judge already builds (`judge.shortcut_reference`) or
from a degenerate submission, and perturbs it. Nothing reads a frame.

    python3 calibration/shortcut_probe.py            # summary
    python3 calibration/shortcut_probe.py --verbose  # every probe's reward

The point is not that these are the only shortcuts, but that the obvious ones --
guessing constants, chaining spoken targets, padding, truncating, duplicating a
good entry, and sweeping systematic offsets -- all land at 0. If any probe here
ever returns above `AGENT_MAX = 0.10`, the metric is broken and this script says
so with a non-zero exit status.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import random
from pathlib import Path
from typing import Any

TASK = Path(__file__).resolve().parent.parent
JUDGE_PATH = TASK / "steps/solve/tests/judge.py"
GROUND_TRUTH = TASK / "steps/solve/tests/ground_truth.json"

AGENT_MAX = 0.10

SPEC = importlib.util.spec_from_file_location("flightgear_judge", JUDGE_PATH)
assert SPEC and SPEC.loader
judge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(judge)

STATE_FIELDS = {
    "ft": ("issue_altitude_ft", "execution_altitude_ft", "completion_altitude_ft",
           "ending_altitude_ft"),
    "deg": ("issue_heading_deg", "execution_heading_deg", "completion_heading_deg",
            "ending_heading_deg"),
    "kt": ("issue_airspeed_kt", "execution_airspeed_kt", "completion_airspeed_kt",
           "ending_airspeed_kt"),
}
TIME_FIELDS = ("issued_time_s", "execution_start_time_s", "completion_time_s")


def truth() -> dict[str, Any]:
    return json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))


def reward(clearances: list[dict[str, Any]]) -> float:
    document = {"clearances": clearances}
    try:
        usable, submitted, dropped = judge.accept_predictions(document)
    except (ValueError, TypeError):
        return 0.0
    return judge.score(usable, truth(), submitted=submitted, dropped=dropped)["reward"]


def grid(base: list[dict[str, Any]]) -> list[tuple[str, float]]:
    """6 x 6 x 6 x 8 x 4 x 4 = 27,648 systematic-offset probes."""
    altitudes = (-100.0, -50.0, -27.0, 0.0, 50.0, 100.0)
    headings = (-8.0, -4.0, -1.0, 0.0, 4.0, 8.0)
    airspeeds = (-3.0, -1.5, -0.5, 0.0, 1.5, 3.0)
    seconds = (-4.0, -2.0, -1.0, -0.5, 0.0, 0.5, 2.0, 4.0)
    progresses = ("keep", "zero", "target", "inflate")
    statuses = ("keep", "complied", "complied_late", "violated")
    results: list[tuple[str, float]] = []
    for altitude in altitudes:
        for heading in headings:
            for airspeed in airspeeds:
                for second in seconds:
                    for progress in progresses:
                        entries = shift(
                            base,
                            altitude=altitude,
                            heading=heading,
                            airspeed=airspeed,
                            seconds=second,
                            progress=progress,
                        )
                        for status in statuses:
                            candidate = entries
                            if status != "keep":
                                candidate = copy.deepcopy(entries)
                                for entry in candidate:
                                    entry["status"] = status
                            label = (
                                f"grid alt{altitude:+g} hdg{heading:+g} "
                                f"spd{airspeed:+g} t{second:+g} "
                                f"prog={progress} status={status}"
                            )
                            results.append((label, reward(candidate)))
    return results


def shift(
    base: list[dict[str, Any]],
    *,
    altitude: float,
    heading: float,
    airspeed: float,
    seconds: float,
    progress: str,
) -> list[dict[str, Any]]:
    out = copy.deepcopy(base)
    for entry in out:
        for field in STATE_FIELDS["ft"]:
            if entry.get(field) is not None:
                entry[field] = round(float(entry[field]) + altitude, 2)
        for field in STATE_FIELDS["deg"]:
            if entry.get(field) is not None:
                entry[field] = round((float(entry[field]) + heading) % 360.0, 2)
        for field in STATE_FIELDS["kt"]:
            if entry.get(field) is not None:
                entry[field] = round(float(entry[field]) + airspeed, 2)
        for field in TIME_FIELDS:
            if entry.get(field) is not None:
                entry[field] = round(max(0.0, float(entry[field]) + seconds), 1)
        current = entry.get("maximum_commanded_progress")
        if current is None:
            continue
        if progress == "zero":
            entry["maximum_commanded_progress"] = 0.0
        elif progress == "target":
            entry["maximum_commanded_progress"] = abs(float(entry["target_value"]))
        elif progress == "inflate":
            entry["maximum_commanded_progress"] = round(float(current) * 1.25, 2)
    return out


def jitter(base: list[dict[str, Any]], seeds: int = 120) -> list[tuple[str, float]]:
    """12 noise magnitudes x 120 seeds = 1,440 randomized ledgers."""
    magnitudes = (5.0, 10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 75.0, 90.0, 100.0,
                  125.0, 150.0)
    results: list[tuple[str, float]] = []
    for magnitude in magnitudes:
        for seed in range(seeds):
            rng = random.Random((int(magnitude) << 16) ^ seed)
            entries = copy.deepcopy(base)
            for entry in entries:
                for field in STATE_FIELDS["ft"]:
                    if entry.get(field) is not None:
                        entry[field] = round(
                            float(entry[field]) + rng.uniform(-magnitude, magnitude), 2
                        )
                for field in STATE_FIELDS["deg"]:
                    if entry.get(field) is not None:
                        span = magnitude * 8.0 / 100.0
                        entry[field] = round(
                            (float(entry[field]) + rng.uniform(-span, span)) % 360.0, 2
                        )
                for field in STATE_FIELDS["kt"]:
                    if entry.get(field) is not None:
                        span = magnitude * 3.0 / 100.0
                        entry[field] = round(
                            float(entry[field]) + rng.uniform(-span, span), 2
                        )
            results.append((f"jitter +/-{magnitude:g} seed {seed}", reward(entries)))
    return results


def structural(base: list[dict[str, Any]]) -> list[tuple[str, float]]:
    """Padding, truncation, duplication, and all-null degenerate submissions."""
    expected = truth()["clearances"]
    ceiling = judge.shortcut_ceiling(expected)
    results: list[tuple[str, float]] = [
        ("audio reference verbatim", reward(base)),
        ("empty submission", reward([])),
    ]

    nulled = copy.deepcopy(base)
    for entry in nulled:
        for field in ("execution_altitude_ft", "execution_heading_deg",
                      "execution_airspeed_kt", "completion_altitude_ft",
                      "completion_heading_deg", "completion_airspeed_kt",
                      "execution_start_time_s", "completion_time_s",
                      "superseded_by_index"):
            entry[field] = None
    results.append(("every optional field null", reward(nulled)))

    for size in (1, 3, 5, 10, 20, 40):
        results.append((f"truncated to {size}", reward(copy.deepcopy(base[:size]))))

    # Pad to the acceptance limit with copies of the strongest single entry.
    strongest = max(
        range(len(base)),
        key=lambda position: judge.pair_credit_units(base[position], expected[position]),
    )
    padded = copy.deepcopy(base)
    filler = copy.deepcopy(base[strongest])
    next_index = max(entry["clearance_index"] for entry in padded) + 1
    while len(padded) < judge.MAX_PREDICTIONS:
        clone = copy.deepcopy(filler)
        clone["clearance_index"] = next_index
        clone["superseded_by_index"] = None
        next_index += 1
        padded.append(clone)
    results.append((f"padded to {judge.MAX_PREDICTIONS}", reward(padded)))

    duplicated = []
    for position in range(len(expected)):
        clone = copy.deepcopy(base[strongest])
        clone["clearance_index"] = position
        clone["superseded_by_index"] = None
        duplicated.append(clone)
    results.append((
        f"strongest entry (#{strongest}, {ceiling[strongest]} ceiling units) "
        f"duplicated {len(expected)}x",
        reward(duplicated),
    ))

    # Keep only the entries whose transcript ceiling already leaves no headroom:
    # the "answer only what is free" strategy.
    free = [
        copy.deepcopy(entry)
        for position, entry in enumerate(base)
        if judge.FULL_CREDIT_UNITS - ceiling[position] <= 0
    ]
    results.append((f"only the {len(free)} zero-headroom clearances", reward(free)))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true",
                        help="print every probe rather than the worst case")
    parser.add_argument("--seeds", type=int, default=120,
                        help="random seeds per jitter magnitude (default 120)")
    options = parser.parse_args()

    expected = truth()["clearances"]
    base = judge.shortcut_reference(expected)

    families = [
        ("structural", structural(base)),
        ("systematic offset grid", grid(base)),
        ("randomized jitter", jitter(base, seeds=options.seeds)),
    ]

    worst = 0.0
    print(f"probes run against {len(expected)} expected clearances\n")
    print(f"{'family':<24} {'probes':>7} {'max reward':>11}  worst-case probe")
    for name, results in families:
        label, value = max(results, key=lambda item: item[1])
        worst = max(worst, value)
        print(f"{name:<24} {len(results):>7} {value:>11.4f}  {label}")
        if options.verbose:
            for probe, score in sorted(results, key=lambda item: -item[1]):
                print(f"    {score:>7.4f}  {probe}")

    total = sum(len(results) for _, results in families)
    print(f"\n{total} probes, highest reward {worst:.4f}, "
          f"gate AGENT_MAX = {AGENT_MAX}")
    if worst > AGENT_MAX:
        print("FAIL: a video-free probe cleared the difficulty gate")
        raise SystemExit(1)
    print("PASS: no video-free probe clears the difficulty gate")


if __name__ == "__main__":
    main()
