from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


JUDGE_PATH = Path(__file__).with_name("judge.py")
SPEC = importlib.util.spec_from_file_location("flightgear_judge", JUDGE_PATH)
assert SPEC and SPEC.loader
judge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(judge)


def clearance(index: int = 1) -> dict[str, object]:
    return {
        "clearance_index": index,
        "issued_time_s": 10.0,
        "command_type": "climb",
        "target_value": 4000,
        "target_unit": "feet",
        "issue_altitude_ft": 3600,
        "issue_heading_deg": 180,
        "issue_airspeed_kt": 100,
        "maximum_commanded_progress": 400,
        "execution_altitude_ft": 3620,
        "execution_heading_deg": 180,
        "execution_airspeed_kt": 100,
        "completion_altitude_ft": 4000,
        "completion_heading_deg": 180,
        "completion_airspeed_kt": 100,
        "ending_altitude_ft": 4000,
        "ending_heading_deg": 180,
        "ending_airspeed_kt": 100,
        "execution_start_time_s": 12.0,
        "completion_time_s": 35.0,
        "status": "complied",
        "superseded_by_index": None,
        "overshoot_bucket": "none",
    }


# A one-event ground truth makes the chance anchor degenerate: the best constant
# predictor is the single event, so it *is* the oracle and there is no headroom
# to grade. Scoring behaviour is therefore exercised against a small ledger with
# real variety, spanning a leg cut at 720 s.
LEDGER_SHAPE = (
    # issue, command, unit, target, status, overshoot, climb_rate, turn_rate
    (100.0, "climb", "feet", 5000, "complied", "none", 20.0, 0.0),
    (240.0, "turn_right_heading", "degrees", 90, "complied", "small", 0.0, 3.0),
    (380.0, "decelerate", "knots", 95, "incomplete", "not_applicable", 0.0, 0.0),
    (500.0, "descend", "feet", 4200, "complied_late", "large", -15.0, 0.0),
    (640.0, "turn_left_heading", "degrees", 20, "violated", "none", 0.0, 2.5),
    (718.5, "accelerate", "knots", 130, "complied", "none", 0.0, 0.0),
    (860.0, "climb", "feet", 6000, "complied", "none", 25.0, 0.0),
    (1010.0, "turn_right_heading", "degrees", 250, "complied", "small", 0.0, 4.0),
    (1180.0, "descend", "feet", 5200, "incomplete", "not_applicable", -10.0, 0.0),
    (1340.0, "decelerate", "knots", 110, "complied", "none", 0.0, 0.0),
)


def ledger() -> list[dict[str, object]]:
    """Ten varied clearances across two legs, coherent enough to validate."""
    events: list[dict[str, object]] = []
    for position, row in enumerate(LEDGER_SHAPE, start=1):
        issue, command, unit, target, status, overshoot, climb, turn = row
        complied = status in {"complied", "complied_late"}
        executes = complied or status == "violated"
        altitude, heading, airspeed = 4000.0 + 30 * position, 180.0, 110.0
        execution_at = issue + 3.0
        completion_at = issue + 24.0
        event = {
            "clearance_index": position,
            "issued_time_s": issue,
            "command_type": command,
            "target_value": target,
            "target_unit": unit,
            "issue_altitude_ft": altitude,
            "issue_heading_deg": heading,
            "issue_airspeed_kt": airspeed,
            "maximum_commanded_progress": abs(target - (altitude if unit == "feet" else airspeed))
            if unit != "degrees"
            else 40.0,
            "execution_altitude_ft": altitude + climb * 3 if executes else None,
            "execution_heading_deg": (heading + turn * 3) % 360.0 if executes else None,
            "execution_airspeed_kt": airspeed if executes else None,
            "completion_altitude_ft": altitude + climb * 24 if complied else None,
            "completion_heading_deg": (heading + turn * 24) % 360.0 if complied else None,
            "completion_airspeed_kt": airspeed if complied else None,
            "ending_altitude_ft": altitude + climb * 24,
            "ending_heading_deg": (heading + turn * 24) % 360.0,
            "ending_airspeed_kt": airspeed,
            "execution_start_time_s": execution_at if executes else None,
            "completion_time_s": completion_at if complied else None,
            "status": status,
            "superseded_by_index": None,
            "overshoot_bucket": overshoot,
        }
        events.append(event)
    judge.validate_document({"clearances": events})
    return events


CREDIT_GROUPS = ("target", "status", "progress", "chain", "timing", "states")


def wreck_groups(event: dict[str, object], groups: tuple[str, ...]) -> dict[str, object]:
    """Copy `event` with each named credit group made wrong and nothing else.

    Used to walk the reward up one group at a time, which is the property the
    scorer has to have: repairing a field can never cost you.
    """
    entry = copy.deepcopy(event)
    if "target" in groups:
        if entry["target_unit"] == "degrees":
            entry["target_value"] = (float(entry["target_value"]) + 90.0) % 360.0
        else:
            entry["target_value"] = float(entry["target_value"]) + 900.0
    if "status" in groups:
        entry["status"] = "violated" if entry["status"] != "violated" else "incomplete"
    if "states" in groups:
        entry["issue_altitude_ft"] = float(entry["issue_altitude_ft"]) + 900.0
    if "timing" in groups:
        for field in ("execution_start_time_s", "completion_time_s"):
            base = entry[field]
            anchor = float(entry["issued_time_s"]) if base is None else float(base)
            entry[field] = anchor + 500.0
    if "chain" in groups:
        entry["overshoot_bucket"] = "large" if entry["overshoot_bucket"] != "large" else "none"
    if "progress" in groups:
        entry["maximum_commanded_progress"] = (
            float(entry["maximum_commanded_progress"]) + 900.0
        )
    return entry


def spurious_entry(events: list[dict[str, object]]) -> dict[str, object]:
    """A well-formed clearance that no ground-truth event can match."""
    entry = copy.deepcopy(events[-1])
    issue = float(events[-1]["issued_time_s"]) + 160.0
    entry["clearance_index"] = len(events) + 1
    entry["issued_time_s"] = issue
    entry["execution_start_time_s"] = issue + 3.0
    entry["completion_time_s"] = issue + 24.0
    entry["status"] = "complied"
    entry["superseded_by_index"] = None
    return entry


def gradable_positions(events: list[dict[str, object]]) -> list[int]:
    ceiling = judge.shortcut_ceiling(events)
    return [
        position
        for position, units in enumerate(ceiling)
        if judge.FULL_CREDIT_UNITS - units > 0
    ]


class ValidationTests(unittest.TestCase):
    def test_extra_field_is_rejected(self) -> None:
        event = clearance()
        event["extra"] = True
        with self.assertRaises(ValueError):
            judge.validate_document({"clearances": [event]})

    def test_invalid_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prediction.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(ValueError):
                judge.load_json(path)

    def test_deeply_nested_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prediction.json"
            path.write_text("[" * 2000 + "]" * 2000, encoding="utf-8")
            with self.assertRaises(ValueError):
                judge.load_json(path)

    def test_superseded_requires_later_index(self) -> None:
        event = clearance()
        event.update(
            {"completion_time_s": None, "status": "superseded", "superseded_by_index": 1}
        )
        with self.assertRaises(ValueError):
            judge.validate_document({"clearances": [event]})

    def test_noncontiguous_index_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            judge.validate_document({"clearances": [clearance(2)]})

    def test_post_video_event_is_rejected(self) -> None:
        prediction = clearance()
        prediction["issued_time_s"] = 4000
        with self.assertRaises(ValueError):
            judge.validate_document({"clearances": [prediction]})

    def test_oversized_number_is_rejected(self) -> None:
        prediction = clearance()
        prediction["target_value"] = 10**400
        with self.assertRaises(ValueError):
            judge.validate_document({"clearances": [prediction]})

    def test_malformed_entry_is_dropped_not_fatal(self) -> None:
        """One bad entry costs precision; it does not void the whole submission."""
        events = ledger()
        broken = copy.deepcopy(events[0])
        broken["status"] = "nonsense"
        usable, submitted, dropped = judge.accept_predictions(
            {"clearances": events + [broken]}
        )
        self.assertEqual(dropped, 1)
        self.assertEqual(submitted, len(events) + 1)
        self.assertEqual(len(usable), len(events))

    def test_serialized_document_round_trip(self) -> None:
        document = {"clearances": [clearance()]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prediction.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            self.assertEqual(judge.load_json(path), document)


class AnchorTests(unittest.TestCase):
    """The reward is an affine map sending a transcript-only ledger to 0 and the
    oracle to 1. Both ends are load bearing, so both are pinned here."""

    def test_oracle_scores_one(self) -> None:
        events = ledger()
        self.assertEqual(judge.score({"clearances": events}, {"clearances": events})["reward"], 1.0)

    def test_empty_scores_zero(self) -> None:
        result = judge.score({"clearances": []}, {"clearances": ledger()})
        self.assertEqual(result["reward"], 0.0)

    def test_transcript_only_guessing_scores_zero(self) -> None:
        """Perfect audio plus the best constant guess for every visual field."""
        events = ledger()
        shortcut = judge.shortcut_reference(events)
        result = judge.score({"clearances": shortcut}, {"clearances": events})
        self.assertEqual(result["reward"], 0.0)

    def test_majority_status_guess_scores_zero(self) -> None:
        """Naming the modal status everywhere must not pay."""
        events = ledger()
        guess = []
        for event in events:
            entry = copy.deepcopy(event)
            entry.update(
                {
                    "status": "complied",
                    "overshoot_bucket": "none",
                    "superseded_by_index": None,
                    "maximum_commanded_progress": 40.0,
                    "execution_start_time_s": event["issued_time_s"] + 3.0,
                    "completion_time_s": event["issued_time_s"] + 24.0,
                    "issue_altitude_ft": 4000.0,
                    "issue_heading_deg": 180.0,
                    "issue_airspeed_kt": 110.0,
                    "execution_altitude_ft": 4000.0,
                    "execution_heading_deg": 180.0,
                    "execution_airspeed_kt": 110.0,
                    "completion_altitude_ft": 4000.0,
                    "completion_heading_deg": 180.0,
                    "completion_airspeed_kt": 110.0,
                    "ending_altitude_ft": 4000.0,
                    "ending_heading_deg": 180.0,
                    "ending_airspeed_kt": 110.0,
                }
            )
            guess.append(entry)
        result = judge.score({"clearances": guess}, {"clearances": events})
        self.assertLess(result["reward"], 0.05)

    def test_shifted_times_lose_the_identity_gate(self) -> None:
        events = ledger()
        guess = []
        for event in events:
            entry = copy.deepcopy(event)
            entry["issued_time_s"] = float(event["issued_time_s"]) + 6.0
            guess.append(entry)
        result = judge.score({"clearances": guess}, {"clearances": events})
        self.assertEqual(result["details"]["identity_matches"], 0)
        self.assertEqual(result["reward"], 0.0)


class GradedCreditTests(unittest.TestCase):
    def test_partial_answer_lands_strictly_between(self) -> None:
        """Right chain, wrong instruments: real credit, well short of the oracle."""
        events = ledger()
        prediction = []
        for event in events:
            entry = copy.deepcopy(event)
            for field in (
                "issue_altitude_ft",
                "execution_altitude_ft",
                "completion_altitude_ft",
                "ending_altitude_ft",
            ):
                if entry[field] is not None:
                    entry[field] = float(entry[field]) + 900.0
            prediction.append(entry)
        result = judge.score({"clearances": prediction}, {"clearances": events})
        self.assertGreater(result["reward"], 0.0)
        self.assertLess(result["reward"], 1.0)

    def test_more_correct_groups_scores_higher(self) -> None:
        """Credit must be monotone, and it has to be visibly monotone in the
        range where answers actually land. Wrecking two fields of the same group
        is a weaker check than it looks -- both land on the same zero -- so this
        wrecks one group on a growing prefix of the ledger instead. Only gradable
        clearances count: an event a transcript already answers in full is not
        scored, so damaging it is correctly free."""
        events = ledger()
        gradable = gradable_positions(events)
        self.assertGreaterEqual(len(gradable), 4)

        def wreck_prefix(count: int) -> float:
            damaged = set(gradable[:count])
            prediction = [
                wreck_groups(event, ("states",)) if position in damaged else copy.deepcopy(event)
                for position, event in enumerate(events)
            ]
            return judge.score({"clearances": prediction}, {"clearances": events})["reward"]

        rewards = [wreck_prefix(count) for count in range(4)]
        self.assertEqual(rewards[0], 1.0)
        for better, worse in zip(rewards, rewards[1:]):
            self.assertLess(worse, better, f"reward did not fall: {rewards}")

    def test_duplicate_is_a_false_positive(self) -> None:
        events = ledger()
        prediction = copy.deepcopy(events) + [copy.deepcopy(events[-1])]
        usable, submitted, dropped = judge.accept_predictions({"clearances": prediction})
        result = judge.score(usable, {"clearances": events}, submitted=submitted, dropped=dropped)
        self.assertEqual(result["details"]["n_predicted"], len(events) + 1)
        self.assertLess(result["reward"], 1.0)

    def test_reordered_events_do_not_double_match(self) -> None:
        events = ledger()
        swapped = [copy.deepcopy(events[1]), copy.deepcopy(events[0])] + copy.deepcopy(events[2:])
        result = judge.score({"clearances": swapped}, {"clearances": events})
        self.assertLess(result["details"]["identity_matches"], len(events))

    def test_wrong_command_type_never_matches(self) -> None:
        events = ledger()
        prediction = copy.deepcopy(events)
        for entry in prediction:
            entry["command_type"] = "climb" if entry["command_type"] != "climb" else "descend"
            entry["target_unit"] = "feet"
            entry["target_value"] = 5000
        result = judge.score({"clearances": prediction}, {"clearances": events})
        # Clearances are >100 s apart, so only the aligned event is inside the
        # issue tolerance -- and its command_type no longer agrees.
        self.assertEqual(result["details"]["identity_matches"], 0)
        self.assertEqual(result["reward"], 0.0)

    def test_heading_target_wraparound_matches(self) -> None:
        expected = clearance()
        expected.update(
            {
                "command_type": "turn_right_heading",
                "target_value": 358,
                "target_unit": "degrees",
                "maximum_commanded_progress": 10,
            }
        )
        predicted = dict(expected)
        predicted["target_value"] = 0
        self.assertTrue(judge.strict_match(predicted, expected))


class ShortcutAnchorTests(unittest.TestCase):
    """The anchor is what stops audio alone from scoring. It has to be the
    strongest transcript-only ledger, not a convenient strawman."""

    def test_ceiling_dominates_every_transcript_only_ledger(self) -> None:
        """`shortcut_ceiling` is a per-event maximum and `shortcut_reference` is
        the single best whole ledger; checking the ceiling against the reference
        alone only restates that. The claim that matters is that the ceiling
        dominates *every* candidate the search considers, on every event."""
        events = ledger()
        ceiling = judge.shortcut_ceiling(events)
        candidates = list(judge._audio_strategies(events))
        candidates.append(judge.shortcut_reference(events))
        self.assertGreater(len(candidates), 1)
        for candidate in candidates:
            for position, (entry, event) in enumerate(zip(candidate, events)):
                self.assertGreaterEqual(
                    ceiling[position], judge.pair_credit_units(entry, event)
                )

    def test_a_hand_built_transcript_ledger_scores_nothing(self) -> None:
        """Built here rather than drawn from the judge's own strategy family, so
        it is not scored against a floor it helped define."""
        events = ledger()
        guess = []
        carried = {"feet": 4030.0, "degrees": 180.0, "knots": 110.0}
        for event in events:
            entry = copy.deepcopy(event)
            unit = event["target_unit"]
            carried[unit] = float(event["target_value"])
            issue = float(event["issued_time_s"])
            entry.update(
                {
                    "status": "complied",
                    "overshoot_bucket": "none",
                    "superseded_by_index": None,
                    "execution_start_time_s": issue + 2.0,
                    "completion_time_s": issue + 22.0,
                    "maximum_commanded_progress": 40.0,
                }
            )
            for prefix in ("issue", "execution", "completion", "ending"):
                entry[f"{prefix}_altitude_ft"] = carried["feet"]
                entry[f"{prefix}_heading_deg"] = carried["degrees"]
                entry[f"{prefix}_airspeed_kt"] = carried["knots"]
            guess.append(entry)
        result = judge.score({"clearances": guess}, {"clearances": events})
        self.assertEqual(result["reward"], 0.0)

    def test_anchor_chains_spoken_targets_forward(self) -> None:
        """ATC names each target aloud, so audio alone knows where a complied
        aircraft ends up. The ceiling has to search that carry-forward, or
        every transcript-only agent gets paid for doing it."""
        events = ledger()
        position = next(
            index
            for index, event in enumerate(events)
            if event["target_unit"] == "degrees"
        )
        target = float(events[position]["target_value"])
        self.assertTrue(
            any(
                float(candidate[position]["ending_heading_deg"]) == target
                and float(candidate[position]["completion_heading_deg"]) == target
                for candidate in judge._audio_strategies(events)
            ),
            "no transcript-only strategy carries the spoken heading forward",
        )

    def test_noisy_transcript_answer_still_scores_zero(self) -> None:
        """A shortcut answer that ties the anchor on average must not profit from
        its own variance: wins on some events have to be paid for by losses on
        others, or clipping alone would hand it a positive score."""
        events = ledger()
        noisy = []
        for position, entry in enumerate(judge.shortcut_reference(events)):
            entry = copy.deepcopy(entry)
            if position % 2 == 0:
                entry["status"] = events[position]["status"]  # a lucky guess
            else:
                entry["status"] = "violated"  # paid for by an unlucky one
                entry["ending_altitude_ft"] = float(entry["ending_altitude_ft"]) + 900.0
            noisy.append(entry)
        result = judge.score({"clearances": noisy}, {"clearances": events})
        self.assertEqual(result["reward"], 0.0)

    def test_events_audio_answers_in_full_are_not_scored(self) -> None:
        """Zero headroom means zero video signal. Such events leave the scored
        set entirely: they cannot be charged for, and answering them perfectly
        cannot pay."""
        events = ledger()
        gradable = gradable_positions(events)
        result = judge.score({"clearances": events}, {"clearances": events})
        details = result["details"]
        self.assertEqual(details["gradable_clearances"], len(gradable))
        # No padding, so the denominator is exactly the gradable count -- the
        # ungradable events are absent from both sides rather than free credit.
        self.assertEqual(details["chargeable_clearances"], len(gradable))
        self.assertEqual(result["reward"], 1.0)

        ungradable = [
            position for position in range(len(events)) if position not in set(gradable)
        ]
        if not ungradable:
            self.assertEqual(len(gradable), len(events))
            return
        oracle_on_ungradable = []
        for order, position in enumerate(ungradable, start=1):
            entry = copy.deepcopy(events[position])
            entry["clearance_index"] = order
            oracle_on_ungradable.append(entry)
        partial = judge.score({"clearances": oracle_on_ungradable}, {"clearances": events})
        self.assertEqual(partial["details"]["spurious_clearances"], 0)
        self.assertEqual(partial["reward"], 0.0)


class LegBoundaryTests(unittest.TestCase):
    """The old scorer bucketed by floor(predicted issued_time_s / 720), so a
    clearance guessed slightly early across a cut was filed under the previous
    leg and matched nothing -- even though the guess was inside the issue
    tolerance. Leg attribution now follows the aligned ground-truth event."""

    def test_prediction_late_across_a_cut_still_matches(self) -> None:
        events = ledger()
        crossing = next(
            index
            for index, event in enumerate(events)
            if 718.0 <= float(event["issued_time_s"]) < 720.0
        )
        self.assertEqual(judge.leg_of(events[crossing]), 0)

        prediction = copy.deepcopy(events)
        # Nudge the clearance to 720.0+, i.e. across the cut but inside +/-2 s.
        prediction[crossing]["issued_time_s"] = 720.5
        result = judge.score({"clearances": prediction}, {"clearances": events})

        self.assertEqual(result["details"]["identity_matches"], len(events))
        self.assertEqual(result["reward"], 1.0)
        # Credit is filed under the leg the clearance was really issued in.
        self.assertEqual(result["details"]["leg_credit_fractions"]["0"], 1.0)

    def test_prediction_early_across_a_cut_still_matches(self) -> None:
        """The maintainer's exact case: ground truth just *after* a cut, guessed
        1.5 s early so the guess falls in the previous leg.

        The shipped ground truth has no clearance within 6 s of a cut, so this
        case cannot be built from it -- the event is re-timed to 720.4 here on
        purpose. Without the fix, floor(718.9 / 720) = 0 while the truth is in
        leg 1, and the prediction matched nothing despite being inside the
        2 s issue tolerance."""
        events = ledger()
        moved = next(
            index
            for index, event in enumerate(events)
            if judge.leg_of(event) == 1
        )
        shift = 720.4 - float(events[moved]["issued_time_s"])
        for field in ("issued_time_s", "execution_start_time_s", "completion_time_s"):
            if events[moved][field] is not None:
                events[moved][field] = round(float(events[moved][field]) + shift, 1)
        self.assertEqual(judge.leg_of(events[moved]), 1)

        prediction = copy.deepcopy(events)
        prediction[moved]["issued_time_s"] = 718.9
        self.assertEqual(int(718.9 // judge.LEG_DURATION_S), 0)

        result = judge.score({"clearances": prediction}, {"clearances": events})
        self.assertEqual(result["details"]["identity_matches"], len(events))
        self.assertEqual(result["reward"], 1.0)
        # Filed under leg 1, where the clearance really was, not leg 0.
        self.assertEqual(result["details"]["leg_credit_fractions"]["1"], 1.0)

    def test_leg_attribution_ignores_predicted_time(self) -> None:
        events = ledger()
        prediction = copy.deepcopy(events)
        for entry in prediction:
            entry["issued_time_s"] = float(entry["issued_time_s"]) + 1.5
        result = judge.score({"clearances": prediction}, {"clearances": events})
        for leg, fraction in result["details"]["leg_credit_fractions"].items():
            self.assertGreater(fraction, 0.0, f"leg {leg} lost all credit to a time nudge")


class TimingCreditTests(unittest.TestCase):
    """Event times are graded, not pass/fail: a timestamp read to the second is
    worth twice one that merely lands inside the tolerance. State and time
    tolerances still must not contradict each other, so an answer that is late
    but honest about what it then saw keeps its state credit -- and pays for the
    shift out of the timing group instead of getting it free."""

    def shift_completions(
        self, events: list[dict[str, object]], delta: float
    ) -> list[dict[str, object]]:
        prediction = copy.deepcopy(events)
        for entry in prediction:
            if entry["completion_time_s"] is not None:
                entry["completion_time_s"] = float(entry["completion_time_s"]) + delta
        return prediction

    def timing_group(
        self, prediction: list[dict[str, object]], events: list[dict[str, object]]
    ) -> dict[str, int]:
        result = judge.score({"clearances": prediction}, {"clearances": events})
        return result["details"]["group_credit"]["timing"]

    def test_precise_timestamp_earns_the_whole_group(self) -> None:
        events = ledger()
        timing = self.timing_group(self.shift_completions(events, 0.5), events)
        self.assertEqual(timing["earned"], timing["available"])

    def test_inside_tolerance_earns_half(self) -> None:
        """At exactly EVENT_TOLERANCE_S the band is inclusive -- of half credit."""
        events = ledger()
        completions = sum(1 for event in events if event["completion_time_s"] is not None)
        self.assertGreater(completions, 0)
        per_timestamp = judge.TIMING_UNITS // 2
        forfeit = per_timestamp - per_timestamp // 2
        timing = self.timing_group(
            self.shift_completions(events, judge.EVENT_TOLERANCE_S), events
        )
        self.assertEqual(timing["earned"], timing["available"] - completions * forfeit)

    def test_outside_tolerance_earns_nothing(self) -> None:
        events = ledger()
        completions = sum(1 for event in events if event["completion_time_s"] is not None)
        per_timestamp = judge.TIMING_UNITS // 2
        timing = self.timing_group(
            self.shift_completions(events, judge.EVENT_TOLERANCE_S + 0.01), events
        )
        self.assertEqual(
            timing["earned"], timing["available"] - completions * per_timestamp
        )

    def test_precision_band_is_strictly_better_than_the_tolerance_band(self) -> None:
        events = ledger()
        precise = judge.score(
            {"clearances": self.shift_completions(events, judge.EVENT_PRECISE_S)},
            {"clearances": events},
        )["reward"]
        loose = judge.score(
            {"clearances": self.shift_completions(events, judge.EVENT_TOLERANCE_S)},
            {"clearances": events},
        )["reward"]
        self.assertEqual(precise, 1.0)
        self.assertLess(loose, precise)

    def test_coherently_late_answer_keeps_state_credit_but_pays_for_it(self) -> None:
        events = ledger()
        prediction = []
        for event in events:
            entry = copy.deepcopy(event)
            rates = judge.snapshot_rates(event)
            for prefix, field in (
                ("execution", "execution_start_time_s"),
                ("completion", "completion_time_s"),
            ):
                if entry[field] is None:
                    continue
                entry[field] = float(entry[field]) + 3.0
                for suffix, _, circular in judge.SNAPSHOT_DIMENSIONS:
                    key = f"{prefix}_{suffix}"
                    moved = float(entry[key]) + rates[suffix] * 3.0
                    entry[key] = moved % 360.0 if circular else moved
            prediction.append(entry)
        result = judge.score({"clearances": prediction}, {"clearances": events})
        states = result["details"]["group_credit"]["states"]
        timing = result["details"]["group_credit"]["timing"]
        # The two tolerances do not contradict each other ...
        self.assertEqual(states["earned"], states["available"])
        # ... but moving the timestamp is charged, so it is never a free ride.
        self.assertLess(timing["earned"], timing["available"])
        self.assertLess(result["reward"], 1.0)

    def test_a_shifted_timestamp_does_not_excuse_a_stale_reading(self) -> None:
        """The old scorer widened the band around the true event time, so an
        answer could keep the instruments it read at that time, move its
        timestamp, and be forgiven an error it had already made. The reference
        point moves with the claim instead: once the aircraft is moving fast
        enough, a stale reading filed under a later time is simply wrong."""
        expected = clearance()
        expected.update(
            {
                "target_value": 9000,
                "issue_altitude_ft": 3000,
                "execution_altitude_ft": 3100,
                "completion_altitude_ft": 9000,
                "ending_altitude_ft": 9000,
                "maximum_commanded_progress": 6000,
            }
        )
        stale = dict(expected)
        # Honest: the execution reading, filed at the execution time.
        self.assertTrue(
            judge.snapshot_matches(
                stale, expected, "execution", claimed_time=12.0, expected_time=12.0
            )
        )
        # Dishonest: the same reading, filed 4 s later while climbing ~256 ft/s.
        self.assertFalse(
            judge.snapshot_matches(
                stale, expected, "execution", claimed_time=16.0, expected_time=12.0
            )
        )

    def test_slack_does_not_excuse_a_stationary_error(self) -> None:
        """Where nothing is moving, the slack is zero and the budget is flat."""
        events = ledger()
        prediction = copy.deepcopy(events)
        for entry in prediction:
            entry["issue_airspeed_kt"] = float(entry["issue_airspeed_kt"]) + 40.0
        result = judge.score({"clearances": prediction}, {"clearances": events})
        self.assertLess(result["reward"], 1.0)


class DenominatorTests(unittest.TestCase):
    """Reward is chance-corrected credit over the gradable clearances plus any
    padding. The earlier F1 precision term charged every submitted entry, so a
    clearance whose gain was positive but smaller than the running score still
    dragged it down and answering *fewer* clearances than you could was the best
    move. That has to be the other way round."""

    def test_a_clean_answer_is_charged_only_for_gradable_clearances(self) -> None:
        events = ledger()
        details = judge.score({"clearances": events}, {"clearances": events})["details"]
        self.assertEqual(details["spurious_clearances"], 0)
        self.assertEqual(
            details["chargeable_clearances"], details["gradable_clearances"]
        )

    def test_padding_is_charged(self) -> None:
        events = ledger()
        padded = copy.deepcopy(events) + [spurious_entry(events)]
        judge.validate_document({"clearances": padded})
        details = judge.score({"clearances": padded}, {"clearances": events})["details"]
        self.assertEqual(details["identity_matches"], len(events))
        self.assertEqual(details["spurious_clearances"], 1)
        self.assertEqual(
            details["chargeable_clearances"], details["gradable_clearances"] + 1
        )

    def test_answering_one_more_readable_clearance_never_costs(self) -> None:
        """The property the instruction relies on: every clearance you can read
        better than a transcript is worth submitting."""
        events = ledger()
        rewards = [
            judge.score({"clearances": copy.deepcopy(events[:count])}, {"clearances": events})[
                "reward"
            ]
            for count in range(len(events) + 1)
        ]
        for smaller, larger in zip(rewards, rewards[1:]):
            self.assertLessEqual(smaller, larger, f"answering more cost reward: {rewards}")
        self.assertEqual(rewards[0], 0.0)
        self.assertEqual(rewards[-1], 1.0)

    def test_withholding_a_below_floor_clearance_still_pays(self) -> None:
        """Characterisation, not endorsement. Because a clearance read worse than
        a transcript could have guessed subtracts, an agent able to identify its
        own weak readings could raise its score by withholding them. The metric
        still carries that incentive; `calibration/rescore_ledgers.py` measures
        how far it goes on each real ledger and `scores.md` publishes it."""
        events = ledger()
        position = gradable_positions(events)[0]
        weak = copy.deepcopy(events)
        weak[position] = wreck_groups(events[position], CREDIT_GROUPS)
        submitted = judge.score({"clearances": weak}, {"clearances": events})["reward"]
        withheld = [entry for index, entry in enumerate(weak) if index != position]
        for order, entry in enumerate(withheld, start=1):
            entry["clearance_index"] = order
        dropped = judge.score({"clearances": withheld}, {"clearances": events})["reward"]
        self.assertGreater(dropped, submitted)


class AlignmentTests(unittest.TestCase):
    """A clearance wrong in every gradable field is still the clearance it names.
    Leaving such a pair out of the alignment made the reward non-monotone: the
    entry cost nothing while unpaired, and *fixing one field* turned it into a
    scored pair sitting below the transcript-only floor, which subtracted."""

    def test_zero_credit_identity_match_is_still_a_pair(self) -> None:
        events = ledger()
        wrecked = [wreck_groups(event, CREDIT_GROUPS) for event in events]
        pairs = judge.align(wrecked, events)
        self.assertEqual(len(pairs), len(events))
        self.assertTrue(all(units == 0 for _, _, units in pairs), pairs)
        result = judge.score({"clearances": wrecked}, {"clearances": events})
        self.assertEqual(result["details"]["identity_matches"], len(events))
        self.assertEqual(result["reward"], 0.0)

    def test_repairing_one_group_at_a_time_never_lowers_the_reward(self) -> None:
        events = ledger()
        rewards = []
        for count in range(len(CREDIT_GROUPS) + 1):
            still_wrong = CREDIT_GROUPS[count:]
            prediction = [wreck_groups(event, still_wrong) for event in events]
            rewards.append(
                judge.score({"clearances": prediction}, {"clearances": events})["reward"]
            )
        for worse, better in zip(rewards, rewards[1:]):
            self.assertLessEqual(worse, better, f"a repair lowered the reward: {rewards}")
        self.assertEqual(rewards[0], 0.0)
        self.assertEqual(rewards[-1], 1.0)


class SupersessionLinkTests(unittest.TestCase):
    """`superseded_by_index` is resolved to the clearance it names before it is
    compared. Comparing the raw integer punished correct bookkeeping: an agent
    that misses one clearance and renumbers the rest contiguously -- which is
    exactly what a one-based chronological index asks for -- had link values that
    no longer coincided with ground truth's."""

    def build(self) -> list[dict[str, object]]:
        rows = (
            (100.0, "climb", "feet", 5000, "complied", "none", None),
            (240.0, "turn_right_heading", "degrees", 90, "superseded", "not_applicable", 3),
            (300.0, "turn_left_heading", "degrees", 20, "complied", "none", None),
        )
        events = []
        for position, row in enumerate(rows, start=1):
            issue, command, unit, target, status, overshoot, link = row
            complied = status == "complied"
            events.append(
                {
                    "clearance_index": position,
                    "issued_time_s": issue,
                    "command_type": command,
                    "target_value": target,
                    "target_unit": unit,
                    "issue_altitude_ft": 4000.0,
                    "issue_heading_deg": 180.0,
                    "issue_airspeed_kt": 110.0,
                    "maximum_commanded_progress": 40.0,
                    "execution_altitude_ft": 4030.0,
                    "execution_heading_deg": 186.0,
                    "execution_airspeed_kt": 110.0,
                    "completion_altitude_ft": 4200.0 if complied else None,
                    "completion_heading_deg": 200.0 if complied else None,
                    "completion_airspeed_kt": 110.0 if complied else None,
                    "ending_altitude_ft": 4200.0,
                    "ending_heading_deg": 200.0,
                    "ending_airspeed_kt": 110.0,
                    "execution_start_time_s": issue + 3.0,
                    "completion_time_s": issue + 24.0 if complied else None,
                    "status": status,
                    "superseded_by_index": link,
                    "overshoot_bucket": overshoot,
                }
            )
        judge.validate_document({"clearances": events})
        return events

    def test_renumbered_link_still_earns_chain_credit(self) -> None:
        events = self.build()
        # The agent missed the first clearance and renumbered contiguously, so
        # its link says 2 where ground truth says 3.
        prediction = copy.deepcopy(events[1:])
        for order, entry in enumerate(prediction, start=1):
            entry["clearance_index"] = order
        prediction[0]["superseded_by_index"] = 2
        judge.validate_document({"clearances": prediction})
        self.assertNotEqual(
            prediction[0]["superseded_by_index"], events[1]["superseded_by_index"]
        )

        self.assertEqual(
            judge.link_identity(prediction[0], judge.index_map(prediction)),
            judge.link_identity(events[1], judge.index_map(events)),
        )
        chain = judge.score({"clearances": prediction}, {"clearances": events})["details"][
            "group_credit"
        ]["chain"]
        self.assertEqual(chain["earned"], judge.CHAIN_UNITS * len(prediction))

    def test_a_link_to_the_wrong_clearance_loses_chain_credit(self) -> None:
        events = self.build()
        prediction = copy.deepcopy(events)
        prediction[1]["overshoot_bucket"] = "none"
        chain = judge.score({"clearances": prediction}, {"clearances": events})["details"][
            "group_credit"
        ]["chain"]
        self.assertEqual(chain["earned"], judge.CHAIN_UNITS * (len(events) - 1))

    def test_an_unresolvable_link_never_collides_with_a_resolved_one(self) -> None:
        events = self.build()
        dangling = judge.link_identity(
            {"superseded_by_index": 3, "command_type": "climb", "issued_time_s": 0.0}, {}
        )
        resolved = judge.link_identity(events[1], judge.index_map(events))
        self.assertIsNotNone(dangling)
        self.assertIsNotNone(resolved)
        self.assertFalse(judge.links_match(dangling, resolved))


class HostilePayloadTests(unittest.TestCase):
    """One malformed clearance costs that clearance and nothing more. `check_event`
    aims to raise ValueError, but an unhashable enum value or a null where a
    number belongs used to raise TypeError, which escaped `accept_predictions`
    and collapsed the whole submission to zero."""

    def document_with(self, field: str, value: object) -> tuple[list[dict[str, object]], dict]:
        events = ledger()
        broken = spurious_entry(events)
        broken[field] = value
        return events, {"clearances": copy.deepcopy(events) + [broken]}

    def check_dropped(self, field: str, value: object) -> None:
        events, document = self.document_with(field, value)
        usable, submitted, dropped = judge.accept_predictions(document)
        self.assertEqual(dropped, 1)
        self.assertEqual(submitted, len(events) + 1)
        self.assertEqual(len(usable), len(events))
        result = judge.score(
            usable, {"clearances": events}, submitted=submitted, dropped=dropped
        )
        # The rest of the answer survives intact; only the padding is charged.
        self.assertEqual(result["details"]["spurious_clearances"], 1)
        self.assertGreater(result["reward"], 0.0)

    def test_unhashable_enum_drops_only_that_clearance(self) -> None:
        for field, value in (
            ("status", []),
            ("command_type", {"climb": True}),
            ("overshoot_bucket", []),
            ("target_unit", ["feet"]),
        ):
            with self.subTest(field=field, value=value):
                self.check_dropped(field, value)

    def test_non_numeric_field_drops_only_that_clearance(self) -> None:
        for field, value in (
            ("issue_altitude_ft", "3600"),
            ("maximum_commanded_progress", None),
            ("maximum_commanded_progress", float("nan")),
            ("target_value", [1]),
            ("execution_start_time_s", {}),
            ("clearance_index", "4"),
        ):
            with self.subTest(field=field, value=value):
                self.check_dropped(field, value)

    def test_a_wrongly_shaped_document_is_still_fatal(self) -> None:
        for document in ({"clearances": {}}, {"other": []}, [], None):
            with self.subTest(document=document):
                with self.assertRaises(ValueError):
                    judge.accept_predictions(document)

    def test_unbounded_integer_index_drops_only_that_clearance(self) -> None:
        """Python ints have no width, so `isinstance(value, int)` alone is not a
        bound. An index of 10**400 used to survive `check_event` and then raise
        OverflowError from `float()` inside `link_identity`, outside the
        ValueError contract -- which zeroed the whole submission instead of
        costing one clearance."""
        for field in ("clearance_index", "superseded_by_index"):
            with self.subTest(field=field):
                self.check_dropped(field, 10**400)

    def test_oversized_supersession_does_not_zero_the_answer(self) -> None:
        """End to end, on a real superseded clearance rather than padding."""
        events = ledger()
        position = next(
            index for index, event in enumerate(events)
            if event["status"] == "incomplete"
            and any(
                judge.dimension_of(later) == judge.dimension_of(event)
                for later in events[index + 1:]
            )
        )
        successor = next(
            later for later in events[position + 1:]
            if judge.dimension_of(later) == judge.dimension_of(events[position])
        )
        events[position]["status"] = "superseded"
        events[position]["superseded_by_index"] = successor["clearance_index"]
        judge.validate_document({"clearances": copy.deepcopy(events)})

        prediction = copy.deepcopy(events)
        prediction[position]["superseded_by_index"] = 10**400
        usable, submitted, dropped = judge.accept_predictions(
            {"clearances": prediction}
        )
        self.assertEqual(dropped, 1)
        result = judge.score(
            usable, {"clearances": events}, submitted=submitted, dropped=dropped
        )
        self.assertEqual(result["details"]["reason"], "ok")
        self.assertGreater(result["reward"], 0.5)


if __name__ == "__main__":
    unittest.main()
