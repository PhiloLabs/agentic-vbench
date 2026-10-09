"""Offline mutation tests for the frame-dump observed-zero-call validator."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

VALIDATOR_PATH = Path(__file__).with_name(
    "avb_validate_frame_dump_no_tools_run.py"
)
SPEC = importlib.util.spec_from_file_location("frame_dump_run_validator", VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


def fake_jpeg(width: int, height: int, nonce: int = 0) -> bytes:
    output = io.BytesIO()
    image = Image.new(
        "RGB",
        (width, height),
        color=(nonce % 256, (nonce * 17) % 256, (nonce * 31) % 256),
    )
    image.save(output, format="JPEG", quality=91, comment=f"fixture-{nonce}".encode())
    return output.getvalue()


def processed_aggregate(images: list[bytes]) -> str:
    payload = "".join(
        f"{hashlib.sha256(image).hexdigest()}  "
        f"/workspace/materials/frame-dump/sheet-{index:03d}.jpg\n"
        for index, image in enumerate(images, start=1)
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def image_session_events(
    images: list[bytes],
    instruction: str = "wrapped task",
    final_text: str = '{"break_points": []}',
) -> list[dict]:
    content = []
    for index, image in enumerate(images, start=1):
        name = f"sheet-{index:03d}.jpg"
        content.extend(
            [
                {
                    "type": "input_text",
                    "text": (
                        f'<image name=[Image #{index}] '
                        f'path="/workspace/materials/frame-dump/{name}">'
                    ),
                },
                {
                    "type": "input_image",
                    "image_url": (
                        "data:image/jpeg;base64,"
                        + base64.b64encode(image).decode("ascii")
                    ),
                    "detail": "high",
                },
                {"type": "input_text", "text": "</image>"},
            ]
        )
    content.append({"type": "input_text", "text": instruction})
    return [
        {
            "type": "response_item",
            "timestamp": "2026-08-27T00:00:01Z",
            "payload": {"type": "message", "role": "user", "content": content},
        },
        {
            "type": "response_item",
            "timestamp": "2026-08-27T00:00:02Z",
            "payload": {"type": "reasoning"},
        },
        {
            "type": "response_item",
            "timestamp": "2026-08-27T00:00:03Z",
            "payload": {
                "type": "message",
                "role": "assistant",
                "phase": "final_answer",
                "content": [{"type": "output_text", "text": final_text}],
            },
        },
    ]


def write_jsonl(path: Path, events: list[dict]) -> None:
    serialized = []
    for ordinal, source in enumerate(events):
        event = dict(source)
        event["ordinal"] = ordinal
        serialized.append(json.dumps(event, separators=(",", ":")) + "\n")
    path.write_text(
        "".join(serialized),
        encoding="utf-8",
    )


class FrameManifestTests(unittest.TestCase):
    def test_accepts_exact_ordered_frame_hash_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hashes.txt"
            path.write_text(
                "".join(
                    f"{index:064x}  /workspace/materials/frame-dump/"
                    f"sheet-{index:03d}.jpg\n"
                    for index in range(1, 4)
                ),
                encoding="utf-8",
            )
            entries = validator.parse_original_frame_manifest(path, 3)
            self.assertEqual([entry["name"] for entry in entries], [
                "sheet-001.jpg",
                "sheet-002.jpg",
                "sheet-003.jpg",
            ])

    def test_rejects_out_of_order_frame_hash_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hashes.txt"
            path.write_text(
                f"{'1' * 64}  /workspace/materials/frame-dump/sheet-002.jpg\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "out-of-order"):
                validator.parse_original_frame_manifest(path, 1)

    def test_rejects_duplicate_frame_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hashes.txt"
            digest = "1" * 64
            path.write_text(
                f"{digest}  /workspace/materials/frame-dump/sheet-001.jpg\n"
                f"{digest}  /workspace/materials/frame-dump/sheet-002.jpg\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate"):
                validator.parse_original_frame_manifest(path, 2)


class RawSessionTests(unittest.TestCase):
    def validate_fixture(self, path: Path, images: list[bytes]) -> dict:
        original = [
            {"name": f"sheet-{index:03d}.jpg", "sha256": "f" * 64}
            for index in range(1, len(images) + 1)
        ]
        return validator.validate_raw_session(
            path,
            original,
            "wrapped task",
            len(images),
            (64, 32),
            processed_aggregate(images),
            0,
            False,
        )

    def test_accepts_passive_strict_jsonl_and_ordered_images(self) -> None:
        images = [fake_jpeg(64, 32, 1), fake_jpeg(64, 32, 2)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            write_jsonl(path, image_session_events(images))
            report = self.validate_fixture(path, images)
            self.assertEqual(report["input_image_count"], 2)
            self.assertEqual(report["model_tool_calls_observed"], 0)

    def test_rejects_active_response_item(self) -> None:
        images = [fake_jpeg(64, 32, 1)]
        events = image_session_events(images)
        events.insert(
            1,
            {
                "type": "response_item",
                "timestamp": "2026-08-27T00:00:01.500Z",
                "payload": {"type": "function_call", "name": "shell"},
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            write_jsonl(path, events)
            with self.assertRaisesRegex(ValueError, "active or unknown"):
                self.validate_fixture(path, images)

    def test_rejects_tool_item_hidden_in_event_msg(self) -> None:
        images = [fake_jpeg(64, 32, 1)]
        events = image_session_events(images)
        events.insert(
            1,
            {
                "type": "event_msg",
                "timestamp": "2026-08-27T00:00:01.500Z",
                "payload": {
                    "type": "item_completed",
                    "completed_at_ms": 2,
                    "item": {"type": "ToolCall", "name": "shell"},
                    "started_at_ms": 1,
                    "thread_id": "thread",
                    "turn_id": "turn",
                },
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            write_jsonl(path, events)
            with self.assertRaisesRegex(ValueError, "active or unknown completed"):
                self.validate_fixture(path, images)

    def test_rejects_unknown_raw_top_level_event(self) -> None:
        images = [fake_jpeg(64, 32, 1)]
        events = image_session_events(images)
        events.insert(
            1,
            {
                "type": "future_tool_event",
                "timestamp": "2026-08-27T00:00:01.500Z",
                "payload": {},
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            write_jsonl(path, events)
            with self.assertRaisesRegex(ValueError, "top-level"):
                self.validate_fixture(path, images)

    def test_rejects_malformed_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            path.write_text("{broken}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "malformed raw session"):
                validator.validate_raw_session(
                    path, [], "wrapped task", 0, (64, 32), None, None, False
                )

    def test_rejects_image_path_order_mutation(self) -> None:
        images = [fake_jpeg(64, 32, 1)]
        events = image_session_events(images)
        events[0]["payload"]["content"][0]["text"] = (
            '<image name=[Image #1] path="/workspace/materials/frame-dump/'
            'sheet-002.jpg">'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            write_jsonl(path, events)
            with self.assertRaisesRegex(ValueError, "out of order"):
                self.validate_fixture(path, images)

    def test_rejects_invalid_base64(self) -> None:
        images = [fake_jpeg(64, 32, 1)]
        events = image_session_events(images)
        events[0]["payload"]["content"][1]["image_url"] += "!"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            write_jsonl(path, events)
            with self.assertRaisesRegex(ValueError, "invalid base64"):
                self.validate_fixture(path, images)

    def test_rejects_wrong_processed_dimensions(self) -> None:
        images = [fake_jpeg(32, 16, 1)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            write_jsonl(path, image_session_events(images))
            with self.assertRaisesRegex(ValueError, "dimensions"):
                self.validate_fixture(path, images)

    def test_rejects_processed_image_aggregate_mutation(self) -> None:
        images = [fake_jpeg(64, 32, 1)]
        original = [{"name": "sheet-001.jpg", "sha256": "f" * 64}]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            write_jsonl(path, image_session_events(images))
            with self.assertRaisesRegex(ValueError, "processed-image manifest"):
                validator.validate_raw_session(
                    path,
                    original,
                    "wrapped task",
                    1,
                    (64, 32),
                    "0" * 64,
                    0,
                    False,
                )

    def test_rejects_unordered_response_timestamps(self) -> None:
        images = [fake_jpeg(64, 32, 1)]
        events = image_session_events(images)
        events[1]["timestamp"] = "2026-08-26T23:59:59Z"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "session.jsonl"
            write_jsonl(path, events)
            with self.assertRaisesRegex(ValueError, "not ordered"):
                self.validate_fixture(path, images)


class SolutionAndNativeTests(unittest.TestCase):
    def test_normalized_final_json_equals_materialized_bytes(self) -> None:
        final = '{"break_points":[]}'
        submitted = b'{\n  "break_points": []\n}\n'
        result = validator.validate_solution_materialization(final, submitted)
        self.assertTrue(result["normalized_byte_equality"])

    def test_rejects_materialization_byte_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "differs"):
            validator.validate_solution_materialization(
                '{"break_points":[]}', b'{"break_points":[]}\n'
            )

    def native_events(self, final_text: str) -> list[dict]:
        return [
            {"type": "thread.started", "thread_id": "fixture"},
            {"type": "turn.started"},
            {
                "type": "item.completed",
                "item": {"id": "item-1", "type": "agent_message", "text": final_text},
            },
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 1,
                    "cached_input_tokens": 0,
                    "cache_write_input_tokens": 0,
                    "output_tokens": 1,
                    "reasoning_output_tokens": 0,
                },
            },
        ]

    def write_native(self, path: Path, events: list[dict]) -> None:
        headers = [
            (
                "WARNING: proceeding, even though we could not create PATH aliases: "
                "Refusing to create helper binaries under temporary dir \"/tmp\" "
                "(codex_home: AbsolutePathBuf(\"/tmp/codex-home\"))"
            ),
            "Reading additional input from stdin...",
        ]
        path.write_text(
            "\n".join(headers + [json.dumps(event) for event in events]) + "\n",
            encoding="utf-8",
        )

    def test_accepts_zero_operation_native_stream(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "codex.txt"
            self.write_native(path, self.native_events("final"))
            report = validator.validate_native_stream(path, "final", False)
            self.assertEqual(report["native_tool_operations"], 0)

    def test_rejects_native_tool_operation(self) -> None:
        events = self.native_events("final")
        events.insert(
            2,
            {
                "type": "item.started",
                "item": {"type": "command_execution", "command": "true"},
            },
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "codex.txt"
            self.write_native(path, events)
            with self.assertRaisesRegex(ValueError, "active or unknown native"):
                validator.validate_native_stream(path, "final", False)

    def test_rejects_unknown_native_completed_item(self) -> None:
        events = self.native_events("final")
        events[2] = {
            "type": "item.completed",
            "item": {"type": "future_tool", "result": "ok"},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "codex.txt"
            self.write_native(path, events)
            with self.assertRaisesRegex(ValueError, "active or unknown native completed"):
                validator.validate_native_stream(path, "final", False)


class RewardMetadataTests(unittest.TestCase):
    def reward(self) -> dict:
        return {
            "reward": 0.0,
            "details": {
                "formula": validator.EXPECTED_FORMULA,
                "n_predicted": 14,
                "n_ground_truth": 16,
                "exact_event_matches_ordered": 0,
                "reward_denominator": 30,
            },
        }

    def test_recomputes_exact_event_f1(self) -> None:
        reward, details = validator.validate_reward_consistency(self.reward())
        self.assertEqual(reward, 0.0)
        self.assertEqual(details["n_ground_truth"], 16)

    def test_rejects_contradictory_reward(self) -> None:
        payload = self.reward()
        payload["reward"] = 1.0
        with self.assertRaisesRegex(ValueError, "recomputed"):
            validator.validate_reward_consistency(payload)

    def test_requires_exact_adapter_metadata(self) -> None:
        self.assertEqual(
            validator.validate_metadata(dict(validator.EXPECTED_METADATA)),
            validator.EXPECTED_METADATA,
        )
        mutated = dict(validator.EXPECTED_METADATA)
        mutated["model_tool_calls"] = 1
        with self.assertRaisesRegex(ValueError, "not exact"):
            validator.validate_metadata(mutated)

    def test_frozen_judge_regrade_rejects_self_consistent_forged_reward(self) -> None:
        judge_source = """
REFERENCE_EVENTS = [{}] * 16
def score_predictions(predictions):
    return 1.0, {
        'formula': '2 * exact_ordered_event_matches / (n_predicted + n_reference)',
        'n_predicted': len(predictions),
        'n_ground_truth': 16,
        'exact_event_matches_ordered': 16,
        'reward_denominator': len(predictions) + 16,
    }
"""
        forged = {
            "reward": 0.0,
            "details": {
                "reason": "ok",
                "root_schema_issue": False,
                "formula": validator.EXPECTED_FORMULA,
                "n_predicted": 16,
                "n_ground_truth": 16,
                "exact_event_matches_ordered": 0,
                "reward_denominator": 32,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            judge = root / "judge.py"
            solution = root / "solution.json"
            judge.write_text(judge_source, encoding="utf-8")
            solution.write_text(
                json.dumps({"break_points": [{}] * 16}), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "independent frozen-judge"):
                validator.regrade_with_frozen_judge(
                    judge, solution, forged, expected_judge_sha256=None
                )


class GatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.t0 = validator.parse_timestamp("2026-08-27T00:00:00Z")
        self.t9 = validator.parse_timestamp("2026-08-27T00:00:09Z")

    def validate_lines(self, lines: list[str], counts: dict[str, int]) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gateway.log"
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return validator.validate_gateway(
                path,
                self.t0,
                self.t9,
                validator.parse_timestamp("2026-08-27T00:00:04Z"),
                counts,
            )

    def test_accepts_closed_world_broken_pipe_recovery(self) -> None:
        lines = [
            "2026-08-27T00:00:00Z START allowlist=chatgpt.com:443",
            (
                "2026-08-27T00:00:01Z ALLOW "
                "authority='chatgpt.com:443' sni='chatgpt.com'"
            ),
            (
                "2026-08-27T00:00:02Z RELAY_END direction=client-to-upstream "
                "bytes=10 error=BrokenPipeError(32, 'Broken pipe')"
            ),
            (
                "2026-08-27T00:00:03Z CLOSE authority='chatgpt.com:443' "
                "client_bytes=10 upstream_bytes=20"
            ),
            (
                "2026-08-27T00:00:03.500Z ALLOW "
                "authority='chatgpt.com:443' sni='chatgpt.com'"
            ),
            (
                "2026-08-27T00:00:04Z CLOSE authority='chatgpt.com:443' "
                "client_bytes=11 upstream_bytes=21"
            ),
            (
                "2026-08-27T00:00:06Z DENY "
                "authority='ab.chatgpt.com:443'"
            ),
        ]
        counts = {
            "start": 1,
            "allow": 2,
            "close": 2,
            "deny": 1,
            "error": 0,
            "connection_reset": 0,
            "broken_pipe": 1,
        }
        report = self.validate_lines(lines, counts)
        self.assertEqual(report["broken_pipe"], 1)

    def test_rejects_unknown_gateway_line(self) -> None:
        with self.assertRaisesRegex(ValueError, "closed-world"):
            validator.classify_gateway_lines(
                [
                    "2026-08-27T00:00:00Z START allowlist=chatgpt.com:443",
                    "2026-08-27T00:00:01Z NOTE oracle=16",
                ]
            )

    def test_rejects_relay_close_byte_mismatch(self) -> None:
        lines = [
            "2026-08-27T00:00:00Z START allowlist=chatgpt.com:443",
            (
                "2026-08-27T00:00:01Z ALLOW "
                "authority='chatgpt.com:443' sni='chatgpt.com'"
            ),
            (
                "2026-08-27T00:00:02Z RELAY_END direction=client-to-upstream "
                "bytes=9 error=ConnectionResetError(104, 'Connection reset by peer')"
            ),
            (
                "2026-08-27T00:00:03Z CLOSE authority='chatgpt.com:443' "
                "client_bytes=10 upstream_bytes=20"
            ),
        ]
        counts = {
            "start": 1,
            "allow": 1,
            "close": 1,
            "deny": 0,
            "error": 0,
            "connection_reset": 1,
            "broken_pipe": 0,
        }
        with self.assertRaisesRegex(ValueError, "byte count"):
            self.validate_lines(lines, counts)

    def test_rejects_unexpected_denied_authority(self) -> None:
        lines = [
            "2026-08-27T00:00:00Z START allowlist=chatgpt.com:443",
            (
                "2026-08-27T00:00:01Z ALLOW "
                "authority='chatgpt.com:443' sni='chatgpt.com'"
            ),
            (
                "2026-08-27T00:00:02Z CLOSE authority='chatgpt.com:443' "
                "client_bytes=10 upstream_bytes=20"
            ),
            "2026-08-27T00:00:05Z DENY authority='evil.example:443'",
        ]
        counts = {
            "start": 1,
            "allow": 1,
            "close": 1,
            "deny": 1,
            "error": 0,
            "connection_reset": 0,
            "broken_pipe": 0,
        }
        with self.assertRaisesRegex(ValueError, "unexpected denied"):
            self.validate_lines(lines, counts)


class IntegrityTests(unittest.TestCase):
    def test_detects_toctou_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.txt"
            path.write_text("before", encoding="utf-8")
            paths = {"evidence": path}
            before = validator.snapshot_hashes(paths)
            path.write_text("after", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "changed during validation"):
                validator.assert_snapshot_unchanged(paths, before)

    def test_jpeg_dimension_parser_rejects_non_jpeg(self) -> None:
        self.assertEqual(validator.jpeg_dimensions(fake_jpeg(64, 32)), (64, 32))
        with self.assertRaisesRegex(ValueError, "not a complete JPEG"):
            validator.jpeg_dimensions(b"not-jpeg")

    def test_rejects_output_alias_or_protected_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            evidence = root / "evidence.txt"
            evidence.write_text("evidence", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "aliases"):
                validator.validate_output_is_disjoint(
                    evidence, {"evidence": evidence}, ()
                )
            with self.assertRaisesRegex(ValueError, "protected"):
                validator.validate_output_is_disjoint(
                    root / "new-report.json", {"evidence": evidence}, (root,)
                )


if __name__ == "__main__":
    unittest.main()
