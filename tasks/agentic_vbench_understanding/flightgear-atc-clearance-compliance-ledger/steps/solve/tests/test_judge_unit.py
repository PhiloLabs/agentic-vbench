from __future__ import annotations

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
            {
                "completion_time_s": None,
                "status": "superseded",
                "superseded_by_index": 1,
            }
        )
        with self.assertRaises(ValueError):
            judge.validate_document({"clearances": [event]})


class ScoringTests(unittest.TestCase):
    def test_oracle_scores_one(self) -> None:
        document = {"clearances": [clearance()]}
        self.assertEqual(judge.score(document, document)["reward"], 1.0)

    def test_empty_scores_zero(self) -> None:
        result = judge.score({"clearances": []}, {"clearances": [clearance()]})
        self.assertEqual(result["reward"], 0.0)

    def test_duplicate_is_false_positive(self) -> None:
        duplicate = clearance(2)
        prediction = {"clearances": [clearance(), duplicate]}
        result = judge.score(prediction, {"clearances": [clearance()]})
        self.assertEqual(result["details"]["strict_matches"], 1)
        self.assertEqual(result["details"]["false_positives"], 1)
        self.assertEqual(result["details"]["clearance_chain_f1"], 0.6667)
        self.assertEqual(result["reward"], 0.0667)

    def test_wrong_status_breaks_chain(self) -> None:
        prediction = clearance()
        prediction.update(
            {
                "completion_time_s": None,
                "status": "incomplete",
            }
        )
        result = judge.score(
            {"clearances": [prediction]},
            {"clearances": [clearance()]},
        )
        self.assertEqual(result["reward"], 0.0)

    def test_wrong_trajectory_value_breaks_chain(self) -> None:
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
        ):
            with self.subTest(field=field):
                prediction = clearance()
                prediction[field] = float(prediction[field]) + 26
                result = judge.score(
                    {"clearances": [prediction]},
                    {"clearances": [clearance()]},
                )
                self.assertEqual(result["reward"], 0.0)

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

    def test_time_boundary_is_inclusive(self) -> None:
        prediction = clearance()
        prediction["issued_time_s"] = 12.0
        prediction["execution_start_time_s"] = 16.0
        prediction["completion_time_s"] = 39.0
        result = judge.score(
            {"clearances": [prediction]},
            {"clearances": [clearance()]},
        )
        self.assertEqual(result["reward"], 1.0)

    def test_time_outside_boundary_fails(self) -> None:
        prediction = clearance()
        prediction["completion_time_s"] = 39.01
        result = judge.score(
            {"clearances": [prediction]},
            {"clearances": [clearance()]},
        )
        self.assertEqual(result["reward"], 0.0)

    def test_reordered_events_do_not_double_match(self) -> None:
        first = clearance(1)
        second = clearance(2)
        second["issued_time_s"] = 50.0
        second["execution_start_time_s"] = 52.0
        second["completion_time_s"] = 70.0
        result = judge.score(
            {"clearances": [second, first]},
            {"clearances": [first, second]},
        )
        self.assertLessEqual(result["details"]["strict_matches"], 1)

    def test_serialized_document_round_trip(self) -> None:
        document = {"clearances": [clearance()]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prediction.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            self.assertEqual(judge.load_json(path), document)


if __name__ == "__main__":
    unittest.main()
