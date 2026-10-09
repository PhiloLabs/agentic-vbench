#!/usr/bin/env python3

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import judge


class HierarchicalScoringTests(unittest.TestCase):
    def setUp(self):
        self.oracle = copy.deepcopy(judge.REFERENCE_EVENTS)

    def scored(self, predictions):
        return judge.score_predictions(predictions)

    def reward(self, predictions):
        return self.scored(predictions)[0]

    def test_oracle_and_empty_anchors(self):
        reward, details = self.scored(self.oracle)
        self.assertEqual(reward, 1.0)
        self.assertEqual(details["scorer_version"], "hierarchical-bottleneck-v1")
        self.assertEqual(details["fully_correct_events"], 16)
        self.assertEqual(details["shot_fields_correct_ordered"], 224)
        self.assertEqual(details["detail_fields_correct"], 368)
        self.assertEqual(details["detail_accuracy"], 1.0)
        self.assertEqual(details["shot_accuracy"], 1.0)
        self.assertEqual(details["exact_event_matches_ordered"], 16)
        self.assertEqual(details["exact_event_f1"], 1.0)
        self.assertEqual(details["hierarchical_precision"], 1.0)
        self.assertEqual(details["hierarchical_recall"], 1.0)
        self.assertEqual(details["hierarchical_event_f1"], 1.0)
        self.assertEqual(self.reward([]), 0.0)

    def test_identity_without_required_layers_scores_zero(self):
        predictions = [
            {field: event[field] for field in judge.IDENTITY_FIELDS}
            for event in self.oracle
        ]
        reward, details = self.scored(predictions)
        self.assertEqual(reward, 0.0)
        self.assertEqual(details["identity_f1"], 1.0)
        self.assertEqual(details["summary_accuracy"], 0.0)
        self.assertEqual(details["shot_f1"], 0.0)

    def test_summary_layer_is_mandatory_even_with_perfect_shots(self):
        predictions = [
            {
                **{field: event[field] for field in judge.IDENTITY_FIELDS},
                "shots": copy.deepcopy(event["shots"]),
            }
            for event in self.oracle
        ]
        reward, details = self.scored(predictions)
        self.assertEqual(reward, 0.0)
        self.assertEqual(details["identity_f1"], 1.0)
        self.assertEqual(details["summary_accuracy"], 0.0)
        self.assertEqual(details["shot_accuracy"], 1.0)

    def test_four_wrong_summary_fields_receive_partial_credit(self):
        predictions = copy.deepcopy(self.oracle)
        for event in predictions:
            event["first_serve_in"] = not event["first_serve_in"]
            event["serve_direction"] = "unknown"
            event["rally_shots"] += 100
            event["terminal_player"] = (
                "Alex De Minaur"
                if event["terminal_player"] == "Daniil Medvedev"
                else "Daniil Medvedev"
            )
        reward, details = self.scored(predictions)
        self.assertEqual(reward, 0.5556)
        self.assertEqual(details["exact_event_matches_ordered"], 0)
        self.assertEqual(details["hierarchical_event_f1"], 0.5556)

    def test_outcome_is_summary_not_identity(self):
        predictions = copy.deepcopy(self.oracle)
        predictions[0]["outcome"] = "converted"
        reward, details = self.scored(predictions)
        self.assertEqual(reward, 0.9931)
        self.assertEqual(details["identity_matches_ordered"], 16)
        self.assertEqual(details["exact_event_matches_ordered"], 15)
        self.assertEqual(details["summary_fields_correct"], 143)
        self.assertEqual(details["hierarchical_event_f1"], 0.9931)

    def test_exact_event_f1_requires_every_layer_on_the_same_event(self):
        predictions = copy.deepcopy(self.oracle[:3])
        predictions[1]["outcome"] = "saved"
        predictions[2]["shots"][0]["direction"] = "unknown"

        reward, details = self.scored(predictions)
        self.assertEqual(reward, 0.2865)
        self.assertEqual(details["identity_matches_ordered"], 3)
        self.assertEqual(details["exact_event_matches_ordered"], 1)
        self.assertEqual(details["exact_event_precision"], 0.3333)
        self.assertEqual(details["exact_event_recall"], 0.0625)
        self.assertEqual(details["exact_event_f1"], 0.1053)
        self.assertGreater(reward, details["exact_event_f1"])

    def test_non_bottleneck_improvement_has_a_documented_plateau(self):
        prediction = copy.deepcopy(self.oracle[0])
        for shot in prediction["shots"]:
            shot["direction"] = "unknown"
        lower_summary = copy.deepcopy(prediction)
        lower_summary["outcome"] = "converted"

        lower_reward, lower_details = self.scored([lower_summary])
        higher_reward, higher_details = self.scored([prediction])
        self.assertEqual(lower_reward, higher_reward)
        self.assertLess(
            lower_details["summary_accuracy"],
            higher_details["summary_accuracy"],
        )
        self.assertEqual(lower_details["shot_accuracy"], 0.5)
        self.assertEqual(higher_details["shot_accuracy"], 0.5)

    def test_formula_and_strict_diagnostic_are_reported(self):
        _, details = self.scored(self.oracle)
        self.assertEqual(
            details["formula"],
            "2 * sum(min(per_event_summary_accuracy, "
            "per_event_ordered_shot_accuracy)) "
            "/ (n_predicted + n_reference)",
        )
        self.assertEqual(
            details["exact_event_formula"],
            "2 * exact_ordered_event_matches "
            "/ (n_predicted + n_reference)",
        )

    def test_partial_submission_and_duplicate_penalties(self):
        self.assertEqual(self.reward(self.oracle[:1]), 0.1176)
        predictions = copy.deepcopy(self.oracle)
        predictions.insert(0, {
            field: predictions[0][field] for field in judge.IDENTITY_FIELDS
        })
        self.assertEqual(self.reward(predictions), 0.9697)

    def test_identity_corruption_cannot_improve_a_partial_submission(self):
        identity_only = {
            field: self.oracle[1][field] for field in judge.IDENTITY_FIELDS
        }
        true_identity = [copy.deepcopy(self.oracle[0]), identity_only]
        false_identity = copy.deepcopy(true_identity)
        false_identity[1]["set"] = 99
        self.assertEqual(self.reward(true_identity), 0.1111)
        self.assertEqual(self.reward(false_identity), 0.1111)
        self.assertEqual(
            self.scored(true_identity)[1]["exact_event_matches_ordered"], 1
        )
        self.assertGreater(
            self.scored(true_identity)[1]["identity_matches_ordered"],
            self.scored(false_identity)[1]["identity_matches_ordered"],
        )

    def test_summary_and_shot_layers_cannot_be_pooled_across_events(self):
        summary_only = copy.deepcopy(self.oracle[0])
        del summary_only["shots"]
        shots_only = {
            **{
                field: self.oracle[1][field]
                for field in judge.IDENTITY_FIELDS
            },
            "shots": copy.deepcopy(self.oracle[1]["shots"]),
        }
        reward, details = self.scored([summary_only, shots_only])
        self.assertEqual(reward, 0.0)
        self.assertEqual(details["identity_matches_ordered"], 2)
        self.assertEqual(details["hierarchical_true_positive_credit"], 0.0)

    def test_missing_one_summary_field(self):
        predictions = copy.deepcopy(self.oracle)
        del predictions[0][judge.SUMMARY_FIELDS[0]]
        reward, details = self.scored(predictions)
        self.assertEqual(reward, 0.9931)
        self.assertEqual(details["summary_fields_present"], 143)
        self.assertEqual(details["summary_fields_predicted"], 144)
        self.assertEqual(details["hierarchical_event_f1"], 0.9931)

    def test_extra_event_field_is_diagnosed_without_erasing_credit(self):
        predictions = copy.deepcopy(self.oracle)
        predictions[0]["explanation"] = "not part of the schema"
        reward, details = self.scored(predictions)
        self.assertEqual(reward, 1.0)
        self.assertEqual(details["schema_issue_events"], 1)
        self.assertEqual(details["invalid_identity_events"], 0)

    def test_identity_types_are_exact(self):
        predictions = copy.deepcopy(self.oracle)
        predictions[0]["set"] = True
        self.assertEqual(self.reward(predictions), 0.9375)

    def test_chronological_event_order_is_scored(self):
        predictions = copy.deepcopy(self.oracle)
        predictions[0], predictions[1] = predictions[1], predictions[0]
        self.assertEqual(self.reward(predictions), 0.9375)

    def test_missing_shot_layer_loses_only_shot_field_credit(self):
        predictions = copy.deepcopy(self.oracle)
        for event in predictions:
            del event["shots"]
        reward, details = self.scored(predictions)
        self.assertEqual(reward, 0.0)
        self.assertEqual(details["identity_f1"], 1.0)
        self.assertEqual(details["summary_accuracy"], 1.0)
        self.assertEqual(details["shot_f1"], 0.0)
        self.assertEqual(details["detail_fields_correct"], 144)

    def test_one_wrong_shot_field_loses_one_atomic_match(self):
        predictions = copy.deepcopy(self.oracle)
        predictions[0]["shots"][0]["direction"] = "unknown"
        reward, details = self.scored(predictions)
        self.assertEqual(reward, 0.9961)
        self.assertEqual(details["shot_fields_correct_ordered"], 223)
        self.assertEqual(details["hierarchical_event_f1"], 0.9961)

    def test_shot_insert_delete_and_order_are_scored(self):
        inserted = copy.deepcopy(self.oracle)
        inserted[0]["shots"].insert(0, copy.deepcopy(inserted[0]["shots"][0]))
        inserted_reward, inserted_details = self.scored(inserted)
        self.assertEqual(inserted_reward, 0.9931)
        self.assertEqual(inserted_details["hierarchical_event_f1"], 0.9931)

        deleted = copy.deepcopy(self.oracle)
        del deleted[0]["shots"][0]
        deleted_reward, deleted_details = self.scored(deleted)
        self.assertEqual(deleted_reward, 0.9922)
        self.assertEqual(deleted_details["hierarchical_event_f1"], 0.9922)

        swapped = copy.deepcopy(self.oracle)
        swapped[0]["shots"][0], swapped[0]["shots"][1] = (
            swapped[0]["shots"][1],
            swapped[0]["shots"][0],
        )
        swapped_reward, swapped_details = self.scored(swapped)
        self.assertEqual(swapped_reward, 0.9922)
        self.assertEqual(swapped_details["hierarchical_event_f1"], 0.9922)

    def test_cross_event_shot_denominators_cannot_cancel(self):
        inserted = copy.deepcopy(self.oracle)
        inserted[0]["shots"].append({
            "stroke": "not_a_valid_value",
            "direction": "not_a_valid_value",
        })
        deleted = copy.deepcopy(self.oracle)
        del deleted[5]["shots"][-1]
        combined = copy.deepcopy(inserted)
        del combined[5]["shots"][-1]

        self.assertEqual(self.reward(inserted), 0.9931)
        self.assertEqual(self.reward(deleted), 0.9975)
        combined_reward, combined_details = self.scored(combined)
        self.assertEqual(combined_reward, 0.9906)
        self.assertEqual(combined_details["shot_fields_correct_ordered"], 222)
        self.assertEqual(combined_details["shot_denominator"], 226)
        self.assertEqual(combined_details["shot_accuracy"], 0.9823)
        self.assertEqual(combined_details["hierarchical_event_f1"], 0.9906)
        self.assertLess(self.reward(combined), self.reward(inserted))
        self.assertLess(self.reward(combined), self.reward(deleted))

    def test_extra_shot_key_is_diagnosed_without_erasing_credit(self):
        predictions = copy.deepcopy(self.oracle)
        predictions[0]["shots"][0]["note"] = "extra key"
        reward, details = self.scored(predictions)
        self.assertEqual(reward, 1.0)
        self.assertEqual(details["shot_schema_issue_entries"], 1)
        self.assertEqual(details["invalid_shot_entries"], 0)

    def test_wrong_shot_field_type_loses_only_that_field(self):
        predictions = copy.deepcopy(self.oracle)
        predictions[0]["shots"][0]["stroke"] = True
        reward, details = self.scored(predictions)
        self.assertEqual(reward, 0.9961)
        self.assertEqual(details["invalid_shot_entries"], 1)
        self.assertEqual(details["shot_fields_correct_ordered"], 223)
        self.assertEqual(details["hierarchical_event_f1"], 0.9961)

    def test_missing_and_wrong_fields_have_the_same_denominator(self):
        missing_summary = copy.deepcopy(self.oracle)
        del missing_summary[0]["outcome"]
        wrong_summary = copy.deepcopy(self.oracle)
        wrong_summary[0]["outcome"] = "not_a_valid_value"
        self.assertEqual(self.reward(missing_summary), self.reward(wrong_summary))

        missing_shots = copy.deepcopy(self.oracle)
        wrong_shots = copy.deepcopy(self.oracle)
        for event in missing_shots:
            del event["shots"]
        for event in wrong_shots:
            for shot in event["shots"]:
                shot["stroke"] = "not_a_valid_value"
                shot["direction"] = "not_a_valid_value"
        self.assertEqual(self.reward(missing_shots), self.reward(wrong_shots))

    def test_strokes_keep_credit_when_every_direction_is_wrong(self):
        predictions = copy.deepcopy(self.oracle)
        for event in predictions:
            for shot in event["shots"]:
                shot["direction"] = "unknown"
        reward, details = self.scored(predictions)
        self.assertEqual(reward, 0.5)
        self.assertEqual(details["shot_fields_correct_ordered"], 112)
        self.assertEqual(details["hierarchical_event_f1"], 0.5)

    def test_duplicate_alignment_selects_best_rate_in_either_order(self):
        noisy = copy.deepcopy(self.oracle[0])
        noisy["shots"].extend([
            {"stroke": "unknown", "direction": "unknown"}
            for _ in range(100)
        ])
        clean = copy.deepcopy(self.oracle[0])
        clean["outcome"] = "converted"
        for predictions in ([noisy, clean], [clean, noisy]):
            reward, details = self.scored(predictions)
            self.assertEqual(reward, 0.0988)
            self.assertEqual(details["hierarchical_event_f1"], 0.0988)
            self.assertEqual(details["detail_accuracy"], 0.96)
            self.assertEqual(details["duplicate_identity_events"], 1)

    def test_extra_root_key_is_diagnosed_without_erasing_credit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            solution = root / "solution.json"
            reward_json = root / "reward.json"
            reward_txt = root / "reward.txt"
            solution.write_text(json.dumps({
                "break_points": self.oracle,
                "metadata": {"note": "ignored extra root key"},
            }))
            argv = [
                "judge.py",
                "--solution", str(solution),
                "--reward-json", str(reward_json),
                "--reward-txt", str(reward_txt),
            ]
            with mock.patch.object(sys, "argv", argv):
                judge.main()
            payload = json.loads(reward_json.read_text())
            self.assertEqual(payload["reward"], 1.0)
            self.assertTrue(payload["details"]["root_schema_issue"])

    def test_resource_limits_reject_oversized_sequences(self):
        with self.assertRaisesRegex(ValueError, "exceeds 512 entries"):
            prediction = copy.deepcopy(self.oracle[0])
            prediction["shots"] = [
                {"stroke": "serve", "direction": "wide"}
                for _ in range(judge.MAX_SHOTS_PER_EVENT + 1)
            ]
            self.scored([prediction])

        with self.assertRaisesRegex(ValueError, "exceeds 256 events"):
            self.scored([
                copy.deepcopy(self.oracle[0])
                for _ in range(judge.MAX_PREDICTED_EVENTS + 1)
            ])

    def test_cli_resource_limit_fails_closed_to_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            solution = root / "solution.json"
            reward_json = root / "reward.json"
            reward_txt = root / "reward.txt"
            solution.write_text(json.dumps({
                "break_points": [
                    {} for _ in range(judge.MAX_PREDICTED_EVENTS + 1)
                ],
            }))
            argv = [
                "judge.py",
                "--solution", str(solution),
                "--reward-json", str(reward_json),
                "--reward-txt", str(reward_txt),
            ]
            with mock.patch.object(sys, "argv", argv):
                judge.main()
            payload = json.loads(reward_json.read_text())
            self.assertEqual(payload["reward"], 0.0)
            self.assertIn("exceeds 256 events", payload["details"]["reason"])

    def test_solve_script_matches_verifier_oracle(self):
        script = Path(__file__).resolve().parents[1] / "solution" / "solve.sh"
        with tempfile.TemporaryDirectory() as directory:
            environment = os.environ.copy()
            environment["MEDVEDEV_OUTPUT_DIR"] = directory
            subprocess.run(["bash", str(script)], check=True, env=environment)
            payload = json.loads((Path(directory) / "solution.json").read_text())
        self.assertEqual(payload, {"break_points": self.oracle})

    def test_reference_shot_lengths_follow_counting_rule(self):
        lengths = [len(event["shots"]) for event in self.oracle]
        self.assertEqual(lengths, [8, 4, 3, 10, 3, 25, 2, 1, 7, 13, 3, 11, 7, 8, 1, 6])
        self.assertEqual(sum(lengths), 112)
        for event in self.oracle:
            offset = event["terminal_result"] in {
                "forced_error", "unforced_error", "error_unknown"
            }
            self.assertEqual(len(event["shots"]), event["rally_shots"] + offset)
            self.assertEqual(event["shots"][0], {
                "stroke": "serve",
                "direction": event["serve_direction"],
            })
            self.assertEqual(event["shots"][-1]["stroke"], event["terminal_stroke"])

    def test_unknown_pressure_error_and_court_position_are_scoreable(self):
        reference = copy.deepcopy(self.oracle)
        reference[0]["terminal_result"] = "error_unknown"
        reference[0]["terminal_court_position"] = "unknown"
        predictions = copy.deepcopy(reference)
        with mock.patch.object(judge, "REFERENCE_EVENTS", reference):
            self.assertEqual(self.reward(predictions), 1.0)
            del predictions[0]["shots"][-1]
            self.assertEqual(self.reward(predictions), 0.9922)

    def test_reference_identities_are_break_points_and_lock_final_score(self):
        def receiver_has_game_point(event):
            if event["server"] == "Daniil Medvedev":
                return (
                    event["de_minaur_points"] == "40"
                    and event["medvedev_points"] in {"0", "15", "30"}
                ) or (
                    event["de_minaur_points"] == "AD"
                    and event["medvedev_points"] == "40"
                )
            return (
                event["medvedev_points"] == "40"
                and event["de_minaur_points"] in {"0", "15", "30"}
            ) or (
                event["medvedev_points"] == "AD"
                and event["de_minaur_points"] == "40"
            )

        self.assertTrue(all(receiver_has_game_point(event) for event in self.oracle))
        self.assertEqual(
            (
                self.oracle[-1]["medvedev_points"],
                self.oracle[-1]["de_minaur_points"],
            ),
            ("40", "AD"),
        )
        medvedev_break_points = [
            event for event in self.oracle if event["server"] == "Alex De Minaur"
        ]
        de_minaur_break_points = [
            event for event in self.oracle if event["server"] == "Daniil Medvedev"
        ]
        self.assertEqual(
            (sum(event["outcome"] == "converted" for event in medvedev_break_points),
             len(medvedev_break_points)),
            (5, 10),
        )
        self.assertEqual(
            (sum(event["outcome"] == "converted" for event in de_minaur_break_points),
             len(de_minaur_break_points)),
            (2, 6),
        )

    def test_ace_and_unreturnable_have_one_serve_token(self):
        ace = self.oracle[7]
        unreturnable = self.oracle[14]
        self.assertEqual(ace["shots"], [{"stroke": "serve", "direction": "wide"}])
        self.assertEqual(
            unreturnable["shots"],
            [{"stroke": "serve", "direction": "down_the_t"}],
        )


if __name__ == "__main__":
    unittest.main()
