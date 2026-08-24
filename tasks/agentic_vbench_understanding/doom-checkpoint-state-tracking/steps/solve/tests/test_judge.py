#!/usr/bin/env python3

from __future__ import annotations

import copy
import unittest

from judge import score


STATE = {
    "active_weapon": "pistol",
    "held_keys": ["blue_key", "red_key"],
    "active_switches": ["switch_amber"],
    "open_doors": ["door_blue"],
    "current_checkpoint": "checkpoint_alpha",
}
EVENT = {
    "timestamp_ms": 1000,
    "event_type": "key_pickup",
    "entity_id": "blue_key",
    "state": STATE,
}


def document(events: list[dict[str, object]]) -> dict[str, object]:
    return {
        "episodes": [
            {
                "episode_id": f"episode_{index:02d}",
                "events": copy.deepcopy(events),
            }
            for index in range(1, 7)
        ]
    }


class ScoreTest(unittest.TestCase):
    def test_oracle_and_null(self) -> None:
        ground_truth = document([EVENT])
        self.assertEqual(score(ground_truth, ground_truth)["reward"], 1.0)
        self.assertEqual(score(ground_truth, document([]))["reward"], 0.0)

    def test_one_wrong_field_receives_gated_credit(self) -> None:
        ground_truth = document([EVENT])
        prediction = copy.deepcopy(ground_truth)
        prediction["episodes"][0]["events"][0]["state"]["held_keys"] = [
            "blue_key"
        ]
        for episode in prediction["episodes"][1:]:
            episode["events"][0]["state"]["held_keys"] = ["blue_key"]
        result = score(ground_truth, prediction)
        self.assertEqual(result["reward"], 0.08)
        episode = result["details"]["episodes"]["episode_01"]
        self.assertEqual(episode["full_event_f1"], 0.0)
        self.assertEqual(episode["gated_field_f1"], 0.8)
        self.assertEqual(
            episode["field_exact_matches"]["held_keys"],
            0,
        )

    def test_field_credit_is_gated_by_event_identity(self) -> None:
        ground_truth = document([EVENT])
        prediction = copy.deepcopy(ground_truth)
        for episode in prediction["episodes"]:
            episode["events"][0]["entity_id"] = "red_key"
        self.assertEqual(score(ground_truth, prediction)["reward"], 0.0)

    def test_set_fields_require_complete_equality(self) -> None:
        ground_truth = document([EVENT])
        prediction = copy.deepcopy(ground_truth)
        for episode in prediction["episodes"]:
            episode["events"][0]["state"]["held_keys"] = ["blue_key"]
        result = score(ground_truth, prediction)
        episode = result["details"]["episodes"]["episode_01"]
        self.assertEqual(episode["field_f1"]["held_keys"], 0.0)
        self.assertEqual(result["reward"], 0.08)

    def test_false_positive_uses_event_f1_denominator(self) -> None:
        ground_truth = document([EVENT])
        extra = copy.deepcopy(EVENT)
        extra["timestamp_ms"] = 2000
        prediction = document([EVENT, extra])
        self.assertEqual(score(ground_truth, prediction)["reward"], 0.666667)

    def test_timestamp_tolerance_is_inclusive(self) -> None:
        ground_truth = document([EVENT])
        boundary = copy.deepcopy(ground_truth)
        for episode in boundary["episodes"]:
            episode["events"][0]["timestamp_ms"] += 750
        self.assertEqual(score(ground_truth, boundary)["reward"], 1.0)
        outside = copy.deepcopy(boundary)
        for episode in outside["episodes"]:
            episode["events"][0]["timestamp_ms"] += 1
        self.assertEqual(score(ground_truth, outside)["reward"], 0.0)

    def test_alignment_tie_breaks_by_timestamp_before_state(self) -> None:
        earlier = copy.deepcopy(EVENT)
        later = copy.deepcopy(EVENT)
        later["timestamp_ms"] = 1500
        later["state"]["held_keys"] = ["red_key"]
        prediction_event = copy.deepcopy(earlier)
        prediction_event["timestamp_ms"] = 1400
        result = score(
            document([earlier, later]),
            document([prediction_event]),
        )
        episode = result["details"]["episodes"]["episode_01"]
        self.assertEqual(episode["identity_time_matches"], 1)
        self.assertEqual(episode["full_state_matches"], 0)
        self.assertEqual(episode["field_exact_matches"]["held_keys"], 0)
        self.assertEqual(result["reward"], 0.053333)

    def test_missing_episode_only_loses_its_reward(self) -> None:
        ground_truth = document([EVENT])
        prediction = copy.deepcopy(ground_truth)
        prediction["episodes"].pop(0)
        result = score(ground_truth, prediction)
        episode = result["details"]["episodes"]["episode_01"]
        self.assertEqual(result["reward"], 0.833333)
        self.assertEqual(episode["predicted_events"], 0)
        self.assertEqual(episode["validation_errors"], ["missing episode"])

    def test_invalid_episode_only_loses_its_reward(self) -> None:
        ground_truth = document([EVENT])
        prediction = copy.deepcopy(ground_truth)
        prediction["episodes"][0]["unexpected"] = True
        result = score(ground_truth, prediction)
        episode = result["details"]["episodes"]["episode_01"]
        self.assertEqual(result["reward"], 0.833333)
        self.assertEqual(episode["predicted_events"], 0)
        self.assertEqual(
            episode["validation_errors"],
            ["invalid episode schema"],
        )

    def test_invalid_episode_id_does_not_discard_siblings(self) -> None:
        ground_truth = document([EVENT])
        prediction = copy.deepcopy(ground_truth)
        prediction["episodes"][0]["episode_id"] = []
        result = score(ground_truth, prediction)
        episode = result["details"]["episodes"]["episode_01"]
        self.assertEqual(result["reward"], 0.833333)
        self.assertEqual(
            result["details"]["validation_errors"],
            ["episodes[0]: unknown episode"],
        )
        self.assertEqual(episode["validation_errors"], ["missing episode"])

    def test_duplicate_episode_only_loses_its_reward(self) -> None:
        ground_truth = document([EVENT])
        prediction = copy.deepcopy(ground_truth)
        prediction["episodes"].append(
            copy.deepcopy(prediction["episodes"][0])
        )
        result = score(ground_truth, prediction)
        episode = result["details"]["episodes"]["episode_01"]
        self.assertEqual(result["reward"], 0.833333)
        self.assertEqual(episode["predicted_events"], 0)
        self.assertEqual(
            episode["validation_errors"],
            ["duplicate episode entries at indices 0, 6"],
        )

    def test_invalid_event_is_dropped_without_losing_episode(self) -> None:
        events = []
        for timestamp in (1000, 2000, 3000):
            event = copy.deepcopy(EVENT)
            event["timestamp_ms"] = timestamp
            events.append(event)
        ground_truth = document(events)
        prediction = copy.deepcopy(ground_truth)
        prediction["episodes"][0]["events"][1]["state"][
            "active_weapon"
        ] = []
        result = score(ground_truth, prediction)
        episode = result["details"]["episodes"]["episode_01"]
        self.assertEqual(result["reward"], 0.966667)
        self.assertEqual(episode["predicted_events"], 2)
        self.assertEqual(episode["episode_reward"], 0.8)
        self.assertEqual(
            episode["validation_errors"],
            ["events[1]: unknown active weapon"],
        )

    def test_backward_event_does_not_poison_later_events(self) -> None:
        events = []
        for timestamp in (1000, 2000, 3000):
            event = copy.deepcopy(EVENT)
            event["timestamp_ms"] = timestamp
            events.append(event)
        ground_truth = document(events)
        prediction = copy.deepcopy(ground_truth)
        prediction["episodes"][0]["events"][1]["timestamp_ms"] = 500
        result = score(ground_truth, prediction)
        episode = result["details"]["episodes"]["episode_01"]
        self.assertEqual(result["reward"], 0.966667)
        self.assertEqual(episode["predicted_events"], 2)
        self.assertEqual(episode["episode_reward"], 0.8)
        self.assertEqual(
            episode["validation_errors"],
            ["events[1]: invalid event timestamp"],
        )

    def test_oversized_event_array_only_loses_its_episode(self) -> None:
        ground_truth = document([EVENT])
        prediction = copy.deepcopy(ground_truth)
        events = []
        for timestamp in range(101):
            event = copy.deepcopy(EVENT)
            event["timestamp_ms"] = timestamp
            events.append(event)
        prediction["episodes"][0]["events"] = events
        result = score(ground_truth, prediction)
        episode = result["details"]["episodes"]["episode_01"]
        self.assertEqual(result["reward"], 0.833333)
        self.assertEqual(episode["predicted_events"], 0)
        self.assertEqual(
            episode["validation_errors"],
            ["invalid events array"],
        )

    def test_invalid_prediction_scores_zero(self) -> None:
        result = score(document([EVENT]), {"unexpected": []})
        self.assertEqual(result["reward"], 0.0)
        self.assertEqual(
            result["details"]["parse_error"],
            "invalid top-level schema",
        )


if __name__ == "__main__":
    unittest.main()
