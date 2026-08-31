#!/usr/bin/env python3

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("beam_judge", TESTS_DIR / "judge.py")
JUDGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(JUDGE)
GROUND_TRUTH = JUDGE.load_ground_truth(TESTS_DIR / "ground_truth.json")


class JudgeTests(unittest.TestCase):
    def test_oracle_scores_one(self):
        reward, details = JUDGE.grade(GROUND_TRUTH, GROUND_TRUTH)
        self.assertEqual(reward, 1.0)
        self.assertEqual(details["true_positives_complete_record"], 23)

    def test_empty_scores_zero(self):
        reward, _ = JUDGE.grade([], GROUND_TRUTH)
        self.assertEqual(reward, 0.0)

    def test_one_complete_record_uses_f1(self):
        reward, _ = JUDGE.grade([GROUND_TRUTH[0]], GROUND_TRUTH)
        self.assertEqual(reward, 0.083333)

    def test_timestamp_tolerances_are_inclusive(self):
        record = dict(GROUND_TRUTH[0])
        record["start_time"] = "00:03:41.971"
        record["end_time"] = "00:04:58.448"
        record["dismount_takeoff_time"] = "00:04:57.647"
        record["score_time"] = "00:08:35.000"
        reward, details = JUDGE.grade([record], [GROUND_TRUTH[0]])
        self.assertEqual(reward, 1.0)
        self.assertEqual(details["true_positives_complete_record"], 1)

    def test_start_outside_tolerance_does_not_match(self):
        record = dict(GROUND_TRUTH[0])
        record["start_time"] = "00:03:41.972"
        reward, _ = JUDGE.grade([record], [GROUND_TRUTH[0]])
        self.assertEqual(reward, 0.0)

    def test_end_outside_tolerance_does_not_match(self):
        record = dict(GROUND_TRUTH[0])
        record["end_time"] = "00:04:58.449"
        reward, _ = JUDGE.grade([record], [GROUND_TRUTH[0]])
        self.assertEqual(reward, 0.0)

    def test_dismount_takeoff_outside_tolerance_does_not_match(self):
        record = dict(GROUND_TRUTH[0])
        record["dismount_takeoff_time"] = "00:04:57.648"
        reward, details = JUDGE.grade([record], [GROUND_TRUTH[0]])
        self.assertEqual(reward, 0.0)
        self.assertEqual(
            details["diagnostics"]["dismount_takeoff_within_tolerance"], 0
        )

    def test_dismount_takeoff_must_precede_landing(self):
        record = dict(GROUND_TRUTH[0])
        record["dismount_takeoff_time"] = record["end_time"]
        reward, details = JUDGE.grade([record], [GROUND_TRUTH[0]])
        self.assertEqual(reward, 0.0)
        self.assertEqual(details["n_invalid_records"], 1)
        self.assertIn("schema-invalid", details["reason"])

    def test_score_time_outside_tolerance_does_not_match(self):
        record = dict(GROUND_TRUTH[0])
        record["score_time"] = "00:08:35.001"
        reward, details = JUDGE.grade([record], [GROUND_TRUTH[0]])
        self.assertEqual(reward, 0.0)
        self.assertEqual(
            details["diagnostics"]["score_time_within_tolerance"], 0
        )

    def test_score_time_must_follow_routine_end(self):
        record = dict(GROUND_TRUTH[0])
        record["score_time"] = record["end_time"]
        reward, details = JUDGE.grade([record], [GROUND_TRUTH[0]])
        self.assertEqual(reward, 0.0)
        self.assertEqual(details["n_invalid_records"], 1)
        self.assertIn("schema-invalid", details["reason"])

    def test_wrong_school_prevents_complete_match(self):
        record = dict(GROUND_TRUTH[0])
        record["school"] = "Arizona"
        reward, details = JUDGE.grade([record], [GROUND_TRUTH[0]])
        self.assertEqual(reward, 0.0)
        self.assertEqual(details["diagnostics"]["school_exact"], 0)

    def test_unknown_school_is_schema_invalid(self):
        record = dict(GROUND_TRUTH[0])
        record["school"] = "Unknown"
        reward, details = JUDGE.grade([record], [GROUND_TRUTH[0]])
        self.assertEqual(reward, 0.0)
        self.assertEqual(details["n_invalid_records"], 1)
        self.assertIn("schema-invalid", details["reason"])

    def test_wrong_gymnast_name_prevents_complete_match(self):
        record = dict(GROUND_TRUTH[0])
        record["gymnast_name"] = "Another Gymnast"
        reward, details = JUDGE.grade([record], [GROUND_TRUTH[0]])
        self.assertEqual(reward, 0.0)
        self.assertEqual(details["diagnostics"]["gymnast_name_exact"], 0)

    def test_wrong_score_prevents_complete_match(self):
        record = dict(GROUND_TRUTH[0])
        record["beam_score"] = "9.750"
        reward, details = JUDGE.grade([record], [GROUND_TRUTH[0]])
        self.assertEqual(reward, 0.0)
        self.assertEqual(details["diagnostics"]["beam_score_exact"], 0)

    def test_score_requires_exact_three_decimal_string(self):
        for invalid_score in ("9.8", "9.85", 9.850, "10.001"):
            with self.subTest(invalid_score=invalid_score):
                record = dict(GROUND_TRUTH[0])
                record["beam_score"] = invalid_score
                reward, details = JUDGE.grade([record], [GROUND_TRUTH[0]])
                self.assertEqual(reward, 0.0)
                self.assertEqual(details["n_invalid_records"], 1)
                self.assertIn("schema-invalid", details["reason"])

    def test_one_invalid_record_invalidates_the_whole_submission(self):
        invalid = dict(GROUND_TRUTH[-1])
        invalid["extra"] = "not allowed"
        records = [*GROUND_TRUTH, invalid]
        reward, details = JUDGE.grade(records, GROUND_TRUTH)
        self.assertEqual(reward, 0.0)
        self.assertEqual(details["n_invalid_records"], 1)
        self.assertEqual(details["true_positives_complete_record"], 0)
        self.assertIn("schema-invalid", details["reason"])

    def test_reversed_oracle_invalidates_the_whole_submission(self):
        reward, details = JUDGE.grade(list(reversed(GROUND_TRUTH)), GROUND_TRUTH)
        self.assertEqual(reward, 0.0)
        self.assertEqual(details["true_positives_complete_record"], 0)
        self.assertIn("chronological", details["reason"])

    def test_duplicate_start_is_not_strictly_chronological(self):
        records = [GROUND_TRUTH[0], GROUND_TRUTH[0]]
        reward, details = JUDGE.grade(records, [GROUND_TRUTH[0]])
        self.assertEqual(reward, 0.0)
        self.assertIn("chronological", details["reason"])

    def test_load_predictions_reports_invalid_schema(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "solution.json"
            path.write_text(
                json.dumps({"beam_routines": [{"start_time": "00:00:01.000"}]})
            )
            records, reason = JUDGE.load_predictions(path)
        self.assertEqual(len(records), 1)
        self.assertIn("schema-invalid", reason)

    def test_malformed_file_loads_as_empty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "solution.json"
            path.write_text("{")
            records, reason = JUDGE.load_predictions(path)
        self.assertEqual(records, [])
        self.assertIn("malformed", reason)

    def test_ground_truth_and_oracle_files_are_identical(self):
        oracle_path = TESTS_DIR.parent / "solution" / "solution.json"
        self.assertEqual(
            json.loads(oracle_path.read_text()),
            json.loads((TESTS_DIR / "ground_truth.json").read_text()),
        )


if __name__ == "__main__":
    unittest.main()
