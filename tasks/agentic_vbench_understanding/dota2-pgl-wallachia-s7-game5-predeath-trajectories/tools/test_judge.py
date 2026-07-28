#!/usr/bin/env python3

from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


TASK_ROOT = Path(__file__).resolve().parents[1]
JUDGE = TASK_ROOT / "steps" / "solve" / "tests" / "judge.py"
ORACLE = TASK_ROOT / "steps" / "solve" / "solution" / "solution.json"


class JudgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.oracle = json.loads(ORACLE.read_text(encoding="utf-8"))

    def score(self, value: object) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            solution = root / "solution.json"
            reward_json = root / "reward.json"
            reward_txt = root / "reward.txt"
            details_json = root / "details.json"
            solution.write_text(json.dumps(value), encoding="utf-8")
            subprocess.run(
                [
                    "python3",
                    str(JUDGE),
                    "--solution",
                    str(solution),
                    "--reward-json",
                    str(reward_json),
                    "--reward-txt",
                    str(reward_txt),
                    "--details-json",
                    str(details_json),
                ],
                check=True,
            )
            reward = json.loads(reward_json.read_text(encoding="utf-8"))
            self.assertEqual(set(reward), {"reward"})
            reward["details"] = json.loads(details_json.read_text(encoding="utf-8"))
            return reward

    @staticmethod
    def shift(clock: str, seconds: int) -> str:
        minutes, remainder = map(int, clock.split(":"))
        total = minutes * 60 + remainder + seconds
        return f"{total // 60:02d}:{total % 60:02d}"

    @staticmethod
    def move(cell: str, columns: int, rows: int) -> str:
        column = chr(ord(cell[0]) + columns)
        row = int(cell[1:]) + rows
        return f"{column}{row}"

    @staticmethod
    def opposite(cell: str) -> str:
        column = chr(ord("A") + (ord(cell[0]) - ord("A") + 7) % 14)
        row = (int(cell[1:]) - 1 + 7) % 14 + 1
        return f"{column}{row}"

    def test_oracle_and_null_anchors(self) -> None:
        self.assertEqual(self.score(self.oracle)["reward"], 1.0)
        self.assertEqual(self.score({"events": []})["reward"], 0.0)

    def test_one_correct_event_gets_small_partial_credit(self) -> None:
        result = self.score({"events": [self.oracle["events"][0]]})
        self.assertGreater(result["reward"], 0.0)
        self.assertLess(result["reward"], 0.06)
        self.assertEqual(
            result["details"]["components"]["exact_trajectory"]["matches"], 1
        )

    def test_one_wrong_endpoint_gets_no_reward(self) -> None:
        event = copy.deepcopy(
            next(e for e in self.oracle["events"] if e["death_cell"][0] < "N")
        )
        event["death_cell"] = self.move(event["death_cell"], 1, 0)
        result = self.score({"events": [event]})
        components = result["details"]["components"]
        self.assertEqual(result["reward"], 0.0)
        self.assertEqual(components["death_cell"]["matches"], 0)
        self.assertEqual(components["neighboring_trajectory"]["matches"], 1)

    def test_two_cells_away_is_not_neighboring(self) -> None:
        event = copy.deepcopy(
            next(e for e in self.oracle["events"] if e["cell_5s_before"][0] <= "L")
        )
        event["cell_5s_before"] = self.move(event["cell_5s_before"], 2, 0)
        result = self.score({"events": [event]})
        components = result["details"]["components"]
        self.assertEqual(result["reward"], 0.0)
        self.assertEqual(components["neighboring_trajectory"]["matches"], 0)
        self.assertEqual(components["killer_attribution"]["matches"], 1)

    def test_wrong_killer_gets_no_reward(self) -> None:
        event = copy.deepcopy(self.oracle["events"][0])
        event["killer"] = next(
            name for name in ["watson", "Nisha"] if name != event["killer"]
        )
        result = self.score({"events": [event]})
        self.assertEqual(result["reward"], 0.0)
        self.assertEqual(
            result["details"]["components"]["victim_attribution"]["matches"], 1
        )

    def test_public_identity_fields_receive_no_reward_without_correct_cells(
        self,
    ) -> None:
        identity_only = copy.deepcopy(self.oracle)
        for event in identity_only["events"]:
            for field in ("cell_10s_before", "cell_5s_before", "death_cell"):
                event[field] = self.opposite(event[field])
        result = self.score(identity_only)
        components = result["details"]["components"]
        self.assertEqual(components["killer_attribution"]["f1"], 1.0)
        self.assertEqual(components["cell_10s_before"]["matches"], 0)
        self.assertEqual(components["cell_5s_before"]["matches"], 0)
        self.assertEqual(components["death_cell"]["matches"], 0)
        self.assertEqual(components["exact_trajectory"]["matches"], 0)
        self.assertEqual(result["reward"], 0.0)

    def test_duplicates_reduce_precision(self) -> None:
        duplicated = {"events": self.oracle["events"] + [self.oracle["events"][0]]}
        result = self.score(duplicated)
        self.assertGreater(result["reward"], 0.98)
        self.assertLess(result["reward"], 1.0)

    def test_clock_boundary(self) -> None:
        shifted = copy.deepcopy(self.oracle)
        for event in shifted["events"]:
            event["clock"] = self.shift(event["clock"], 2)
        self.assertEqual(self.score(shifted)["reward"], 1.0)

        event = copy.deepcopy(self.oracle["events"][0])
        event["clock"] = self.shift(event["clock"], 3)
        self.assertEqual(self.score({"events": [event]})["reward"], 0.0)

    def test_missing_trajectory_field_invalidates_event(self) -> None:
        event = copy.deepcopy(self.oracle["events"][0])
        del event["cell_10s_before"]
        result = self.score({"events": [event]})
        self.assertEqual(result["reward"], 0.0)
        self.assertEqual(result["details"]["n_schema_valid_events"], 0)

    def test_grid_boundaries(self) -> None:
        event = copy.deepcopy(self.oracle["events"][0])
        for field in ("cell_10s_before", "cell_5s_before", "death_cell"):
            event[field] = "N14"
        result = self.score({"events": [event]})
        self.assertEqual(result["details"]["n_schema_valid_events"], 1)

        event["death_cell"] = "O14"
        result = self.score({"events": [event]})
        self.assertEqual(result["details"]["n_schema_valid_events"], 0)


if __name__ == "__main__":
    unittest.main()
