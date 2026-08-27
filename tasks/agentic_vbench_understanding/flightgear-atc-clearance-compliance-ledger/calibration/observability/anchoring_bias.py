#!/usr/bin/env python3
"""Does anchoring on the spoken target work equally well on all three instruments?

Like ``tolerance_consistency.py`` this needs nothing but ``ground_truth.json``
-- no media, no instrument reader, no model.

The cheapest audio-only strategy is to assume the aircraft ends up exactly where
it was told to go, and to report the spoken target as the ending instrument
value. This script measures how well that works per dimension.

Only clearances that actually reached a stable hold are counted, i.e. those with
``status`` in {``complied``, ``complied_late``}. A superseded, violated, or
incomplete clearance never settles on its target, so including it would measure
the interruption rather than the anchoring bias.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GROUND_TRUTH = ROOT / "steps" / "solve" / "tests" / "ground_truth.json"

HELD = {"complied", "complied_late"}
DIMENSIONS = (
    ("altitude", "feet", "ending_altitude_ft", "ft"),
    ("heading", "degrees", "ending_heading_deg", "deg"),
    ("airspeed", "knots", "ending_airspeed_kt", "kt"),
)


def circular_error(actual: float, target: float) -> float:
    return (actual - target + 180.0) % 360.0 - 180.0


def main() -> None:
    events = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))["clearances"]
    held = [event for event in events if event["status"] in HELD]
    print(
        f"{len(held)}/{len(events)} clearances reached a stable hold "
        f"(status in {sorted(HELD)}); the rest never settle on their target.\n"
    )

    print(f"{'dimension':>10} {'n':>4} {'mean':>9} {'sd':>7} {'min':>9} {'max':>9}")
    for name, unit, field, suffix in DIMENSIONS:
        errors = [
            circular_error(event[field], event["target_value"])
            if unit == "degrees"
            else event[field] - event["target_value"]
            for event in held
            if event["target_unit"] == unit
        ]
        if not errors:
            continue
        mean = sum(errors) / len(errors)
        variance = sum((value - mean) ** 2 for value in errors) / len(errors)
        print(
            f"{name:>10} {len(errors):>4} {mean:>9.2f} {variance ** 0.5:>7.2f} "
            f"{min(errors):>9.2f} {max(errors):>9.2f}   ({suffix})"
        )

    print(
        "\nHeading and airspeed holds land exactly on the commanded value, so "
        "anchoring on the\nspoken target is free credit there. Altitude carries "
        "a systematic offset that nothing in\nthe video reveals -- against the "
        "25 ft budget shipped in the first revision, an agent doing\nthe right "
        "thing on two instruments was irreducibly outside the budget on the third."
    )

    completions = [
        event["completion_altitude_ft"] - event["target_value"]
        for event in held
        if event["target_unit"] == "feet"
        and event["completion_altitude_ft"] is not None
    ]
    if completions:
        print(
            f"\ncompletion_altitude_ft - target, n={len(completions)}: "
            f"min {min(completions):.2f} ft, max {max(completions):.2f} ft -- "
            "completion is defined by\nthe 100 ft capture band, so ground truth "
            "sits just inside it, and landing within 25 ft of that\ndemanded "
            "sub-second precision on a completion time that was itself allowed "
            "4 s of slack."
        )


if __name__ == "__main__":
    main()
