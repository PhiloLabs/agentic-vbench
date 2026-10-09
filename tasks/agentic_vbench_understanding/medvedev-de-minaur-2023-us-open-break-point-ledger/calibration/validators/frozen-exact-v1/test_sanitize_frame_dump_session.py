#!/usr/bin/env python3
"""Offline tests for the frame-dump session sanitizer."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SANITIZER_PATH = Path(__file__).with_name("sanitize_frame_dump_session.py")
SPEC = importlib.util.spec_from_file_location("frame_dump_sanitizer", SANITIZER_PATH)
assert SPEC is not None and SPEC.loader is not None
sanitizer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sanitizer
SPEC.loader.exec_module(sanitizer)


def write_fixture(path: Path) -> tuple[bytes, str, dict]:
    image = b"fixture-image-bytes"
    encrypted = 'encrypted-\\"opaque\\"-payload'
    rate_limits = {
        "limit_id": "account-specific-id",
        "limit_name": "private-plan-name",
        "primary": {"used_percent": 12.5, "resets_at": 123456},
        "credits": {"has_credits": True, "balance": "123.45"},
        "nested": {"text": "a brace } and escaped quote \\\" stay balanced"},
    }
    events = [
        {
            "timestamp": "2026-08-27T00:00:00Z",
            "ordinal": 0,
            "type": "response_item",
            "payload": {
                "type": "message",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": (
                            "data:image/jpeg;base64,"
                            + base64.b64encode(image).decode("ascii")
                        ),
                    }
                ],
            },
        },
        {
            "timestamp": "2026-08-27T00:00:01Z",
            "ordinal": 1,
            "type": "response_item",
            "payload": {
                "type": "reasoning",
                "encrypted_content": encrypted,
                "summary": [{"type": "summary_text", "text": "kept"}],
            },
        },
        {
            "timestamp": "2026-08-27T00:00:02Z",
            "ordinal": 2,
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {"total_token_usage": {"input_tokens": 10}},
                "rate_limits": rate_limits,
            },
        },
    ]
    path.write_text(
        "".join(
            json.dumps(event, separators=(",", ":"), ensure_ascii=True) + "\n"
            for event in events
        ),
        encoding="utf-8",
    )
    return image, encrypted, rate_limits


class SanitizerTests(unittest.TestCase):
    def test_redacts_all_sensitive_values_and_preserves_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.jsonl"
            destination = root / "sanitized.jsonl"
            manifest_path = root / "manifest.json"
            image, encrypted, rate_limits = write_fixture(source)

            manifest = sanitizer.sanitize(source, destination, manifest_path)
            output = destination.read_text(encoding="utf-8")
            events = [json.loads(line) for line in output.splitlines()]

            self.assertNotIn(base64.b64encode(image).decode("ascii"), output)
            self.assertNotIn(encrypted, output)
            self.assertNotIn("account-specific-id", output)
            self.assertNotIn("123.45", output)
            self.assertEqual(events[0]["timestamp"], "2026-08-27T00:00:00Z")
            self.assertEqual(events[1]["payload"]["summary"][0]["text"], "kept")
            self.assertEqual(
                events[2]["payload"]["info"]["total_token_usage"]["input_tokens"],
                10,
            )

            image_redaction = events[0]["payload"]["content"][0]["image_url"]
            encrypted_redaction = events[1]["payload"]["encrypted_content"]
            rate_redaction = events[2]["payload"]["rate_limits"]
            self.assertEqual(image_redaction["bytes"], len(image))
            self.assertEqual(
                image_redaction["sha256"], hashlib.sha256(image).hexdigest()
            )
            self.assertEqual(encrypted_redaction["bytes"], len(encrypted.encode()))
            rate_serialized = json.dumps(
                rate_limits, separators=(",", ":"), ensure_ascii=True
            ).encode()
            self.assertEqual(rate_redaction["bytes"], len(rate_serialized))
            self.assertEqual(
                rate_redaction["sha256"], hashlib.sha256(rate_serialized).hexdigest()
            )

            self.assertEqual(
                manifest["schema_version"],
                "avb-frame-dump-session-sanitization-v2",
            )
            self.assertEqual(manifest["original"]["base64_image_payloads"], 1)
            self.assertEqual(manifest["original"]["encrypted_content_values"], 1)
            self.assertEqual(manifest["original"]["rate_limits_objects"], 1)
            self.assertTrue(
                manifest["preservation"][
                    "timeline_and_operation_evidence_preserved"
                ]
            )
            self.assertEqual(
                json.loads(manifest_path.read_text(encoding="utf-8")), manifest
            )

    def test_output_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.jsonl"
            write_fixture(source)
            destination = root / "sanitized.jsonl"
            manifest_path = root / "manifest.json"

            first = sanitizer.sanitize(source, destination, manifest_path)
            first_output = destination.read_bytes()
            first_manifest = manifest_path.read_bytes()
            second = sanitizer.sanitize(source, destination, manifest_path)

            self.assertEqual(destination.read_bytes(), first_output)
            self.assertEqual(manifest_path.read_bytes(), first_manifest)
            self.assertEqual(first, second)

    def test_requires_each_expected_redaction_class(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.jsonl"
            source.write_text(
                json.dumps(
                    {
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "content": [
                                {
                                    "image_url": "data:image/jpeg;base64,YQ=="
                                }
                            ],
                        },
                    },
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "encrypted_content"):
                sanitizer.sanitize(
                    source, root / "sanitized.jsonl", root / "manifest.json"
                )


if __name__ == "__main__":
    unittest.main()
