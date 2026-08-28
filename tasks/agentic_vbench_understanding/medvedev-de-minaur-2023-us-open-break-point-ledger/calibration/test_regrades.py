#!/usr/bin/env python3

import importlib.util
import json
from pathlib import Path
import unittest


TASK_ROOT = Path(__file__).resolve().parents[1]
JUDGE_PATH = TASK_ROOT / "steps" / "solve" / "tests" / "judge.py"
SPEC = importlib.util.spec_from_file_location("medvedev_judge", JUDGE_PATH)
JUDGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(JUDGE)


CASES = (
    (
        "full media",
        "calibration/rollouts/codex-gpt-5.6-sol-high-v10-full-media.submitted-solution.json",
        "calibration/rollouts/codex-gpt-5.6-sol-high-v10-full-media.hierarchical-verifier-details.json",
        0.3305,
    ),
    (
        "scoreboard only",
        "calibration/ablations/codex-gpt-5.6-sol-high-v13-scoreboard-only.submitted-solution.json",
        "calibration/ablations/codex-gpt-5.6-sol-high-v13-scoreboard-only.hierarchical-verifier-details.json",
        0.1175,
    ),
    (
        "all-frame contact sheets",
        "calibration/ablations/codex-gpt-5.6-sol-high-v1-frame-dump-observed-zero-call.submitted-solution.json",
        "calibration/ablations/codex-gpt-5.6-sol-high-v1-frame-dump-observed-zero-call.hierarchical-verifier-details.json",
        0.0222,
    ),
    (
        "score/result fixed prior",
        "calibration/baselines/score-result-prior-v4-exact/solution.json",
        "calibration/baselines/score-result-prior-v4-exact/hierarchical-verifier-details.json",
        0.1833,
    ),
    (
        "oracle",
        "calibration/baselines/anchors/oracle/solution.json",
        "calibration/baselines/anchors/oracle/reward.json",
        1.0,
    ),
    (
        "empty",
        "calibration/baselines/anchors/empty/solution.json",
        "calibration/baselines/anchors/empty/reward.json",
        0.0,
    ),
    (
        "no media",
        "calibration/baselines/anchors/empty/solution.json",
        "calibration/ablations/codex-gpt-5.6-sol-high-v11-no-media.hierarchical-verifier-details.json",
        0.0,
    ),
    (
        "single frame",
        "calibration/baselines/anchors/empty/solution.json",
        "calibration/ablations/codex-gpt-5.6-sol-high-v11-single-frame.hierarchical-verifier-details.json",
        0.0,
    ),
)


class CalibrationRegradeTests(unittest.TestCase):
    def test_saved_hierarchical_regrades(self):
        for name, solution_rel, details_rel, expected in CASES:
            with self.subTest(name=name):
                solution = json.loads((TASK_ROOT / solution_rel).read_text())
                stored = json.loads((TASK_ROOT / details_rel).read_text())
                reward, details = JUDGE.score_predictions(solution["break_points"])
                self.assertEqual(reward, expected)
                self.assertEqual(stored["reward"], expected)
                stored_details = {
                    key: value
                    for key, value in stored["details"].items()
                    if key not in {"reason", "root_schema_issue"}
                }
                self.assertEqual(stored_details, details)

    def test_saved_f1_components_recompute(self):
        for name, _, details_rel, expected in CASES:
            with self.subTest(name=name):
                stored = json.loads((TASK_ROOT / details_rel).read_text())
                details = stored["details"]
                precision = details["hierarchical_precision"]
                recall = details["hierarchical_recall"]
                recomputed = (
                    2 * precision * recall / (precision + recall)
                    if precision + recall
                    else 0.0
                )
                self.assertAlmostEqual(recomputed, expected, places=4)
                self.assertEqual(
                    details["scorer_version"],
                    "hierarchical-bottleneck-v1",
                )


if __name__ == "__main__":
    unittest.main()
