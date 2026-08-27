#!/usr/bin/env python3
"""Are the state tolerances internally consistent with the time tolerances?

This check needs nothing but ``ground_truth.json`` -- no media, no instrument
reader, no model. It therefore cannot be argued away as a weakness of one
particular vision pipeline.

The ledger asks for an instrument snapshot *at* a named event, and separately
allows the event's timestamp to be off by up to ``EVENT_TOLERANCE_S``. But the
aircraft is manoeuvring at exactly those moments -- that is what makes them
events. So an answer that is fully inside the timing tolerance is still sampling
the instrument somewhere else on the trajectory, and the state error that forces
is ``|rate| * tolerance``.

Rates are estimated from the ground truth's own paired snapshots (issue ->
execution -> completion), so the arithmetic is entirely self-contained: if
``|rate| * tolerance`` exceeds the state budget, the two tolerances contradict
each other, and a reader can only satisfy both by being luckier about the
timestamp than the timing tolerance requires it to be.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GROUND_TRUTH = ROOT / "steps" / "solve" / "tests" / "ground_truth.json"

EVENT_TOLERANCE_S = 4.0
STRICT_STATE_TOLERANCE = {"altitude": 25.0, "heading": 2.0, "airspeed": 2.0}
RELAXED_STATE_TOLERANCE = {"altitude": 100.0, "heading": 8.0, "airspeed": 3.0}

DIMENSIONS = (
    ("altitude", "altitude_ft", False),
    ("heading", "heading_deg", True),
    ("airspeed", "airspeed_kt", False),
)


def signed_delta(later: float, earlier: float, circular: bool) -> float:
    difference = later - earlier
    if circular:
        difference = ((difference + 180.0) % 360.0) - 180.0
    return difference


def segment_rates(event: dict) -> dict[str, float]:
    """Fastest |rate| per second seen on each dimension across this clearance."""
    stamps = [
        ("issue", event["issued_time_s"]),
        ("execution", event["execution_start_time_s"]),
        ("completion", event["completion_time_s"]),
    ]
    available = [
        (prefix, time)
        for prefix, time in stamps
        if time is not None and event.get(f"{prefix}_{DIMENSIONS[0][1]}") is not None
    ]
    rates = {name: 0.0 for name, _, _ in DIMENSIONS}
    for (first, start), (second, end) in zip(available, available[1:]):
        span = float(end) - float(start)
        if span <= 0:
            continue
        for name, suffix, circular in DIMENSIONS:
            delta = signed_delta(
                float(event[f"{second}_{suffix}"]), float(event[f"{first}_{suffix}"]), circular
            )
            rates[name] = max(rates[name], abs(delta) / span)
    return rates


def coherent_shift(event: dict, rates: dict[str, float], delay: float) -> dict:
    """An answer that is late by ``delay`` and honestly reports what it then saw.

    This is the shape of a good-faith error: the agent picked an event moment a
    few seconds off, and read the gauges at *its own* moment. Every field is
    self-consistent; only the anchor slid.
    """
    shifted = dict(event)
    for prefix, field in (
        ("issue", "issued_time_s"),
        ("execution", "execution_start_time_s"),
        ("completion", "completion_time_s"),
    ):
        stamp = event[field]
        step = min(delay, EVENT_TOLERANCE_S if prefix != "issue" else 2.0)
        if stamp is not None:
            shifted[field] = float(stamp) + step
        for name, suffix, circular in DIMENSIONS:
            key = f"{prefix}_{suffix}"
            if event.get(key) is None:
                continue
            moved = float(event[key]) + rates[name] * step
            shifted[key] = moved % 360.0 if circular else moved
    return shifted


def verify_shipped_judge(events: list[dict]) -> None:
    """The shipped judge must accept a coherently shifted answer. Anything else
    means the state and time tolerances still contradict each other."""
    import importlib.util

    location = ROOT / "steps" / "solve" / "tests" / "judge.py"
    spec = importlib.util.spec_from_file_location("judge", location)
    judge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(judge)

    print("\n=== verification: does the shipped judge accept a coherent shift? ===")
    for delay in (1.0, 2.0, 4.0):
        shifted = [
            coherent_shift(event, segment_rates(event), delay) for event in events
        ]
        result = judge.score({"clearances": shifted}, {"clearances": events})
        credit = result["details"]["group_credit"]["states"]
        print(
            f"  every event shifted +{delay:.0f}s, gauges read at the shifted moment: "
            f"state credit {credit['earned']}/{credit['available']}, "
            f"reward {result['reward']:.4f}"
        )


def main() -> None:
    events = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))["clearances"]
    measured = [(event, segment_rates(event)) for event in events]
    manoeuvring = [
        (event, rates)
        for event, rates in measured
        if event["execution_start_time_s"] is not None
    ]

    for label, tolerance in (
        ("strict (shipped in the first revision)", STRICT_STATE_TOLERANCE),
        ("relaxed (this PR), applied as a flat budget", RELAXED_STATE_TOLERANCE),
    ):
        print(f"\n=== state tolerance: {label} ===")
        print(
            f"{'dimension':>10} {'budget':>8} {'median forced':>14} "
            f"{'worst forced':>13} {'events over budget':>20}"
        )
        for name, _, _ in DIMENSIONS:
            forced = sorted(rates[name] * EVENT_TOLERANCE_S for _, rates in manoeuvring)
            budget = tolerance[name]
            over = sum(1 for value in forced if value > budget)
            median = forced[len(forced) // 2] if forced else 0.0
            print(
                f"{name:>10} {budget:8.1f} {median:14.2f} {max(forced, default=0.0):13.2f} "
                f"{over:>13d}/{len(forced):<6d}"
            )
        contradictory = [
            event["clearance_index"]
            for event, rates in manoeuvring
            if any(rates[name] * EVENT_TOLERANCE_S > tolerance[name] for name, _, _ in DIMENSIONS)
        ]
        print(
            f"  clearances where timing slack alone breaks the state budget: "
            f"{len(contradictory)}/{len(events)}"
        )
        if contradictory:
            print(f"  indices: {contradictory}")

    print(
        "\nA flat budget cannot fix this: heading swings up to "
        f"{max(rates['heading'] for _, rates in manoeuvring) * EVENT_TOLERANCE_S:.1f} deg "
        "inside the timing tolerance, so a flat budget wide enough to be\n"
        "consistent would be too wide to mean anything on a turn. The shipped "
        "judge instead compares each snapshot against the trajectory\n"
        "interpolated to the timestamp the answer itself reports, so a coherent "
        "shift keeps its state credit while paying for the shift out\n"
        "of the timing group -- which is why reward falls below 1.0 in the "
        "check that follows even though state credit stays full."
    )
    verify_shipped_judge(events)


if __name__ == "__main__":
    main()

