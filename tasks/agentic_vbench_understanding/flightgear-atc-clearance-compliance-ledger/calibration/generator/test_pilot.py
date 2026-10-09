from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from build_full_dataset import make_config
from derive_ground_truth import derive_event, stable_completion, sustained_rate_start
from pilot_lib import AircraftState, KinematicController, angular_delta_deg, angular_error_deg
from run_pilot import build_control_actions, resolve_commands


JUDGE_PATH = Path(__file__).resolve().parents[2] / "steps/solve/tests/judge.py"
JUDGE_SPEC = importlib.util.spec_from_file_location("flightgear_judge", JUDGE_PATH)
assert JUDGE_SPEC and JUDGE_SPEC.loader
judge = importlib.util.module_from_spec(JUDGE_SPEC)
JUDGE_SPEC.loader.exec_module(judge)


CONTROLLER_CONFIG = {
    "heading_rate_deg_s": 4.0,
    "heading_capture_rate_deg_s": 1.0,
    "heading_capture_zone_deg": 8.0,
    "altitude_rate_fpm": 600.0,
    "altitude_capture_rate_fpm": 300.0,
    "altitude_capture_zone_ft": 100.0,
    "airspeed_rate_kt_s": 2.0,
    "airspeed_capture_rate_kt_s": 0.5,
    "airspeed_capture_zone_kt": 8.0,
    "max_bank_deg": 18.0,
    "max_pitch_deg": 6.0,
}

RULES = {
    "heading_execution_rate_deg_s": 0.5,
    "heading_completion_tolerance_deg": 8.0,
    "altitude_execution_rate_fpm": 100.0,
    "altitude_completion_tolerance_ft": 100.0,
    "execution_hold_s": 2.0,
    "completion_hold_s": 3.0,
    "late_response_s": 12.0,
    "issued_time_tolerance_s": 2.0,
    "event_time_tolerance_s": 4.0,
}


def event(index: int, issued: float) -> dict[str, object]:
    return {
        "clearance_index": index,
        "issued_time_s": issued,
        "command_type": "turn_right_heading",
        "target_value": 20,
        "target_unit": "degrees",
        "issue_altitude_ft": 3500,
        "issue_heading_deg": 350,
        "issue_airspeed_kt": 100,
        "maximum_commanded_progress": 30,
        "execution_altitude_ft": 3500,
        "execution_heading_deg": 351,
        "execution_airspeed_kt": 100,
        "completion_altitude_ft": 3500,
        "completion_heading_deg": 20,
        "completion_airspeed_kt": 100,
        "ending_altitude_ft": 3500,
        "ending_heading_deg": 20,
        "ending_airspeed_kt": 100,
        "execution_start_time_s": issued + 1,
        "completion_time_s": issued + 5,
        "status": "complied",
        "superseded_by_index": None,
        "overshoot_bucket": "none",
    }


class GeometryTests(unittest.TestCase):
    def test_heading_wraparound(self) -> None:
        self.assertEqual(angular_delta_deg(350, 10), 20)
        self.assertEqual(angular_delta_deg(10, 350), -20)
        self.assertEqual(angular_error_deg(359, 1), 2)


class ControllerTests(unittest.TestCase):
    def test_controller_converges_all_dimensions(self) -> None:
        controller = KinematicController(AircraftState(3500, 350, 120), CONTROLLER_CONFIG)
        controller.target_heading_deg = 20
        controller.target_altitude_ft = 3800
        controller.target_airspeed_kt = 100
        for _ in range(600):
            controller.update(0.1)
        self.assertLess(angular_error_deg(controller.state.heading_deg, 20), 0.01)
        self.assertAlmostEqual(controller.state.altitude_ft, 3800, places=3)
        self.assertAlmostEqual(controller.state.airspeed_kt, 100, places=3)
        self.assertAlmostEqual(controller.state.roll_deg, 0, places=3)
        self.assertAlmostEqual(controller.state.pitch_deg, 0, places=3)

    def test_heading_controller_preserves_commanded_direction(self) -> None:
        controller = KinematicController(AircraftState(3500, 306, 120), CONTROLLER_CONFIG)
        controller.target_heading_deg = 323
        controller.heading_direction = -1.0
        controller.update(1.0)
        self.assertLess(controller.state.heading_deg, 306)

    def test_heading_overshoot_settle_reverses_direction(self) -> None:
        commands = resolve_commands(
            {
                "commands": [
                    {
                        "issue_time_s": 1,
                        "command_type": "turn_right_heading",
                        "target": {"mode": "delta_from_previous", "value": 30},
                        "behavior": "overshoot",
                        "overshoot_amount": 12,
                        "overshoot_duration_s": 20,
                    }
                ]
            },
            100,
            3000,
            100,
        )
        commands[0]["audio_end_time_s"] = 2.0
        actions = build_control_actions(commands)
        self.assertEqual(actions[0]["heading_direction"], 1.0)
        self.assertEqual(actions[1]["heading_direction"], -1.0)


class DatasetScenarioTests(unittest.TestCase):
    def test_outcome_order_is_not_repeated_across_segments(self) -> None:
        patterns = {
            tuple(command["expected_status"] for command in make_config(index)["commands"])
            for index in range(1, 6)
        }
        self.assertEqual(len(patterns), 5)


class DerivationTests(unittest.TestCase):
    @staticmethod
    def speed_command(
        *,
        issue: float = 0.0,
        control_applied: float | None = None,
        target: float = 120.0,
        command_type: str = "accelerate",
    ) -> dict[str, object]:
        result = {
            "clearance_index": 1,
            "issued_time_s": issue,
            "command_type": command_type,
            "target_value": target,
            "target_unit": "knots",
        }
        if control_applied is not None:
            result["control_applied_time_s"] = control_applied
        return result

    @staticmethod
    def speed_samples(points: list[tuple[float, float]]) -> list[dict[str, float]]:
        return [
            {
                "time_s": time_s,
                "airspeed_kt": value,
                "indicated_airspeed_kt": value,
                "fdm_vias_kt": value,
                "indicated_heading_deg": 0.0,
                "indicated_altitude_ft": 3000.0,
            }
            for time_s, value in points
        ]

    def test_stable_completion_rejects_transient_crossing(self) -> None:
        samples = [
            {"time_s": 0.0, "value": 20.0},
            {"time_s": 1.0, "value": 5.0},
            {"time_s": 2.0, "value": 1.0},
            {"time_s": 3.0, "value": 3.0},
            {"time_s": 4.0, "value": 12.0},
        ]
        self.assertIsNone(stable_completion(samples, lambda sample: sample["value"] <= 5, 2.0))

    def test_stable_completion_accepts_remainder_hold(self) -> None:
        samples = [
            {"time_s": 0.0, "value": 20.0},
            {"time_s": 1.0, "value": 4.0},
            {"time_s": 2.0, "value": 3.0},
            {"time_s": 3.0, "value": 2.0},
            {"time_s": 4.0, "value": 1.0},
        ]
        self.assertEqual(stable_completion(samples, lambda sample: sample["value"] <= 5, 2.0), 1.0)

    def test_rate_start_tolerates_duplicate_samples(self) -> None:
        samples = [
            {"time_s": 0.0, "value": 0.0},
            {"time_s": 0.5, "value": 0.0},
            {"time_s": 1.0, "value": 2.0},
            {"time_s": 2.0, "value": 5.0},
        ]
        self.assertEqual(
            sustained_rate_start(
                samples,
                lambda sample: sample["value"],
                lambda start, finish: finish - start,
                1.0,
                1.0,
                2.0,
            ),
            0.0,
        )

    def test_rate_start_rejects_last_moment_jump(self) -> None:
        samples = [
            {"time_s": 0.0, "value": 0.0},
            {"time_s": 1.0, "value": 0.0},
            {"time_s": 1.9, "value": 0.0},
            {"time_s": 2.0, "value": 3.0},
        ]
        self.assertIsNone(
            sustained_rate_start(
                samples,
                lambda sample: sample["value"],
                lambda start, finish: finish - start,
                1.0,
                1.0,
                2.0,
            )
        )

    def test_delayed_response_is_complied_late(self) -> None:
        command = self.speed_command(control_applied=16.0)
        samples = self.speed_samples(
            [(16, 100), (18, 104), (20, 108), (22, 112), (24, 116), (26, 120), (30, 120)]
        )
        result = derive_event(command, None, samples, RULES)
        self.assertEqual(result["status"], "complied_late")

    def test_wrong_direction_is_violated(self) -> None:
        command = self.speed_command(target=120)
        samples = self.speed_samples([(0, 100), (2, 96), (4, 92), (8, 88)])
        result = derive_event(command, None, samples, RULES)
        self.assertEqual(result["status"], "violated")
        self.assertIsNone(result["execution_start_time_s"])

    def test_unfinished_command_is_superseded(self) -> None:
        command = self.speed_command(target=140)
        next_command = self.speed_command(issue=5, target=100, command_type="decelerate")
        next_command["clearance_index"] = 2
        samples = self.speed_samples([(0, 100), (2, 104), (4, 108), (6, 105)])
        result = derive_event(command, next_command, samples, RULES)
        self.assertEqual(result["status"], "superseded")
        self.assertEqual(result["superseded_by_index"], 2)

    def test_large_speed_overshoot_is_bucketed(self) -> None:
        command = self.speed_command(target=120)
        samples = self.speed_samples(
            [(0, 100), (2, 106), (4, 112), (6, 120), (8, 132), (10, 125), (12, 120), (16, 120)]
        )
        result = derive_event(command, None, samples, RULES)
        self.assertEqual(result["status"], "complied")
        self.assertEqual(result["overshoot_bucket"], "large")


class ScorerTests(unittest.TestCase):
    def test_duplicate_prediction_is_false_positive(self) -> None:
        gold = {"clearances": [event(1, 10.0)]}
        duplicate = dict(event(1, 10.0))
        duplicate["clearance_index"] = 2
        prediction = {"clearances": [event(1, 10.0), duplicate]}
        result = judge.score(prediction, gold)
        self.assertEqual(result["details"]["strict_matches"], 1)
        self.assertEqual(result["details"]["false_positives"], 1)
        self.assertEqual(result["details"]["clearance_chain_f1"], 0.6667)
        self.assertEqual(result["reward"], 0.0667)

    def test_invalid_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prediction.json"
            path.write_text("{", encoding="utf-8")
            with self.assertRaises(ValueError):
                judge.load_json(path)

    def test_extra_fields_are_rejected(self) -> None:
        invalid = {"clearances": [dict(event(1, 10.0), unexpected=True)]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prediction.json"
            path.write_text(json.dumps(invalid), encoding="utf-8")
            with self.assertRaises(ValueError):
                judge.load_json(path)


if __name__ == "__main__":
    unittest.main()
