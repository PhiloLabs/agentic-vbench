#!/usr/bin/env python3
"""Boundary tests for the deterministic pilot scorer."""

from __future__ import annotations

import copy
import unittest

from verify_ledger import MAX_EVENTS_PER_EPISODE, score_documents


EVENT = {
    "timestamp_ms": 1000,
    "event_type": "key_pickup",
    "entity_id": "blue_key",
    "state": {
        "active_weapon": "pistol",
        "held_keys": ["blue_key"],
        "active_switches": [],
        "current_checkpoint": None,
    },
}
GROUND_TRUTH = {
    "episodes": [{"episode_id": "episode_01", "events": [EVENT]}]
}


class ScoreDocumentsTest(unittest.TestCase):
    def test_oracle_and_null_anchors(self) -> None:
        self.assertEqual(score_documents(GROUND_TRUTH, GROUND_TRUTH)["reward"], 1.0)
        null = {"episodes": [{"episode_id": "episode_01", "events": []}]}
        self.assertEqual(score_documents(GROUND_TRUTH, null)["reward"], 0.0)

    def test_timestamp_tolerance_is_inclusive(self) -> None:
        at_boundary = copy.deepcopy(GROUND_TRUTH)
        at_boundary["episodes"][0]["events"][0]["timestamp_ms"] += 750
        self.assertEqual(
            score_documents(GROUND_TRUTH, at_boundary)["reward"], 1.0
        )

        outside = copy.deepcopy(at_boundary)
        outside["episodes"][0]["events"][0]["timestamp_ms"] += 1
        self.assertEqual(score_documents(GROUND_TRUTH, outside)["reward"], 0.0)

    def test_duplicate_prediction_is_a_false_positive(self) -> None:
        duplicate = copy.deepcopy(GROUND_TRUTH)
        duplicate["episodes"][0]["events"].append(copy.deepcopy(EVENT))
        self.assertEqual(
            score_documents(GROUND_TRUTH, duplicate)["reward"], 0.666667
        )

    def test_unknown_empty_episode_cannot_inflate_reward(self) -> None:
        prediction = copy.deepcopy(GROUND_TRUTH)
        prediction["episodes"].append(
            {"episode_id": "episode_unknown", "events": []}
        )
        result = score_documents(GROUND_TRUTH, prediction)
        self.assertEqual(result["reward"], 0.0)
        self.assertIn("unknown episode_id", result["details"]["parse_error"])

    def test_duplicate_set_members_do_not_match(self) -> None:
        prediction = copy.deepcopy(GROUND_TRUTH)
        prediction["episodes"][0]["events"][0]["state"]["held_keys"].append(
            "blue_key"
        )
        self.assertEqual(score_documents(GROUND_TRUTH, prediction)["reward"], 0.0)

    def test_negative_tolerance_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-negative"):
            score_documents(GROUND_TRUTH, GROUND_TRUTH, tolerance_ms=-1)

    def test_oversized_event_list_scores_zero(self) -> None:
        prediction = {
            "episodes": [
                {
                    "episode_id": "episode_01",
                    "events": [EVENT] * (MAX_EVENTS_PER_EPISODE + 1),
                }
            ]
        }
        result = score_documents(GROUND_TRUTH, prediction)
        self.assertEqual(result["reward"], 0.0)
        self.assertIn("too many events", result["details"]["parse_error"])

    def test_non_monotonic_timestamps_score_zero(self) -> None:
        prediction = copy.deepcopy(GROUND_TRUTH)
        second_event = copy.deepcopy(EVENT)
        second_event["timestamp_ms"] -= 1
        prediction["episodes"][0]["events"].append(second_event)
        result = score_documents(GROUND_TRUTH, prediction)
        self.assertEqual(result["reward"], 0.0)
        self.assertIn("non-decreasing", result["details"]["parse_error"])

    def test_extra_schema_field_scores_zero(self) -> None:
        prediction = copy.deepcopy(GROUND_TRUTH)
        prediction["unexpected"] = True
        result = score_documents(GROUND_TRUTH, prediction)
        self.assertEqual(result["reward"], 0.0)
        self.assertIn("exactly", result["details"]["parse_error"])

    def test_empty_ground_truth_episode_is_rejected(self) -> None:
        empty_ground_truth = {
            "episodes": [{"episode_id": "episode_01", "events": []}]
        }
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            score_documents(empty_ground_truth, empty_ground_truth)


if __name__ == "__main__":
    unittest.main()
