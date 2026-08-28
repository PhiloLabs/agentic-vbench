#!/usr/bin/env python3
"""Offline mutation tests for avb_validate_formal_run.py."""

from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

VALIDATOR_PATH = Path(__file__).with_name("avb_validate_formal_run.py")
SPEC = importlib.util.spec_from_file_location("avb_formal_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class GatewayGrammarTests(unittest.TestCase):
    def test_accepts_closed_world_gateway_lines(self) -> None:
        lines = [
            "2026-08-27T00:00:00+00:00 START allowlist=chatgpt.com:443",
            (
                "2026-08-27T00:00:01+00:00 ALLOW "
                "authority='chatgpt.com:443' sni='chatgpt.com'"
            ),
            "2026-08-27T00:00:02+00:00 DENY authority='pypi.org:443'",
            (
                "2026-08-27T00:00:03+00:00 ERROR "
                "authority='chatgpt.com:443' "
                "error=gaierror(-2, 'Name or service not known')"
            ),
            (
                "2026-08-27T00:00:04+00:00 RELAY_END "
                "direction=client-to-upstream bytes=12 "
                "error=ConnectionResetError(104, 'Connection reset by peer')"
            ),
            (
                "2026-08-27T00:00:05+00:00 RELAY_END "
                "direction=client-to-upstream bytes=13 "
                "error=BrokenPipeError(32, 'Broken pipe')"
            ),
            (
                "2026-08-27T00:00:06+00:00 CLOSE "
                "authority='chatgpt.com:443' client_bytes=13 upstream_bytes=9"
            ),
        ]
        kinds, timestamps = validator.classify_gateway_lines(lines)
        self.assertEqual(kinds[0], "start")
        self.assertEqual(len(kinds), len(timestamps))

    def test_rejects_unknown_gateway_line(self) -> None:
        lines = [
            "2026-08-27T00:00:00+00:00 START allowlist=chatgpt.com:443",
            "2026-08-27T00:00:01+00:00 NOTE oracle_count=16",
        ]
        with self.assertRaisesRegex(ValueError, "closed-world"):
            validator.classify_gateway_lines(lines)

    def test_rejects_start_after_another_event(self) -> None:
        lines = [
            "2026-08-27T00:00:00+00:00 DENY authority='pypi.org:443'",
            "2026-08-27T00:00:01+00:00 START allowlist=chatgpt.com:443",
        ]
        with self.assertRaisesRegex(ValueError, "unique first"):
            validator.classify_gateway_lines(lines)

    def test_rejects_unmodeled_deny_shape(self) -> None:
        lines = [
            "2026-08-27T00:00:00+00:00 START allowlist=chatgpt.com:443",
            "2026-08-27T00:00:01+00:00 DENY malformed='GET / HTTP/1.1'",
        ]
        with self.assertRaisesRegex(ValueError, "closed-world"):
            validator.classify_gateway_lines(lines)


class TimelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.t0 = validator.parse_timestamp("2026-08-27T00:00:00Z")
        self.t1 = validator.parse_timestamp("2026-08-27T00:00:01Z")
        self.t2 = validator.parse_timestamp("2026-08-27T00:00:02Z")
        self.t3 = validator.parse_timestamp("2026-08-27T00:00:03Z")

    def test_accepts_nested_execution_envelope(self) -> None:
        validator.validate_execution_envelope(self.t0, self.t3, self.t1, self.t2)
        validator.validate_ordered_timestamps_within(
            "fixture", [self.t1, self.t2], self.t1, self.t2
        )

    def test_rejects_execution_outside_trial(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside"):
            validator.validate_execution_envelope(self.t1, self.t3, self.t0, self.t2)

    def test_rejects_unordered_or_outside_items(self) -> None:
        with self.assertRaisesRegex(ValueError, "not ordered"):
            validator.validate_ordered_timestamps_within(
                "fixture", [self.t2, self.t1], self.t1, self.t2
            )
        with self.assertRaisesRegex(ValueError, "outside"):
            validator.validate_ordered_timestamps_within(
                "fixture", [self.t0], self.t1, self.t2
            )

    def test_relay_recovery_requires_a_strictly_later_atif_step(self) -> None:
        validator.require_later_atif_step("reset", self.t1, [self.t2])
        with self.assertRaisesRegex(ValueError, "no later ATIF"):
            validator.require_later_atif_step("reset", self.t2, [self.t1, self.t2])

    def test_raw_session_requires_ordered_productive_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            events = [
                {
                    "type": "response_item",
                    "timestamp": "2026-08-27T00:00:02Z",
                    "payload": {"type": "reasoning"},
                },
                {
                    "type": "response_item",
                    "timestamp": "2026-08-27T00:00:01Z",
                    "payload": {"type": "message", "role": "assistant"},
                },
            ]
            path.write_text(
                "\n".join(json.dumps(event) for event in events) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "not ordered"):
                validator.productive_session_timestamps(path)


class RewardAndConnectionTests(unittest.TestCase):
    def reward_payload(self) -> dict:
        return {
            "reward": 0.0,
            "details": {
                "formula": validator.EXPECTED_FORMULA,
                "n_predicted": 17,
                "n_ground_truth": 16,
                "exact_event_matches_ordered": 0,
                "reward_denominator": 33,
            },
        }

    def test_recomputes_reward_from_counts(self) -> None:
        reward, _ = validator.validate_reward_consistency(self.reward_payload(), 16)
        self.assertEqual(reward, 0.0)

    def test_rejects_contradictory_or_wrong_ground_truth_reward(self) -> None:
        payload = self.reward_payload()
        payload["reward"] = 1.0
        with self.assertRaisesRegex(ValueError, "recomputed"):
            validator.validate_reward_consistency(payload, 16)
        payload = self.reward_payload()
        payload["details"]["n_ground_truth"] = 15
        payload["details"]["reward_denominator"] = 32
        with self.assertRaisesRegex(ValueError, "pinned expected"):
            validator.validate_reward_consistency(payload, 16)

    def test_gateway_connection_conservation_and_positive_bytes(self) -> None:
        validator.validate_gateway_connection_conservation(2, [(10, 20)], 1)
        with self.assertRaisesRegex(ValueError, "conservation"):
            validator.validate_gateway_connection_conservation(3, [(10, 20)], 1)
        with self.assertRaisesRegex(ValueError, "nonpositive"):
            validator.validate_gateway_connection_conservation(1, [(10, 0)], 0)


class ChecksumTests(unittest.TestCase):
    def test_recomputes_current_full_media_harbor_checksum(self) -> None:
        configured = os.environ.get("AVB_FORMAL_FULL_MEDIA_OVERLAY")
        if not configured:
            self.skipTest("AVB_FORMAL_FULL_MEDIA_OVERLAY is not configured")
        task = Path(configured)
        self.assertEqual(
            validator.recompute_harbor_task_checksum(task),
            "1c4cda86035db349b8c2d8f0a8d131aeafb703f676c9603892da8c085aa4281a",
        )


if __name__ == "__main__":
    unittest.main()
