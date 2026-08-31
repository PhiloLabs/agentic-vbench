from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).parent
GROUND_TRUTH = HERE / "ground_truth.json"
SPEC = importlib.util.spec_from_file_location("meva_judge", HERE / "judge.py")
assert SPEC and SPEC.loader
JUDGE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = JUDGE
SPEC.loader.exec_module(JUDGE)


class JudgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ground_truth_value = json.loads(
            GROUND_TRUTH.read_text(encoding="utf-8")
        )
        cls.ground_truth = JUDGE._parse(
            GROUND_TRUTH, strict=True
        )

    def _parse_value(self, value: dict) -> list:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "solution.json"
            path.write_text(
                json.dumps(value, indent=2) + "\n", encoding="utf-8"
            )
            return JUDGE._parse(path, strict=False)

    def test_oracle_scores_one(self) -> None:
        result = JUDGE.score(self.ground_truth, self.ground_truth)
        self.assertEqual(result["reward"], 1.0)

    def test_empty_scores_zero(self) -> None:
        prediction = self._parse_value({"ledgers": []})
        self.assertEqual(
            JUDGE.score(prediction, self.ground_truth)["reward"], 0.0
        )

    def test_order_is_irrelevant(self) -> None:
        value = copy.deepcopy(self.ground_truth_value)
        value["ledgers"].reverse()
        for ledger in value["ledgers"]:
            ledger["events"].reverse()
        prediction = self._parse_value(value)
        self.assertEqual(
            JUDGE.score(prediction, self.ground_truth)["reward"], 1.0
        )

    def test_narrow_centered_interval_gets_partial_credit(self) -> None:
        value = copy.deepcopy(self.ground_truth_value)
        event = value["ledgers"][0]["events"][0]
        midpoint = (event["start_time_s"] + event["end_time_s"]) / 2
        event["start_time_s"] = midpoint - 0.1
        event["end_time_s"] = midpoint + 0.1
        prediction = self._parse_value(value)
        reward = JUDGE.score(prediction, self.ground_truth)["reward"]
        self.assertGreater(reward, 0.8)
        self.assertLess(reward, 1.0)

    def test_duplicates_are_penalized(self) -> None:
        value = copy.deepcopy(self.ground_truth_value)
        value["ledgers"][0]["events"].append(
            copy.deepcopy(value["ledgers"][0]["events"][0])
        )
        prediction = self._parse_value(value)
        reward = JUDGE.score(prediction, self.ground_truth)["reward"]
        self.assertGreater(reward, 0.9)
        self.assertLess(reward, 1.0)

    def test_midpoint_tolerance_is_inclusive(self) -> None:
        for expected in self.ground_truth:
            shifted = JUDGE.Event(
                reference_id=expected.reference_id,
                activity_type=expected.activity_type,
                start_time_s=(
                    expected.start_time_s + JUDGE.MIDPOINT_TOLERANCE_S
                ),
                end_time_s=(
                    expected.end_time_s + JUDGE.MIDPOINT_TOLERANCE_S
                ),
            )
            self.assertGreater(JUDGE._temporal_weight(shifted, expected), 0.0)

    def test_all_events_on_one_identity_stays_low(self) -> None:
        events = [
            copy.deepcopy(event)
            for ledger in self.ground_truth_value["ledgers"]
            for event in ledger["events"]
        ]
        prediction = self._parse_value(
            {
                "ledgers": [
                    {"reference_id": "reference_001", "events": events}
                ]
            }
        )
        self.assertLessEqual(
            JUDGE.score(prediction, self.ground_truth)["reward"], 0.1
        )

    def test_copying_all_events_to_every_identity_stays_low(self) -> None:
        events = [
            copy.deepcopy(event)
            for ledger in self.ground_truth_value["ledgers"]
            for event in ledger["events"]
        ]
        prediction = self._parse_value(
            {
                "ledgers": [
                    {
                        "reference_id": reference_id,
                        "events": copy.deepcopy(events),
                    }
                    for reference_id in JUDGE.REFERENCE_IDS
                ]
            }
        )
        self.assertLessEqual(
            JUDGE.score(prediction, self.ground_truth)["reward"], 0.15
        )

    def test_unknown_reference_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self._parse_value(
                {
                    "ledgers": [
                        {
                            "reference_id": "reference_999",
                            "events": [],
                        }
                    ]
                }
            )

    def test_unknown_fields_are_ignored(self) -> None:
        value = copy.deepcopy(self.ground_truth_value)
        value["metadata"] = {"ignored": True}
        value["ledgers"][0]["confidence"] = 0.5
        value["ledgers"][0]["events"][0]["note"] = "ignored"
        prediction = self._parse_value(value)
        self.assertEqual(
            JUDGE.score(prediction, self.ground_truth)["reward"], 1.0
        )

    def test_ground_truth_symlink_scores_zero_and_is_not_artifacted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            solution = directory_path / "solution.json"
            solution.symlink_to(GROUND_TRUTH)
            reward_json = directory_path / "reward.json"
            reward_txt = directory_path / "reward.txt"
            artifact = directory_path / "submitted_solution.json"
            subprocess.run(
                [
                    sys.executable,
                    str(HERE / "judge.py"),
                    "--solution",
                    str(solution),
                    "--ground-truth",
                    str(GROUND_TRUTH),
                    "--reward-json",
                    str(reward_json),
                    "--reward-txt",
                    str(reward_txt),
                    "--artifact",
                    str(artifact),
                ],
                check=True,
            )
            result = json.loads(reward_json.read_text(encoding="utf-8"))
            self.assertEqual(result["reward"], 0.0)
            self.assertIn("invalid solution", result["details"]["reason"])
            self.assertFalse(artifact.exists())

    def test_fifo_is_rejected_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "solution.json"
            os.mkfifo(path)
            with self.assertRaises(ValueError):
                JUDGE._parse(path, strict=False)

    def test_oversized_solution_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "solution.json"
            path.write_bytes(b" " * (JUDGE.MAX_SOLUTION_BYTES + 1))
            with self.assertRaises(ValueError):
                JUDGE._parse(path, strict=False)

    def test_ground_truth_hardlink_scores_zero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            directory_path = Path(directory)
            solution = directory_path / "solution.json"
            os.link(GROUND_TRUTH, solution)
            reward_json = directory_path / "reward.json"
            reward_txt = directory_path / "reward.txt"
            artifact = directory_path / "submitted_solution.json"
            subprocess.run(
                [
                    sys.executable,
                    str(HERE / "judge.py"),
                    "--solution",
                    str(solution),
                    "--ground-truth",
                    str(GROUND_TRUTH),
                    "--reward-json",
                    str(reward_json),
                    "--reward-txt",
                    str(reward_txt),
                    "--artifact",
                    str(artifact),
                ],
                check=True,
            )
            result = json.loads(reward_json.read_text(encoding="utf-8"))
            self.assertEqual(result["reward"], 0.0)
            self.assertIn("aliases ground truth", result["details"]["reason"])
            self.assertFalse(artifact.exists())


if __name__ == "__main__":
    unittest.main()
