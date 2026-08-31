#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPURPOSE_ROOT = ROOT / "tasks" / "agentic_vbench_repurpose"
JUDGE_PATHS = sorted(REPURPOSE_ROOT.glob("*/steps/solve/tests/judge.py"))
CONTRACT_FUNCTIONS = {"_score_max", "_violation_framing", "_require_json_bool"}


def load_contract(path: Path) -> tuple[dict[str, object], ast.Module]:
    tree = ast.parse(path.read_text(), filename=str(path))
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in CONTRACT_FUNCTIONS
    ]
    found = {node.name for node in functions}
    if found != CONTRACT_FUNCTIONS:
        raise AssertionError(f"{path}: expected {CONTRACT_FUNCTIONS}, found {found}")
    module = ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[]))
    namespace: dict[str, object] = {}
    exec(compile(module, str(path), "exec"), namespace)
    return namespace, tree


def function_calls(tree: ast.Module, function_name: str, called_name: str) -> bool:
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == called_name
        for node in ast.walk(function)
    )


class RepurposeJudgeContractTest(unittest.TestCase):
    def test_all_task_local_judges_use_contract_helpers(self) -> None:
        self.assertTrue(JUDGE_PATHS)
        for path in JUDGE_PATHS:
            with self.subTest(path=path):
                _, tree = load_contract(path)
                self.assertTrue(
                    function_calls(tree, "judge_item_gemini_audio", "_violation_framing")
                )
                self.assertTrue(
                    function_calls(tree, "judge_item_gemini_audio", "_require_json_bool")
                )
                self.assertTrue(
                    function_calls(tree, "judge_item_gemini_video", "_require_json_bool")
                )
                self.assertTrue(function_calls(tree, "judge_item", "_require_json_bool"))

    def test_violation_scoring_and_framing(self) -> None:
        for path in JUDGE_PATHS:
            namespace, _ = load_contract(path)
            score_max = namespace["_score_max"]
            framing = namespace["_violation_framing"]
            with self.subTest(path=path):
                violation = {"weight": -30}
                self.assertIn("Return pass=true", framing(violation))
                self.assertEqual(score_max(violation, False), (0, 0))
                self.assertEqual(score_max(violation, True), (-30, 0))

                narrative = {"weight": -30, "narrative_essential": True}
                self.assertEqual(framing(narrative), "")
                self.assertEqual(score_max(narrative, False), (-30, 0))
                self.assertEqual(score_max(narrative, True), (0, 0))

                positive = {"weight": 5}
                self.assertEqual(framing(positive), "")
                self.assertEqual(score_max(positive, False), (0, 5))
                self.assertEqual(score_max(positive, True), (5, 5))

    def test_pass_requires_a_json_boolean(self) -> None:
        for path in JUDGE_PATHS:
            namespace, _ = load_contract(path)
            require_bool = namespace["_require_json_bool"]
            with self.subTest(path=path):
                self.assertIs(require_bool(True), True)
                self.assertIs(require_bool(False), False)
                for invalid in ("true", "false", 1, 0, None):
                    with self.assertRaises(ValueError):
                        require_bool(invalid)

    def test_reachable_negative_audio_items_receive_violation_framing(self) -> None:
        affected = 0
        for path in JUDGE_PATHS:
            namespace, _ = load_contract(path)
            framing = namespace["_violation_framing"]
            rubric = json.loads(path.with_name("rubric.json").read_text())
            for item in rubric["items"]:
                if (
                    item["weight"] < 0
                    and item.get("judge", "").lower() == "gemini-audio"
                    and not item.get("narrative_essential")
                ):
                    affected += 1
                    with self.subTest(path=path, item=item["id"]):
                        self.assertIn("decline to fire the penalty", framing(item))
        self.assertGreater(affected, 0)


if __name__ == "__main__":
    unittest.main()
