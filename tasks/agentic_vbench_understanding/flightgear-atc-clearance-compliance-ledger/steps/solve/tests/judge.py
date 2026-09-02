#!/usr/bin/env python3
"""Deterministically grade a FlightGear ATC clearance-to-compliance ledger.

Scoring model
-------------
Each predicted clearance is aligned to at most one ground-truth clearance under
an order-preserving one-to-one alignment that maximises awarded credit.

A pair is eligible only when it agrees on the *identity* of the clearance:
the spoken command type and an issue time inside ``ISSUE_TOLERANCE_S``. Eligible
pairs then earn graded credit across six independent field groups, so a
clearance that is correctly located and classified still earns credit when a
single downstream group (typically the instrument snapshots) is wrong.

Leg attribution follows the *aligned ground-truth* event rather than the floor
of the predicted issue time. A prediction that is early by less than the issue
tolerance but lands on the far side of a 720 s hard cut therefore still matches,
and is credited to the leg its ground-truth counterpart belongs to.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


EVENT_FIELDS = {
    "clearance_index",
    "issued_time_s",
    "command_type",
    "target_value",
    "target_unit",
    "issue_altitude_ft",
    "issue_heading_deg",
    "issue_airspeed_kt",
    "maximum_commanded_progress",
    "execution_altitude_ft",
    "execution_heading_deg",
    "execution_airspeed_kt",
    "completion_altitude_ft",
    "completion_heading_deg",
    "completion_airspeed_kt",
    "ending_altitude_ft",
    "ending_heading_deg",
    "ending_airspeed_kt",
    "execution_start_time_s",
    "completion_time_s",
    "status",
    "superseded_by_index",
    "overshoot_bucket",
}
COMMAND_TYPES = {
    "climb",
    "descend",
    "turn_left_heading",
    "turn_right_heading",
    "accelerate",
    "decelerate",
}
STATUSES = {"complied", "complied_late", "superseded", "violated", "incomplete"}
OVERSHOOT_BUCKETS = {"none", "small", "large", "not_applicable"}
UNITS = {"feet", "degrees", "knots"}

# Spoken targets are stated verbatim by ATC and stay on a tight tolerance.
TARGET_TOLERANCE = {"feet": 25.0, "degrees": 2.0, "knots": 2.0}

# Instrument snapshots are read off analog 720p15 gauges at a timestamp that is
# itself only known to EVENT_TOLERANCE_S. These reuse the task's own capture
# tolerances from instruction.md; calibration/observability/ documents why the
# former 25 ft / 2 deg / 2 kt budget was not satisfiable even by a perfect
# reader once the event-time tolerance is taken into account.
STATE_TOLERANCE = {"feet": 100.0, "degrees": 8.0, "knots": 3.0}

ISSUE_TOLERANCE_S = 2.0
EVENT_TOLERANCE_S = 4.0
# A timestamp inside this band is treated as read at the right moment and earns
# full timing credit; between here and EVENT_TOLERANCE_S it is accepted but paid
# at half, so buying snapshot slack with a loose timestamp is never free.
EVENT_PRECISE_S = 1.0
LEG_DURATION_S = 720.0
VIDEO_DURATION_S = 3600.0
MAX_PREDICTIONS = 2000

# Credit budget for one perfectly reconstructed clearance. Units are in halves
# of the original six-group budget so the timing group can be graded rather than
# all-or-nothing; the group weights themselves are unchanged.
TARGET_UNITS = 4
STATUS_UNITS = 4
STATE_UNITS = 4
TIMING_UNITS = 4
CHAIN_UNITS = 2
PROGRESS_UNITS = 2
FULL_CREDIT_UNITS = (
    TARGET_UNITS + STATUS_UNITS + STATE_UNITS + TIMING_UNITS + CHAIN_UNITS + PROGRESS_UNITS
)

# The piecewise-linear reconstruction of where an instrument was at a shifted
# timestamp is an approximation of a curved capture. This fraction of the
# implied movement is forgiven on top of the base band to absorb that model
# error -- and only that. It is not enough to excuse reporting the value at the
# true event time under a different timestamp.
INTERPOLATION_SLACK = 0.5


STATE_PREFIXES = ("issue", "execution", "completion", "ending")


def finite_number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def in_closed_set(value: Any, allowed: frozenset[str] | set[str]) -> bool:
    """Membership test that survives a JSON list or object in an enum field.

    `value in allowed` raises `TypeError: unhashable type` when an agent emits
    `"status": []`. That exception used to escape `check_event` and, because
    `accept_predictions` only caught `ValueError`, collapsed the entire
    submission to zero instead of dropping the one bad clearance.
    """
    return isinstance(value, str) and value in allowed


def check_event(event: Any, *, expected_index: int | None = None) -> None:
    """Raise ValueError when a single clearance object is not well formed."""
    if not isinstance(event, dict) or set(event) != EVENT_FIELDS:
        raise ValueError("each clearance must contain exactly the required fields")
    index = event["clearance_index"]
    issue = event["issued_time_s"]
    if not isinstance(index, int) or isinstance(index, bool) or index < 1:
        raise ValueError("clearance_index must be a positive integer")
    if index > MAX_PREDICTIONS:
        # A Python int has no width limit, so an index like 10**400 survives the
        # isinstance test and only blows up later, where `float()` on it raises
        # OverflowError outside this function's ValueError contract. No index
        # above the acceptance limit can name a real clearance anyway.
        raise ValueError(f"clearance_index must not exceed {MAX_PREDICTIONS}")
    if expected_index is not None and index != expected_index:
        raise ValueError("clearance_index values must be contiguous from 1")
    if not finite_number(issue) or not 0 <= issue < VIDEO_DURATION_S:
        raise ValueError("issued_time_s must be finite and inside the recording")
    if not in_closed_set(event["command_type"], COMMAND_TYPES):
        raise ValueError("invalid command_type")
    if not in_closed_set(event["target_unit"], UNITS):
        raise ValueError("invalid target_unit")
    if not finite_number(event["target_value"]):
        raise ValueError("target_value must be finite")
    expected_unit = (
        "degrees"
        if "heading" in event["command_type"]
        else "feet"
        if event["command_type"] in {"climb", "descend"}
        else "knots"
    )
    if event["target_unit"] != expected_unit:
        raise ValueError("target_unit does not match command_type")
    if event["target_unit"] == "degrees" and not 0 <= event["target_value"] < 360:
        raise ValueError("heading targets must be in [0, 360)")
    if event["target_unit"] != "degrees" and event["target_value"] <= 0:
        raise ValueError("altitude and airspeed targets must be positive")
    for field in (
        "issue_altitude_ft",
        "issue_heading_deg",
        "issue_airspeed_kt",
        "maximum_commanded_progress",
        "execution_altitude_ft",
        "execution_heading_deg",
        "execution_airspeed_kt",
        "completion_altitude_ft",
        "completion_heading_deg",
        "completion_airspeed_kt",
        "ending_altitude_ft",
        "ending_heading_deg",
        "ending_airspeed_kt",
        "execution_start_time_s",
        "completion_time_s",
    ):
        value = event[field]
        if field.endswith("_time_s"):
            if value is not None and (not finite_number(value) or value < issue):
                raise ValueError(f"{field} must be null or a finite time after issue")
        elif value is not None and not finite_number(value):
            raise ValueError(f"{field} must be finite")
    if not finite_number(event["maximum_commanded_progress"]):
        raise ValueError("maximum_commanded_progress must be finite")
    if event["maximum_commanded_progress"] < 0:
        raise ValueError("maximum_commanded_progress cannot be negative")
    for prefix in STATE_PREFIXES:
        values = (
            event[f"{prefix}_altitude_ft"],
            event[f"{prefix}_heading_deg"],
            event[f"{prefix}_airspeed_kt"],
        )
        if any(value is None for value in values):
            if prefix in {"issue", "ending"}:
                raise ValueError(f"{prefix} state must be numeric")
            if not all(value is None for value in values):
                raise ValueError(f"{prefix} state must be entirely null or numeric")
        else:
            if values[0] <= 0 or values[2] <= 0:
                raise ValueError(f"{prefix} altitude and airspeed must be positive")
            if not 0 <= values[1] < 360:
                raise ValueError(f"{prefix} heading must be in [0, 360)")
    for prefix, time_field in (
        ("execution", "execution_start_time_s"),
        ("completion", "completion_time_s"),
    ):
        if (event[f"{prefix}_altitude_ft"] is None) != (event[time_field] is None):
            raise ValueError(f"{prefix} state nullness must match {time_field}")
    if not in_closed_set(event["status"], STATUSES):
        raise ValueError("invalid status")
    if not in_closed_set(event["overshoot_bucket"], OVERSHOOT_BUCKETS):
        raise ValueError("invalid overshoot_bucket")
    superseded_by = event["superseded_by_index"]
    if superseded_by is not None and (
        not isinstance(superseded_by, int)
        or isinstance(superseded_by, bool)
        or superseded_by <= index
        or superseded_by > MAX_PREDICTIONS
    ):
        # The upper bound matters as much as the lower one: an unresolvable
        # index falls back to `float(target)` in `link_identity`, and an
        # unbounded int raises OverflowError there rather than ValueError here,
        # which would drop the whole submission instead of this one clearance.
        raise ValueError("superseded_by_index must refer to a later clearance")
    if event["status"] in {"complied", "complied_late"}:
        if event["execution_start_time_s"] is None or event["completion_time_s"] is None:
            raise ValueError("complied clearances require execution and completion times")
        if superseded_by is not None:
            raise ValueError("complied clearances cannot be superseded")
    elif event["completion_time_s"] is not None:
        raise ValueError("non-complied clearances cannot have completion_time_s")
    if event["status"] == "superseded" and superseded_by is None:
        raise ValueError("superseded clearances require superseded_by_index")
    if event["status"] != "superseded" and superseded_by is not None:
        raise ValueError("only superseded clearances may name a superseding index")


def validate_document(value: Any, *, allow_source: bool = False) -> dict[str, Any]:
    """Strict whole-document validation. Used for ground truth and unit tests."""
    allowed_top = {"clearances", "source"} if allow_source else {"clearances"}
    if not isinstance(value, dict) or set(value) - allowed_top or "clearances" not in value:
        raise ValueError("top-level object must contain only clearances")
    if not isinstance(value["clearances"], list):
        raise ValueError("clearances must be an array")
    previous_issue = -math.inf
    for position, event in enumerate(value["clearances"], start=1):
        check_event(event, expected_index=position)
        if float(event["issued_time_s"]) < previous_issue:
            raise ValueError("issued_time_s values must be chronological")
        previous_issue = float(event["issued_time_s"])
    indexed = {event["clearance_index"]: event for event in value["clearances"]}
    for event in value["clearances"]:
        superseded_by = event["superseded_by_index"]
        if superseded_by is None:
            continue
        later = indexed.get(superseded_by)
        if later is None:
            raise ValueError("superseded_by_index must resolve to an event")
        if dimension_of(event) != dimension_of(later):
            raise ValueError("supersession must stay on the same control dimension")
    return value


def dimension_of(event: dict[str, Any]) -> str:
    unit = event["target_unit"]
    return "heading" if unit == "degrees" else "altitude" if unit == "feet" else "airspeed"


def accept_predictions(value: Any) -> tuple[list[dict[str, Any]], int, int]:
    """Return (usable events, submitted count, dropped count).

    A single malformed clearance costs precision instead of collapsing the whole
    submission to zero, matching the partial-credit convention used by the other
    ledger tasks. Only an unreadable or wrongly shaped document scores zero.
    """
    if not isinstance(value, dict) or "clearances" not in value:
        raise ValueError("top-level object must contain clearances")
    if set(value) - {"clearances", "source"}:
        raise ValueError("top-level object must contain only clearances")
    raw = value["clearances"]
    if not isinstance(raw, list):
        raise ValueError("clearances must be an array")
    if len(raw) > MAX_PREDICTIONS:
        raise ValueError(f"clearances exceeds {MAX_PREDICTIONS} entries")
    usable: list[dict[str, Any]] = []
    for event in raw:
        try:
            check_event(event)
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            # Any way a single clearance can be malformed drops that clearance,
            # never the submission. `check_event` aims to raise only ValueError,
            # but a hostile payload should not be able to find the one field
            # where it raises something else and zero the whole answer.
            continue
        usable.append(event)
    return usable, len(raw), len(raw) - len(usable)


def load_json(path: Path, *, allow_source: bool = False) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, RecursionError, json.JSONDecodeError) as exc:
        raise ValueError(f"unreadable JSON: {exc}") from exc
    return validate_document(value, allow_source=allow_source)


def load_prediction(path: Path) -> tuple[list[dict[str, Any]], int, int]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, RecursionError, json.JSONDecodeError) as exc:
        raise ValueError(f"unreadable JSON: {exc}") from exc
    return accept_predictions(value)


def time_matches(predicted: Any, expected: Any, tolerance_s: float) -> bool:
    if predicted is None or expected is None:
        return predicted is expected
    return abs(float(predicted) - float(expected)) <= tolerance_s


def value_matches(
    predicted: Any,
    expected: Any,
    tolerance: float,
    *,
    circular: bool = False,
) -> bool:
    if predicted is None or expected is None:
        return predicted is expected
    difference = abs(float(predicted) - float(expected))
    if circular:
        difference = abs((float(predicted) - float(expected) + 180.0) % 360.0 - 180.0)
    return difference <= tolerance


SNAPSHOT_DIMENSIONS = (
    ("altitude_ft", "feet", False),
    ("heading_deg", "degrees", True),
    ("airspeed_kt", "knots", False),
)


def snapshot_rates(expected: dict[str, Any]) -> dict[str, float]:
    """Fastest per-second rate this clearance shows, per dimension.

    Estimated from the ground truth's own paired snapshots, so it needs no
    telemetry track beyond what the judge already has.
    """
    stamps = [
        ("issue", expected["issued_time_s"]),
        ("execution", expected["execution_start_time_s"]),
        ("completion", expected["completion_time_s"]),
    ]
    available = [
        (prefix, time)
        for prefix, time in stamps
        if time is not None and expected.get(f"{prefix}_altitude_ft") is not None
    ]
    rates = {suffix: 0.0 for suffix, _, _ in SNAPSHOT_DIMENSIONS}
    for (first, start), (second, end) in zip(available, available[1:]):
        span = float(end) - float(start)
        if span <= 0:
            continue
        for suffix, _, circular in SNAPSHOT_DIMENSIONS:
            before = float(expected[f"{first}_{suffix}"])
            after = float(expected[f"{second}_{suffix}"])
            difference = after - before
            if circular:
                difference = ((difference + 180.0) % 360.0) - 180.0
            rates[suffix] = max(rates[suffix], abs(difference) / span)
    return rates


def _snapshot_anchors(expected: dict[str, Any], suffix: str) -> list[tuple[float, float]]:
    """The (time, value) points this dimension is pinned to by ground truth."""
    anchors: list[tuple[float, float]] = []
    for prefix, field in (
        ("issue", "issued_time_s"),
        ("execution", "execution_start_time_s"),
        ("completion", "completion_time_s"),
    ):
        when = expected[field]
        value = expected.get(f"{prefix}_{suffix}")
        if when is not None and value is not None:
            anchors.append((float(when), float(value)))
    anchors.sort(key=lambda anchor: anchor[0])
    return anchors


def expected_value_at(
    expected: dict[str, Any], suffix: str, circular: bool, when: float
) -> float | None:
    """Where the instrument actually was at `when`, by linear interpolation.

    Ground truth pins each dimension at issue, execution and completion. Between
    those points the aircraft is either steady or under a roughly constant
    commanded rate, so a straight line between neighbouring anchors is a fair
    reconstruction; outside them it holds flat.
    """
    return interpolate(event_geometry(expected)["anchors"][suffix], circular, when)


def interpolate(
    anchors: list[tuple[float, float]], circular: bool, when: float
) -> float | None:
    if not anchors:
        return None
    if when <= anchors[0][0]:
        return anchors[0][1]
    if when >= anchors[-1][0]:
        return anchors[-1][1]
    for (start, before), (end, after) in zip(anchors, anchors[1:]):
        if not start <= when <= end:
            continue
        if end == start:
            return after
        span = after - before
        if circular:
            span = ((span + 180.0) % 360.0) - 180.0
        value = before + span * (when - start) / (end - start)
        return value % 360.0 if circular else value
    return anchors[-1][1]


_GEOMETRY_CACHE: dict[int, tuple[dict[str, Any], dict[str, Any]]] = {}


def event_geometry(expected: dict[str, Any]) -> dict[str, Any]:
    """Per-event rates and interpolation anchors, computed once.

    The shortcut search scores hundreds of candidate ledgers against the same
    ground-truth events, so recomputing this per comparison dominates runtime.
    Keyed by identity and re-validated against the object, so a mutated or
    recycled event never picks up a stale entry.
    """
    key = id(expected)
    cached = _GEOMETRY_CACHE.get(key)
    if cached is not None and cached[0] is expected:
        return cached[1]
    geometry = {
        "rates": snapshot_rates(expected),
        "anchors": {
            suffix: _snapshot_anchors(expected, suffix)
            for suffix, _, _ in SNAPSHOT_DIMENSIONS
        },
    }
    _GEOMETRY_CACHE[key] = (expected, geometry)
    return geometry


def snapshot_matches(
    predicted: dict[str, Any],
    expected: dict[str, Any],
    prefix: str,
    *,
    claimed_time: Any = None,
    expected_time: Any = None,
    rates: dict[str, float] | None = None,
) -> bool:
    """Compare one instrument snapshot against where the aircraft actually was.

    A ledger entry names an event time and the instruments *at* that time, and
    the event time is separately allowed to be off by up to the timing
    tolerance. During a manoeuvre those two allowances fight: an answer that is
    comfortably inside the timing tolerance is still reading the gauges at a
    different point on the trajectory, and is wrong through no fault of its own.
    Charging for that would make the tolerances contradict each other -- on this
    ground truth, unsatisfiably so for 47 of 65 clearances at the originally
    shipped 25 ft / 2 deg / 2 kt.

    So the answer is graded against the trajectory *at the timestamp it claims*,
    not against a band widened around the true one. Widening was the wrong
    mechanism: it let an answer keep the values from the true event time, move
    its timestamp, and be excused for an error it had already made. Shifting the
    reference point instead means a claimed timestamp only helps if the reading
    genuinely belongs to that moment -- which is a thing you can only know by
    looking at the video. Claiming the shift is also no longer free: it is paid
    for out of the timing group.
    """
    geometry = event_geometry(expected)
    rates = rates if rates is not None else geometry["rates"]
    offset = 0.0
    if claimed_time is not None and expected_time is not None:
        offset = float(claimed_time) - float(expected_time)
        offset = max(-EVENT_TOLERANCE_S, min(EVENT_TOLERANCE_S, offset))
    for suffix, unit, circular in SNAPSHOT_DIMENSIONS:
        reference = expected[f"{prefix}_{suffix}"]
        tolerance = STATE_TOLERANCE[unit]
        if offset and expected_time is not None:
            shifted = interpolate(
                geometry["anchors"][suffix], circular, float(expected_time) + offset
            )
            if shifted is not None:
                reference = shifted
                tolerance += INTERPOLATION_SLACK * rates[suffix] * abs(offset)
        if not value_matches(
            predicted[f"{prefix}_{suffix}"],
            reference,
            tolerance,
            circular=circular,
        ):
            return False
    return True


def time_credit(predicted: Any, expected: Any, units: int) -> int:
    """Graded credit for one timestamp: exact, merely inside tolerance, or wrong."""
    if predicted is None or expected is None:
        return units if predicted is expected else 0
    error = abs(float(predicted) - float(expected))
    if error <= EVENT_PRECISE_S:
        return units
    if error <= EVENT_TOLERANCE_S:
        return units // 2
    return 0


def identity_matches(predicted: dict[str, Any], expected: dict[str, Any]) -> bool:
    """The alignment gate: same spoken command, issued at the same moment."""
    return predicted["command_type"] == expected["command_type"] and time_matches(
        predicted["issued_time_s"], expected["issued_time_s"], ISSUE_TOLERANCE_S
    )


def link_identity(
    event: dict[str, Any], by_index: dict[int, dict[str, Any]] | None
) -> tuple[str, float] | None:
    """Resolve `superseded_by_index` to the clearance it points at.

    Comparing the raw integer punishes correct bookkeeping: an agent that misses
    one clearance and renumbers the rest contiguously -- exactly what
    `clearance_index` "one-based chronological index" asks for -- ends up with
    link values that no longer coincide with ground truth's, and loses chain
    credit on every downstream supersession. What the task actually asks is
    *which* later clearance took over, so that is what is compared.
    """
    target = event["superseded_by_index"]
    if target is None:
        return None
    referenced = by_index.get(target) if by_index else None
    if referenced is None:
        # Nothing to resolve against: fall back to the raw index so the pair is
        # still comparable, tagged so it can never collide with a resolved one.
        return ("#unresolved", float(target))
    return (referenced["command_type"], float(referenced["issued_time_s"]))


def links_match(
    predicted_link: tuple[str, float] | None, expected_link: tuple[str, float] | None
) -> bool:
    if predicted_link is None or expected_link is None:
        return predicted_link is expected_link
    return predicted_link[0] == expected_link[0] and abs(
        predicted_link[1] - expected_link[1]
    ) <= ISSUE_TOLERANCE_S


def credit_breakdown(
    predicted: dict[str, Any],
    expected: dict[str, Any],
    *,
    predicted_by_index: dict[int, dict[str, Any]] | None = None,
    expected_by_index: dict[int, dict[str, Any]] | None = None,
) -> dict[str, int]:
    """Per-group credit units for an identity-matched pair."""
    unit = expected["target_unit"]
    rates = event_geometry(expected)["rates"]

    target = TARGET_UNITS if value_matches(
        predicted["target_value"],
        expected["target_value"],
        TARGET_TOLERANCE[unit],
        circular=unit == "degrees",
    ) else 0

    status = STATUS_UNITS if predicted["status"] == expected["status"] else 0

    core_ok = snapshot_matches(
        predicted,
        expected,
        "issue",
        claimed_time=predicted["issued_time_s"],
        expected_time=expected["issued_time_s"],
        rates=rates,
    ) and snapshot_matches(predicted, expected, "ending", rates=rates)
    all_ok = core_ok and all(
        snapshot_matches(
            predicted,
            expected,
            prefix,
            claimed_time=predicted[field],
            expected_time=expected[field],
            rates=rates,
        )
        for prefix, field in (
            ("execution", "execution_start_time_s"),
            ("completion", "completion_time_s"),
        )
    )
    states = STATE_UNITS if all_ok else STATE_UNITS // 2 if core_ok else 0

    timing = sum(
        time_credit(predicted[field], expected[field], TIMING_UNITS // 2)
        for field in ("execution_start_time_s", "completion_time_s")
    )

    chain = CHAIN_UNITS if (
        links_match(
            link_identity(predicted, predicted_by_index),
            link_identity(expected, expected_by_index),
        )
        and predicted["overshoot_bucket"] == expected["overshoot_bucket"]
    ) else 0

    progress = PROGRESS_UNITS if value_matches(
        predicted["maximum_commanded_progress"],
        expected["maximum_commanded_progress"],
        STATE_TOLERANCE[unit],
    ) else 0

    return {
        "target": target,
        "status": status,
        "states": states,
        "timing": timing,
        "chain": chain,
        "progress": progress,
    }


def pair_credit_units(
    predicted: dict[str, Any],
    expected: dict[str, Any],
    *,
    predicted_by_index: dict[int, dict[str, Any]] | None = None,
    expected_by_index: dict[int, dict[str, Any]] | None = None,
) -> int:
    if not identity_matches(predicted, expected):
        return 0
    return sum(
        credit_breakdown(
            predicted,
            expected,
            predicted_by_index=predicted_by_index,
            expected_by_index=expected_by_index,
        ).values()
    )


def index_map(events: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """clearance_index -> event, last one wins if an agent repeats an index."""
    return {event["clearance_index"]: event for event in events}


def strict_match(predicted: dict[str, Any], expected: dict[str, Any]) -> bool:
    """True when a pair earns the full credit budget."""
    return pair_credit_units(predicted, expected) == FULL_CREDIT_UNITS


def align(
    predicted: list[dict[str, Any]], expected: list[dict[str, Any]]
) -> list[tuple[int, int, int]]:
    """Order-preserving one-to-one alignment maximising total credit units.

    Returns the chosen pairs as (predicted_position, expected_position, units).

    A pair that identity-matches is taken even when it earns nothing. Leaving
    those out used to make the reward non-monotone: an entry wrong in every
    field went unpaired and cost zero, while the same entry with one field
    *fixed* became a scored pair sitting below the transcript-only floor and
    subtracted. Fixing a field must never lower the score, so zero-unit
    identity matches are pairs too, and the tie is broken toward taking them.
    """
    predicted_by_index = index_map(predicted)
    expected_by_index = index_map(expected)

    def units_for(row: int, column: int) -> int | None:
        """Units for this pair, or None when it is not an identity match."""
        if not identity_matches(predicted[row], expected[column]):
            return None
        return sum(
            credit_breakdown(
                predicted[row],
                expected[column],
                predicted_by_index=predicted_by_index,
                expected_by_index=expected_by_index,
            ).values()
        )

    rows, columns = len(predicted), len(expected)
    # Each cell is (total units, number of pairs); units dominate, pair count
    # only breaks ties so that a worthless identity match is still recorded.
    best = [[(0, 0)] * (columns + 1) for _ in range(rows + 1)]
    scored: dict[tuple[int, int], int | None] = {}
    for i in range(1, rows + 1):
        for j in range(1, columns + 1):
            skip = max(best[i - 1][j], best[i][j - 1])
            units = units_for(i - 1, j - 1)
            scored[(i - 1, j - 1)] = units
            if units is None:
                best[i][j] = skip
                continue
            previous = best[i - 1][j - 1]
            take = (previous[0] + units, previous[1] + 1)
            best[i][j] = max(skip, take)
    pairs: list[tuple[int, int, int]] = []
    i, j = rows, columns
    while i > 0 and j > 0:
        units = scored.get((i - 1, j - 1))
        previous = best[i - 1][j - 1]
        if units is not None and best[i][j] == (previous[0] + units, previous[1] + 1):
            pairs.append((i - 1, j - 1, units))
            i -= 1
            j -= 1
        elif best[i - 1][j] >= best[i][j - 1]:
            i -= 1
        else:
            j -= 1
    pairs.reverse()
    return pairs



def leg_of(event: dict[str, Any]) -> int:
    return int(float(event["issued_time_s"]) // LEG_DURATION_S)


def _median(values: list[float]) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


DIMENSION_FIELD = {"feet": "altitude_ft", "degrees": "heading_deg", "knots": "airspeed_kt"}


def _audio_supersessions(expected: list[dict[str, Any]]) -> dict[int, int | None]:
    """Which clearances a transcript alone can tell were cut short.

    A clearance is superseded when a later command on the *same dimension*
    arrives inside the same leg before this one would have settled. Both facts
    -- the dimension and the arrival time -- are spoken aloud, so an agent with
    the transcript and nothing else can derive this without a single frame.
    """
    settle = _median(
        [
            float(event["completion_time_s"]) - float(event["issued_time_s"])
            for event in expected
            if event["completion_time_s"] is not None
        ]
    ) or 30.0
    outcome: dict[int, int | None] = {}
    for position, event in enumerate(expected):
        leg = leg_of(event)
        issue = float(event["issued_time_s"])
        outcome[position] = None
        for later_position in range(position + 1, len(expected)):
            later = expected[later_position]
            if leg_of(later) != leg:
                break
            if later["target_unit"] != event["target_unit"]:
                continue
            if float(later["issued_time_s"]) < issue + settle:
                outcome[position] = later_position + 1
            break
    return outcome


def _audio_ending_time(expected: list[dict[str, Any]], position: int) -> float:
    """When this clearance stops being the live instruction on its dimension.

    Audio alone fixes this: the transcript says when the next command on the
    same dimension arrives, and the instruction states where the leg cuts fall.
    """
    event = expected[position]
    leg_end = (leg_of(event) + 1) * LEG_DURATION_S
    for later in expected[position + 1 :]:
        if float(later["issued_time_s"]) >= leg_end:
            break
        if later["target_unit"] == event["target_unit"]:
            return float(later["issued_time_s"])
    return leg_end


def _audio_candidate(
    expected: list[dict[str, Any]],
    *,
    status: str,
    overshoot: str,
    with_execution: bool,
    settle_on_target: bool,
    use_supersession: bool,
    scale_delays: bool,
    derive_status: bool,
    constants: dict[str, Any],
    supersessions: dict[int, int | None],
) -> list[dict[str, Any]]:
    """One transcript-only strategy, played out over the whole recording.

    The strong shortcut is *chaining*: ATC names each target aloud, and an
    aircraft that complies is thereafter sitting on that value. So a
    transcript-only agent can reconstruct a believed instrument timeline for the
    whole leg -- every dimension holding its last commanded target -- and read
    any snapshot off it, with no video at all. On the two dimensions whose holds
    land exactly on the commanded value that belief is not an approximation, it
    is exact. Anything an agent earns above this ledger is what it actually read
    off the gauges.
    """
    execution_delay = constants["execution_delay"]
    completion_delay = constants["completion_delay"]

    def delays_for(unit: str, span: float) -> tuple[float, float]:
        """How long this particular clearance should take, from audio alone.

        A transcript-only agent knows the size of every commanded change -- ATC
        speaks the target and the previous target -- and a big turn plainly takes
        longer than a small one. Holding the completion delay constant across all
        clearances would be a strawman anchor, so the search also offers the
        variant that scales it with the commanded span.
        """
        if not scale_delays:
            return execution_delay, completion_delay
        rate = constants["rates"].get(unit) or 0.0
        if rate <= 0:
            return execution_delay, completion_delay
        return execution_delay, execution_delay + abs(span) / rate

    def believed_at(leg: int, when: float) -> dict[str, float]:
        """Where the transcript says the gauges are, with no video at all."""
        state = {
            "feet": constants["altitude"],
            "degrees": constants["heading"],
            "knots": constants["airspeed"],
        }
        if not settle_on_target:
            return state
        for other in expected:
            if leg_of(other) != leg:
                continue
            # Only clearances that had time to settle have moved the gauge.
            if float(other["issued_time_s"]) + completion_delay > when:
                continue
            state[other["target_unit"]] = float(other["target_value"])
        return state

    entries = []
    for position, event in enumerate(expected):
        leg = leg_of(event)
        unit = event["target_unit"]
        target = float(event["target_value"])
        issue = float(event["issued_time_s"])

        believed_issue = believed_at(leg, issue)
        commanded_span = target - believed_issue[unit]
        if unit == "degrees":
            commanded_span = (commanded_span + 180.0) % 360.0 - 180.0
        execution_offset, completion_offset = delays_for(unit, commanded_span)

        superseded = supersessions[position] if use_supersession else None
        if superseded is not None:
            entry_status = "superseded"
        elif derive_status:
            # Audio alone knows when this clearance stops being live and roughly
            # how long the commanded change takes, so it can tell a manoeuvre
            # that ran out of leg from one that had time to settle.
            entry_status = (
                "incomplete"
                if issue + completion_offset > _audio_ending_time(expected, position)
                else "complied_late"
                if execution_offset > 12.0
                else "complied"
            )
        else:
            entry_status = status
        complied = entry_status in {"complied", "complied_late"}
        executes = complied or (with_execution and entry_status != "superseded")

        at_issue = believed_issue
        at_execution = believed_at(leg, issue + execution_offset)
        at_completion = believed_at(leg, issue + completion_offset)
        at_end = believed_at(leg, _audio_ending_time(expected, position))
        if settle_on_target:
            # This clearance is the live instruction on its own dimension, so by
            # its completion the transcript says the gauge is on the target.
            at_completion[unit] = target
            at_end[unit] = target

        span = target - at_issue[unit]
        if unit == "degrees":
            span = (span + 180.0) % 360.0 - 180.0

        entries.append(
            {
                "clearance_index": position + 1,
                "issued_time_s": issue,
                "command_type": event["command_type"],
                "target_value": event["target_value"],
                "target_unit": unit,
                "issue_altitude_ft": at_issue["feet"],
                "issue_heading_deg": at_issue["degrees"],
                "issue_airspeed_kt": at_issue["knots"],
                "maximum_commanded_progress": abs(span),
                "execution_altitude_ft": at_execution["feet"] if executes else None,
                "execution_heading_deg": at_execution["degrees"] if executes else None,
                "execution_airspeed_kt": at_execution["knots"] if executes else None,
                "completion_altitude_ft": at_completion["feet"] if complied else None,
                "completion_heading_deg": at_completion["degrees"] if complied else None,
                "completion_airspeed_kt": at_completion["knots"] if complied else None,
                "ending_altitude_ft": at_end["feet"],
                "ending_heading_deg": at_end["degrees"],
                "ending_airspeed_kt": at_end["knots"],
                "execution_start_time_s": issue + execution_offset if executes else None,
                "completion_time_s": issue + completion_offset if complied else None,
                "status": entry_status,
                "superseded_by_index": superseded,
                "overshoot_bucket": overshoot,
            }
        )
    return entries


def _audio_strategies(
    expected: list[dict[str, Any]]
) -> list[list[dict[str, Any]]]:
    """Every transcript-only strategy the search considers.

    This is an enumerated family, not a proof of optimality over all possible
    audio-only reasoning. It is meant to be wide enough that the strategies a
    real transcript-only agent would actually reach are inside it: constant-gauge
    guessing, chaining each spoken target forward, supersession from the spoken
    schedule, delays that scale with the size of the commanded change, and status
    derived per clearance from whether it had time to settle.
    """
    if not expected:
        return []
    completed = [
        event
        for event in expected
        if event["completion_time_s"] is not None
        and event["execution_start_time_s"] is not None
    ]
    rates: dict[str, float] = {}
    for unit in UNITS:
        spans = []
        for event in completed:
            if event["target_unit"] != unit:
                continue
            duration = float(event["completion_time_s"]) - float(
                event["execution_start_time_s"]
            )
            if duration <= 0:
                continue
            span = float(event["target_value"]) - float(
                event[f"issue_{DIMENSION_FIELD[unit]}"]
            )
            if unit == "degrees":
                span = (span + 180.0) % 360.0 - 180.0
            spans.append(abs(span) / duration)
        if spans:
            rates[unit] = _median(spans)
    constants: dict[str, Any] = {
        "altitude": _median([event["issue_altitude_ft"] for event in expected]),
        "heading": _median([event["issue_heading_deg"] for event in expected]),
        "airspeed": _median([event["issue_airspeed_kt"] for event in expected]),
        "execution_delay": _median(
            [
                float(event["execution_start_time_s"]) - float(event["issued_time_s"])
                for event in expected
                if event["execution_start_time_s"] is not None
            ]
        ) or 5.0,
        "completion_delay": _median(
            [
                float(event["completion_time_s"]) - float(event["issued_time_s"])
                for event in expected
                if event["completion_time_s"] is not None
            ]
        ) or 30.0,
        "rates": rates,
    }
    supersessions = _audio_supersessions(expected)
    candidates = []
    for status in ("complied", "complied_late", "incomplete", "violated"):
        for overshoot in sorted(OVERSHOOT_BUCKETS):
            for with_execution in (False, True):
                if status in {"complied", "complied_late"} and with_execution:
                    continue
                for settle_on_target in (False, True):
                    for use_supersession in (False, True):
                        for scale_delays in (False, True):
                            for derive_status in (False, True):
                                candidates.append(
                                    _audio_candidate(
                                        expected,
                                        status=status,
                                        overshoot=overshoot,
                                        with_execution=with_execution,
                                        settle_on_target=settle_on_target,
                                        use_supersession=use_supersession,
                                        scale_delays=scale_delays,
                                        derive_status=derive_status,
                                        constants=constants,
                                        supersessions=supersessions,
                                    )
                                )
    return candidates


_CEILING_CACHE: dict[str, list[int]] = {}


def shortcut_ceiling(expected: list[dict[str, Any]]) -> list[int]:
    """Per-event best over the enumerated transcript-only strategy family.

    The floor has to be an envelope rather than one fixed ledger. Per-event
    credit compares against this floor, so a noisy answer that merely ties a
    single reference ledger on average would otherwise still score above it --
    it keeps its wins and has its losses forgiven. Taking the best
    transcript-only result on each event separately prices that away: an agent
    is credited only where it beat everything the family could have said about
    *that* clearance.

    This is a maximum over :func:`_audio_strategies`, not a proof that no
    audio-only reasoning can do better. Widening the family is the maintenance
    burden that comes with the anchor.

    The result depends only on the ground truth, and :func:`score` needs it on
    every call, so it is memoised on a canonical digest of ``expected``. A single
    grading run computes it once; the calibration sweeps, which score tens of
    thousands of candidate ledgers against one fixed ground truth, would
    otherwise spend all their time rebuilding the same envelope.
    """
    key = hashlib.sha256(
        json.dumps(expected, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    cached = _CEILING_CACHE.get(key)
    if cached is not None:
        return list(cached)
    ceiling = [0] * len(expected)
    for candidate in _audio_strategies(expected):
        for position, (entry, event) in enumerate(zip(candidate, expected)):
            units = pair_credit_units(entry, event)
            if units > ceiling[position]:
                ceiling[position] = units
    _CEILING_CACHE[key] = list(ceiling)
    return ceiling


def shortcut_reference(expected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strongest single ledger reachable from perfect audio with no video at all.

    Command type, issue time and spoken target are copied verbatim because ATC
    states them aloud. Every visually determined field is filled by the best
    transcript-only strategy this search can find: chain each spoken target
    forward as the believed instrument state, derive supersession from the
    clearance sequence, derive commanded progress from the chained gap, and pick
    the best constant for what remains. This is the task's ``M_broken`` anchor in
    the spirit of docs/VERIFIER_DESIGN.md: the score is an affine map that sends
    this transcript-only ledger to 0 and the oracle to 1, so credit measures what
    an agent recovered *from the instruments*. That document scopes itself to the
    repair tasks and clips its normalised improvement to [0, 1]; this scorer
    clips to [-1, 1] instead, deliberately, so that an answer worse than the
    anchor subtracts rather than rounding up to par.

    Making this anchor strong is the whole point. A weak anchor -- a single
    global constant for every gauge -- leaves the chaining shortcut unpriced, and
    a real audio-only agent then scores well above zero on a task that is
    supposed to require video. Scoring uses the per-event envelope over the same
    strategy family (:func:`shortcut_ceiling`); this function returns the single
    best ledger, which is what the anti-shortcut tests submit.
    """
    best: list[dict[str, Any]] = []
    best_units = -1
    for candidate in _audio_strategies(expected):
        # Candidate and ground truth share issue times and order, so the identity
        # pairing is already the optimal alignment; scoring it directly keeps the
        # search cheap.
        units = sum(
            pair_credit_units(entry, event)
            for entry, event in zip(candidate, expected)
        )
        if units > best_units:
            best_units, best = units, candidate
    return best


def score(
    prediction: dict[str, Any] | list[dict[str, Any]],
    ground_truth: dict[str, Any],
    *,
    submitted: int | None = None,
    dropped: int = 0,
    reason: str = "ok",
) -> dict[str, Any]:
    predicted = (
        prediction["clearances"] if isinstance(prediction, dict) else list(prediction)
    )
    expected = ground_truth["clearances"]
    if submitted is None:
        submitted = len(predicted)

    pairs = align(predicted, expected)
    credit_units = sum(units for _, _, units in pairs)
    full_matches = sum(1 for _, _, units in pairs if units == FULL_CREDIT_UNITS)
    partial_matches = len(pairs) - full_matches

    # Chance floor: the units a transcript-only ledger already earns on each
    # ground-truth event without ever reading an instrument. Per-event credit is
    # rescaled so that floor maps to 0 and the oracle maps to 1, which is the
    # normalise-improvement convention in docs/VERIFIER_DESIGN.md. Without it a
    # constant "everything complied" guess collects the closed-vocabulary and
    # spoken-target units for free and the reward stops measuring the video.
    chance_units = shortcut_ceiling(expected)
    chance_total = sum(chance_units)

    # An event the transcript-only ledger already answers perfectly has no
    # headroom left: nothing an agent does with the video can show up there. Such
    # events are dropped from both sides of the F1 rather than scored, so they
    # neither inflate a shortcut answer nor penalise a real one.
    gradable = [
        position
        for position in range(len(expected))
        if FULL_CREDIT_UNITS - chance_units[position] > 0
    ]
    gradable_set = set(gradable)

    def gain_of(expected_position: int, units: int) -> float:
        """Net credit above what audio alone could have said about this event.

        Deliberately allowed to go negative, bounded symmetrically at -1. If a
        shortfall scored zero rather than negative, an answer that merely ties
        the transcript-only ceiling *on average* would still score well above it:
        its lucky events would count and its unlucky ones would be clipped away.
        Letting the shortfall carry means guessing nets out at zero, which is
        what an anti-shortcut anchor has to do.
        """
        floor = chance_units[expected_position]
        headroom = FULL_CREDIT_UNITS - floor
        return max(-1.0, min(1.0, (units - floor) / headroom))

    gains = {
        expected_position: gain_of(expected_position, units)
        for _, expected_position, units in pairs
        if expected_position in gradable_set
    }
    credit = max(0.0, sum(gains.values()))

    # Predictions that landed on an ungraded event are not false positives -- the
    # event simply is not being scored -- so they cost nothing. Everything else
    # that matched no ground-truth clearance at all is padding and is charged.
    #
    # The denominator is deliberately *not* an F1 precision term over every
    # submitted entry. Under that form a clearance whose gain was positive but
    # below half the current reward still dragged the score down, so the best
    # move was to answer fewer clearances than you could -- the opposite of what
    # the instruction asks for. Charging only unmatched padding means finding a
    # clearance and reading it better than the transcript can always helps.
    spurious = max(0, submitted - len(pairs))
    chargeable = len(gradable) + spurious
    reward = credit / chargeable if chargeable else 0.0
    precision = credit / max(1, len(pairs)) if pairs else 0.0
    recall = credit / len(gradable) if gradable else 0.0

    # Per-leg gain is reported as a diagnostic only. It is deliberately *not*
    # folded into the reward: the legs hold 13/12/12/11/12 gradable clearances,
    # so a mean of per-leg means would quietly reweight individual clearances by
    # which leg they fell in without adding any signal about the video.
    # The old scorer's leg bug is gone by construction -- nothing buckets by
    # predicted issued_time_s // 720 any more. Legs are attributed through the
    # aligned ground-truth event, so a clearance guessed 1.5 s early across a cut
    # still matches and still lands in the leg it was actually issued in.
    leg_expected: dict[int, int] = {}
    for position in gradable:
        leg = leg_of(expected[position])
        leg_expected[leg] = leg_expected.get(leg, 0) + 1
    leg_gain: dict[int, float] = {leg: 0.0 for leg in leg_expected}
    for expected_position, gain in gains.items():
        leg_gain[leg_of(expected[expected_position])] += gain
    leg_fractions = {
        leg: max(0.0, leg_gain[leg]) / count for leg, count in leg_expected.items()
    }
    leg_score = (
        sum(leg_fractions.values()) / len(leg_fractions) if leg_fractions else 0.0
    )
    complete_legs = sum(1 for value in leg_fractions.values() if value >= 1.0)

    group_totals = {"target": 0, "status": 0, "states": 0, "timing": 0, "chain": 0, "progress": 0}
    predicted_by_index = index_map(predicted)
    expected_by_index = index_map(expected)
    for predicted_position, expected_position, units in pairs:
        if not units:
            continue
        for key, value in credit_breakdown(
            predicted[predicted_position],
            expected[expected_position],
            predicted_by_index=predicted_by_index,
            expected_by_index=expected_by_index,
        ).items():
            group_totals[key] += value
    group_maxima = {
        "target": TARGET_UNITS,
        "status": STATUS_UNITS,
        "states": STATE_UNITS,
        "timing": TIMING_UNITS,
        "chain": CHAIN_UNITS,
        "progress": PROGRESS_UNITS,
    }

    return {
        "reward": round(reward, 4),
        "details": {
            "reason": reason,
            "graded_clearance_credit": round(reward, 4),
            "leg_credit_accuracy": round(leg_score, 4),
            "credited_clearances": round(credit, 4),
            "raw_credit_units": credit_units,
            "chance_credit_units": chance_total,
            "max_credit_units": FULL_CREDIT_UNITS * len(expected),
            "gradable_clearances": len(gradable),
            "full_credit_matches": full_matches,
            "partial_credit_matches": partial_matches,
            "identity_matches": len(pairs),
            "spurious_clearances": spurious,
            "chargeable_clearances": chargeable,
            "complete_legs": complete_legs,
            "n_leg_chains": len(leg_expected),
            "leg_credit_fractions": {
                str(leg): round(value, 4) for leg, value in sorted(leg_fractions.items())
            },
            "group_credit": {
                key: {
                    "earned": group_totals[key],
                    "available": group_maxima[key] * len(expected),
                }
                for key in group_totals
            },
            "n_predicted": submitted,
            "n_schema_valid": len(predicted),
            "n_dropped_invalid": dropped,
            "n_ground_truth": len(expected),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "issued_time_tolerance_s": ISSUE_TOLERANCE_S,
            "event_time_tolerance_s": EVENT_TOLERANCE_S,
            "target_tolerance": TARGET_TOLERANCE,
            "state_tolerance": STATE_TOLERANCE,
            "credit_policy": {
                "identity_gate": ["command_type", f"issued_time_s +/-{ISSUE_TOLERANCE_S}s"],
                "full_credit_units": FULL_CREDIT_UNITS,
                "target_value": TARGET_UNITS,
                "status": STATUS_UNITS,
                "state_snapshots": (
                    f"{STATE_UNITS} all four, {STATE_UNITS // 2} issue+ending only; "
                    "each snapshot is compared against the trajectory at the "
                    "timestamp the answer itself claims"
                ),
                "event_times": (
                    f"{TIMING_UNITS // 2} per timestamp within {EVENT_PRECISE_S}s, "
                    f"half that within {EVENT_TOLERANCE_S}s, else 0"
                ),
                "supersession_and_overshoot": (
                    f"{CHAIN_UNITS}; superseded_by_index is resolved to the "
                    "clearance it names and compared by identity, not by integer"
                ),
                "maximum_commanded_progress": PROGRESS_UNITS,
                "chance_floor": (
                    "per-event credit is rescaled to (units - transcript_only_units) "
                    "/ (full - transcript_only_units), clipped to [-1, 1]; events the "
                    "transcript-only ledger already answers in full carry no video "
                    "signal and are not scored at all"
                ),
                "reward": (
                    "summed chance-corrected credit over the gradable clearances, "
                    "divided by the gradable count plus any submitted clearance "
                    "that matched no ground-truth clearance"
                ),
                "leg_assignment": (
                    "diagnostic only; legs follow the aligned ground-truth event, "
                    "never floor(predicted issued_time_s / 720)"
                ),
            },
        },
    }


def empty_result(reason: str, n_ground_truth: int = 0) -> dict[str, Any]:
    """A zero result carrying the same keys `score` emits, so consumers of the
    reward JSON do not have to special-case the rejected path."""
    return {
        "reward": 0.0,
        "details": {
            "reason": reason,
            "graded_clearance_credit": 0.0,
            "leg_credit_accuracy": 0.0,
            "credited_clearances": 0.0,
            "raw_credit_units": 0,
            "chance_credit_units": 0,
            "max_credit_units": FULL_CREDIT_UNITS * n_ground_truth,
            "gradable_clearances": 0,
            "full_credit_matches": 0,
            "partial_credit_matches": 0,
            "identity_matches": 0,
            "spurious_clearances": 0,
            "chargeable_clearances": 0,
            "complete_legs": 0,
            "n_leg_chains": 0,
            "leg_credit_fractions": {},
            "group_credit": {},
            "n_predicted": 0,
            "n_schema_valid": 0,
            "n_dropped_invalid": 0,
            "n_ground_truth": n_ground_truth,
            "precision": 0.0,
            "recall": 0.0,
            "issued_time_tolerance_s": ISSUE_TOLERANCE_S,
            "event_time_tolerance_s": EVENT_TOLERANCE_S,
            "target_tolerance": TARGET_TOLERANCE,
            "state_tolerance": STATE_TOLERANCE,
            "credit_policy": {},
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--ground-truth", required=True, type=Path)
    parser.add_argument("--reward-json", required=True, type=Path)
    parser.add_argument("--reward-txt", required=True, type=Path)
    parser.add_argument("--details-json", type=Path)
    args = parser.parse_args()

    try:
        ground_truth = load_json(args.ground_truth, allow_source=True)
    except (OverflowError, RecursionError, TypeError, ValueError) as exc:
        raise RuntimeError(f"invalid verifier ground truth: {exc}") from exc

    try:
        usable, submitted, dropped = load_prediction(args.solution)
        result = score(
            usable,
            ground_truth,
            submitted=submitted,
            dropped=dropped,
            reason="ok" if not dropped else f"dropped {dropped} malformed clearances",
        )
    except (OverflowError, RecursionError, TypeError, ValueError) as exc:
        result = empty_result(str(exc), len(ground_truth["clearances"]))

    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    args.reward_txt.write_text(f"{result['reward']}\n", encoding="utf-8")
    if args.details_json:
        args.details_json.parent.mkdir(parents=True, exist_ok=True)
        args.details_json.write_text(
            json.dumps(result["details"], indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
