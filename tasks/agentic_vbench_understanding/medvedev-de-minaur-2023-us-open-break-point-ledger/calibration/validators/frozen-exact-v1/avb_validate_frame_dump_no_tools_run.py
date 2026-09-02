"""Strict evidence validator for one completed frame-dump/zero-call run.

This policy proves what the preserved run can prove: the model received 179
ordered, decodable images and the raw session contains no active response item.
It deliberately does not claim that the backend request used an empty tools
array. Codex CLI 0.149.1 preprocesses the 2560x1080 contact sheets to 2048x864
before serializing them into the raw session, so the original and session image
bytes are tracked as distinct evidence layers.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

import PIL
from PIL import Image, UnidentifiedImageError

VALIDATION_POLICY = "avb-frame-dump-observed-zero-call-strict-v2"
SCHEMA_VERSION = "avb-frame-dump-run-validation-v2"
EXPECTED_FORMULA = "2 * exact_ordered_event_matches / (n_predicted + n_reference)"
EXPECTED_TRIAL_NAME = "frame-dump-no-tools__uRwKB2a"
EXPECTED_TASK_CHECKSUM = (
    "b9af704673c53cfbdda71ded6e5c5c0a9874f19ebba55cba6a173d1a774e9f25"
)
EXPECTED_IMAGE_REFERENCE = (
    "avb-medvedev-codex@"
    "sha256:390fb56051fafb49b5b4b797cb15704469294f816255994e9ee0fd21fe2da06b"
)
EXPECTED_IMAGE_ID = (
    "sha256:390fb56051fafb49b5b4b797cb15704469294f816255994e9ee0fd21fe2da06b"
)
EXPECTED_IMAGE_SIZE = 1_085_220_502
EXPECTED_MODEL = "gpt-5.6-sol"
EXPECTED_AGENT_VERSION = "0.149.1"
EXPECTED_REASONING_EFFORT = "high"
EXPECTED_AGENT_IMPORT_PATH = (
    "avb_frame_dump_no_tools_codex:PreinstalledCodexFrameDumpNoTools"
)
EXPECTED_GROUND_TRUTH_EVENTS = 16
EXPECTED_REWARD = 0.0
EXPECTED_FRAME_SHEETS = 179
EXPECTED_ORIGINAL_DIMENSIONS = (2560, 1080)
EXPECTED_SESSION_DIMENSIONS = (2048, 864)
EXPECTED_PROCESSED_IMAGE_MANIFEST_SHA256 = (
    "d79c946a23bad83bf02c576cd3a0c9c6b542f45f29a478959d7971f38d42dbcf"
)
EXPECTED_GATEWAY_COUNTS = {
    "start": 1,
    "allow": 21,
    "close": 21,
    "deny": 8,
    "error": 0,
    "connection_reset": 2,
    "broken_pipe": 6,
}
EXPECTED_METADATA = {
    "ablation": "frame_dump_no_tools",
    "frame_sheet_count": 179,
    "model_tool_calls": 0,
    "solution_materialized_by": "harbor_adapter",
    "tool_absence_guarantee": "post_hoc_zero_call_audit",
}
EXPECTED_MANIFEST_LINES = (
    "ablation=frame_dump_no_tools",
    "source_validation=passed",
    "canonical_image_id=sha256:f592cda4dfc09ca25ae3a19d7e65d17248fb01059f061368eecf14ae1ae9cb28",
    "expected_harness_image_id=sha256:390fb56051fafb49b5b4b797cb15704469294f816255994e9ee0fd21fe2da06b",
    "source_sha256=d61bee17596a28dbc8f8b607e4fc0dd6542885dbe9cdad18e1953e89363b0860",
    "source_bytes=685013111",
    "source_duration_seconds=7152.578767",
    "source_frames=214363",
    "cell_width=64",
    "cell_height=36",
    "grid_columns=40",
    "grid_rows=30",
    "expected_sheets=179",
    "actual_sheets=179",
    "last_sheet_valid_cells=763",
    "last_valid_global_frame=214362",
    "Python 3.12.14",
    "ffmpeg version 7.1.5-0+deb13u1 Copyright (c) 2000-2026 the FFmpeg developers",
    "codex-cli 0.149.1",
    "ripgrep 14.1.1",
)
FROZEN_TASK_HASHES = {
    "steps/solve/instruction.md": (
        "2b025b557a17f2443e9b8f5951ee19562eee570038d092a7757b957555d1cd55"
    ),
    "steps/solve/tests/judge.py": (
        "3ece409c4c223c2bf2120fb1ef251d76c88bc6150fb59b4d0b6963bcf69c4b40"
    ),
    "steps/solve/tests/test_judge.py": (
        "6b1801277acdc2b73ee13c4a0f51b0ef90a2860edd43d834c872aec623cda5b4"
    ),
    "steps/solve/solution/solve.sh": (
        "75c03d3084ebc3670ffbf77ee2ca5b0a46f16f8a4feb6b1d834c80aaa3a4c5c5"
    ),
}
PINNED_EVIDENCE_HASHES = {
    "config.json": "cae98b52b2475bf1474e5c3bb271b601612df678418aa8721188840ef9fdf12a",
    "result.json": "1bbc98fecd2d3b4cd041d6e65df2e38d3bb153d8dca68f5dbbd87252919f3e50",
    "native_codex_jsonl": "5c02facdcf4cc8397eb41d2616da139fe3e817204792304644ef76d038650fcd",
    "raw_session_jsonl": "f6f275834e2c3f727f022eb4d0fa11d4de1b935f5bb5761e50103c4df7e46018",
    "input_manifest": "8fd3d4a01117d3a6d328679b9d66436c2962ce0f6b57c0bc08de01b3981950a7",
    "frame_dump_sha256": "4ee2dbfef29fd9da705d5e84452c9b4b5837d06e1162edaa844356ec298b0ed1",
    "artifact_manifest": "74e23daa039ba00190dae93bf955ac487e1a7598da085c2c974cb980be084042",
    "materials_listing": "6aba76cdb32eef492e1bfa6518c8dbfe5399453c2f91f4e2682c20a5f84da2a8",
    "submitted_solution": "845b3ae14fdd23ff264b5ee37bbc791a9c7c63d20069eb50c778eb41419d8c2c",
    "reward_json": "55f9214eb23969158ec32b4bcb0eddc3d451739a01f843fea3a6caea0a2556b3",
    "gateway_log": "1b23d924889a5116304899aa3477e341d26e5b45d6181f590cd7d00f8a8133e9",
    "adapter_source": "035034322a96a3ad2a4a755fb254c1528fda0ce45b9eaac8921601144087fdfe",
    "base_adapter_source": "39b8c9d70870627f8e95c2c69655cc476748fd2fcda310e65a8d860553983690",
}

PASSIVE_RESPONSE_ITEM_TYPES = frozenset(
    {"message", "reasoning", "compaction", "context_compaction"}
)
PASSIVE_RAW_TOP_LEVEL_TYPES = frozenset(
    {"session_meta", "event_msg", "response_item", "world_state", "turn_context"}
)
PASSIVE_EVENT_MSG_TYPES = frozenset(
    {"task_started", "item_completed", "token_count", "task_complete"}
)
PASSIVE_EVENT_MSG_SCHEMAS = {
    "task_started": frozenset(
        {
            "type",
            "turn_id",
            "started_at",
            "model_context_window",
            "collaboration_mode_kind",
        }
    ),
    "item_completed": frozenset(
        {
            "type",
            "completed_at_ms",
            "item",
            "started_at_ms",
            "thread_id",
            "turn_id",
        }
    ),
    "token_count": frozenset({"type", "info", "rate_limits"}),
    "task_complete": frozenset(
        {
            "type",
            "turn_id",
            "last_agent_message",
            "started_at",
            "completed_at",
            "duration_ms",
            "time_to_first_token_ms",
        }
    ),
}
PASSIVE_EVENT_ITEM_SCHEMAS = {
    "UserMessage": frozenset({"content", "id", "type"}),
    "Reasoning": frozenset({"id", "raw_content", "summary_text", "type"}),
    "AgentMessage": frozenset({"content", "id", "phase", "type"}),
}
EXPECTED_RAW_TOP_LEVEL_COUNTS = {
    "session_meta": 1,
    "event_msg": 12,
    "response_item": 13,
    "world_state": 1,
    "turn_context": 1,
}
EXPECTED_EVENT_MSG_COUNTS = {
    "task_started": 1,
    "item_completed": 9,
    "token_count": 1,
    "task_complete": 1,
}
EXPECTED_PASSIVE_EVENT_ITEM_COUNTS = {
    "UserMessage": 1,
    "Reasoning": 7,
    "AgentMessage": 1,
}
PASSIVE_NATIVE_ITEM_TYPES = frozenset(
    {
        "error",
        "agent_message",
    }
)
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")
FRAME_HASH_LINE = re.compile(
    r"^(?P<sha>[0-9a-f]{64})  "
    r"/workspace/materials/frame-dump/(?P<name>sheet-[0-9]{3}\.jpg)$"
)
IMAGE_OPEN_TAG = re.compile(
    r'^<image name=\[Image #(?P<index>[0-9]+)\] '
    r'path="/workspace/materials/frame-dump/(?P<name>sheet-[0-9]{3}\.jpg)">$'
)
START_LINE = re.compile(r"^(?P<timestamp>\S+) START allowlist=chatgpt\.com:443$")
ALLOW_LINE = re.compile(
    r"^(?P<timestamp>\S+) ALLOW authority='chatgpt\.com:443' sni='chatgpt\.com'$"
)
CLOSE_LINE = re.compile(
    r"^(?P<timestamp>\S+) CLOSE authority='chatgpt\.com:443' "
    r"client_bytes=(?P<client_bytes>[0-9]+) upstream_bytes=(?P<upstream_bytes>[0-9]+)$"
)
DENY_LINE = re.compile(
    r"^(?P<timestamp>\S+) DENY authority='(?P<authority>[^'\r\n]+)'$"
)
ERROR_LINE = re.compile(
    r"^(?P<timestamp>\S+) ERROR authority='chatgpt\.com:443' "
    r"error=gaierror\(-2, 'Name or service not known'\)$"
)
RELAY_LINE = re.compile(
    r"^(?P<timestamp>\S+) RELAY_END "
    r"direction=(?P<direction>client-to-upstream|upstream-to-client) "
    r"bytes=(?P<bytes>[0-9]+) "
    r"error=(?P<error>BrokenPipeError\(32, 'Broken pipe'\)|"
    r"ConnectionResetError\(104, 'Connection reset by peer'\))$"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8", errors="strict"))


def parse_timestamp(value: str) -> dt.datetime:
    if not isinstance(value, str) or not value:
        raise ValueError("missing timestamp")
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp has no timezone: {value!r}")
    return parsed


def require_exact_hash(path: Path, expected: str, label: str) -> str:
    if SHA256_HEX.fullmatch(expected) is None:
        raise ValueError(f"malformed pinned SHA-256 for {label}")
    actual = sha256(path)
    if actual != expected:
        raise ValueError(f"{label} SHA-256 {actual} != pinned {expected}")
    return actual


def snapshot_hashes(paths: dict[str, Path]) -> dict[str, str]:
    return {label: sha256(path) for label, path in paths.items()}


def assert_snapshot_unchanged(
    paths: dict[str, Path], before: dict[str, str]
) -> None:
    after = snapshot_hashes(paths)
    changed = [label for label in paths if before.get(label) != after.get(label)]
    if changed:
        raise ValueError("evidence changed during validation: " + ", ".join(changed))


def validate_output_is_disjoint(
    output: Path,
    evidence_paths: dict[str, Path],
    protected_roots: tuple[Path, ...],
) -> Path:
    resolved_output = output.resolve()
    for label, path in evidence_paths.items():
        resolved_input = path.resolve()
        if resolved_output == resolved_input:
            raise ValueError(f"output aliases evidence input: {label}")
        if output.exists() and path.exists() and output.samefile(path):
            raise ValueError(f"output is same file as evidence input: {label}")
    for root in protected_roots:
        try:
            resolved_output.relative_to(root.resolve())
        except ValueError:
            continue
        raise ValueError(f"output is inside protected evidence root: {root}")
    return resolved_output


def locate_session_file(trial: Path) -> Path:
    root = trial / "steps" / "solve" / "agent" / "sessions"
    files = sorted(root.rglob("*.jsonl")) if root.exists() else []
    if len(files) != 1:
        raise ValueError(f"expected exactly one raw session JSONL, found {len(files)}")
    return files[0]


def expected_wrapped_instruction(instruction: str) -> str:
    note = f"""

---

Calibration harness delivery note (not task evidence): the complete frame dump is
attached to this initial message as {EXPECTED_FRAME_SHEETS} chronological contact-sheet
images. Each 40x30 sheet is ordered left-to-right and then top-to-bottom, and the
sheets are ordered by filename. The original task instruction above is unchanged;
where it names `/workspace/materials/match.mp4`, use the attached images as the
ablation's only visual evidence.

This is a zero-model-tool ablation. Do not call or request any tool. Return only the
JSON object that belongs in `/workspace/output/solution.json`, with no Markdown
fence or explanatory text. The calibration harness will validate and save that
final JSON response after the model turn ends.
"""
    return instruction + note


def parse_original_frame_manifest(path: Path, expected_count: int) -> list[dict]:
    lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    if len(lines) != expected_count:
        raise ValueError(
            f"frame hash manifest has {len(lines)} lines, expected {expected_count}"
        )
    entries = []
    for index, line in enumerate(lines, start=1):
        match = FRAME_HASH_LINE.fullmatch(line)
        if match is None:
            raise ValueError(f"malformed frame hash manifest line {index}")
        expected_name = f"sheet-{index:03d}.jpg"
        if match.group("name") != expected_name:
            raise ValueError(f"out-of-order frame hash manifest line {index}")
        entries.append({"name": expected_name, "sha256": match.group("sha")})
    if len({entry["sha256"] for entry in entries}) != expected_count:
        raise ValueError("frame hash manifest contains duplicate image hashes")
    return entries


def jpeg_dimensions(data: bytes) -> tuple[int, int]:
    """Fully decode a JPEG payload and return its dimensions."""
    if len(data) < 4 or not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
        raise ValueError("input_image is not a complete JPEG byte stream")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format != "JPEG":
                raise ValueError("input_image decoder format is not JPEG")
            image.load()
            dimensions = image.size
    except (OSError, SyntaxError, UnidentifiedImageError) as exc:
        raise ValueError(f"input_image is not a fully decodable JPEG: {exc}") from exc
    if (
        not isinstance(dimensions, tuple)
        or len(dimensions) != 2
        or any(not isinstance(value, int) or value <= 0 for value in dimensions)
    ):
        raise ValueError("decoded JPEG has invalid dimensions")
    return dimensions


def normalize_solution_json(final_text: str) -> bytes:
    stripped = final_text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            stripped = "\n".join(lines[1:-1]).strip()
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"final assistant response is not standalone JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise TypeError("final assistant response is not a JSON object")
    if not isinstance(parsed.get("break_points"), list):
        raise TypeError("final assistant JSON lacks a break_points array")
    return (json.dumps(parsed, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def validate_solution_materialization(final_text: str, submitted: bytes) -> dict:
    normalized = normalize_solution_json(final_text)
    if normalized != submitted:
        raise ValueError(
            "normalized final assistant JSON differs from submitted solution bytes"
        )
    parsed = json.loads(submitted)
    return {
        "normalized_byte_equality": True,
        "submitted_bytes": len(submitted),
        "predicted_events": len(parsed["break_points"]),
    }


def validate_raw_session(
    path: Path,
    original_entries: list[dict],
    wrapped_instruction: str,
    expected_count: int,
    expected_dimensions: tuple[int, int],
    expected_processed_manifest_sha256: str | None,
    expected_original_processed_hash_matches: int | None,
    require_formal_envelope: bool = True,
) -> dict:
    event_counts: Counter[str] = Counter()
    event_msg_counts: Counter[str] = Counter()
    passive_event_item_counts: Counter[str] = Counter()
    response_item_counts: Counter[str] = Counter()
    assistant_messages: list[tuple[str | None, str, str]] = []
    event_msg_agent_messages: list[str] = []
    event_msg_user_messages: list[list[dict]] = []
    task_complete_messages: list[str] = []
    image_message_seen = False
    processed_entries: list[dict] = []
    all_timestamps: list[dt.datetime] = []
    event_count = 0

    with path.open("r", encoding="utf-8", errors="strict") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.endswith("\n"):
                raise ValueError(f"raw session line {line_number} lacks newline terminator")
            if not line.strip():
                raise ValueError(f"raw session line {line_number} is blank")
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"malformed raw session JSONL at line {line_number}: {exc}"
                ) from exc
            if not isinstance(event, dict):
                raise TypeError(f"raw session event {line_number} is not an object")
            if set(event) != {"ordinal", "payload", "timestamp", "type"}:
                raise ValueError(f"raw session event {line_number} envelope is not exact")
            if type(event.get("ordinal")) is not int or event["ordinal"] != line_number - 1:
                raise ValueError(f"raw session ordinal is not exact at line {line_number}")
            event_count += 1
            event_type = event.get("type")
            if not isinstance(event_type, str):
                raise TypeError(f"raw session event {line_number} has no string type")
            if event_type not in PASSIVE_RAW_TOP_LEVEL_TYPES:
                raise ValueError(
                    f"active or unknown raw top-level event: {event_type!r}"
                )
            payload = event.get("payload")
            if not isinstance(payload, dict):
                raise TypeError(f"raw {event_type} payload is not an object")
            all_timestamps.append(parse_timestamp(event.get("timestamp")))
            event_counts[event_type] += 1

            if event_type == "event_msg":
                payload_type = payload.get("type")
                if payload_type not in PASSIVE_EVENT_MSG_TYPES:
                    raise ValueError(
                        f"active or unknown event_msg payload: {payload_type!r}"
                    )
                if set(payload) != PASSIVE_EVENT_MSG_SCHEMAS[payload_type]:
                    raise ValueError(
                        f"event_msg {payload_type} schema is not exact"
                    )
                event_msg_counts[str(payload_type)] += 1
                if payload_type == "item_completed":
                    item = payload.get("item")
                    if not isinstance(item, dict):
                        raise TypeError("event_msg item_completed item is not an object")
                    item_type = item.get("type")
                    expected_keys = PASSIVE_EVENT_ITEM_SCHEMAS.get(item_type)
                    if expected_keys is None:
                        raise ValueError(
                            f"active or unknown completed event item: {item_type!r}"
                        )
                    if set(item) != expected_keys:
                        raise ValueError(
                            f"completed {item_type} event item schema is not exact"
                        )
                    passive_event_item_counts[str(item_type)] += 1
                    if item_type == "UserMessage":
                        content = item.get("content")
                        if not isinstance(content, list):
                            raise TypeError("event_msg UserMessage content is not a list")
                        event_msg_user_messages.append(content)
                    elif item_type == "AgentMessage":
                        content = item.get("content")
                        if (
                            item.get("phase") != "final_answer"
                            or not isinstance(content, list)
                            or len(content) != 1
                            or not isinstance(content[0], dict)
                            or content[0].get("type") != "Text"
                            or set(content[0]) != {"type", "text"}
                            or not isinstance(content[0].get("text"), str)
                        ):
                            raise ValueError(
                                "event_msg AgentMessage final content is not exact"
                            )
                        event_msg_agent_messages.append(content[0]["text"])
                elif payload_type == "task_complete":
                    last_message = payload.get("last_agent_message")
                    if not isinstance(last_message, str):
                        raise TypeError("task_complete last_agent_message is not text")
                    task_complete_messages.append(last_message)
                continue

            if event_type != "response_item":
                continue

            payload_type = payload.get("type")
            if payload_type not in PASSIVE_RESPONSE_ITEM_TYPES:
                raise ValueError(
                    f"active or unknown response item in zero-call run: {payload_type!r}"
            )
            response_item_counts[str(payload_type)] += 1

            if payload_type != "message":
                continue
            role = payload.get("role")
            if role not in {"developer", "user", "assistant"}:
                raise ValueError(f"unexpected raw message role: {role!r}")
            content = payload.get("content")
            if not isinstance(content, list):
                raise TypeError("raw message content is not a list")
            if any(not isinstance(block, dict) for block in content):
                raise TypeError("raw message contains a non-object content block")
            content_types = [block.get("type") for block in content]
            passive_content_types = (
                {"output_text"} if role == "assistant" else {"input_text", "input_image"}
            )
            if any(block_type not in passive_content_types for block_type in content_types):
                raise ValueError("raw message contains an active or unknown content block")
            image_count = sum(
                isinstance(block, dict) and block.get("type") == "input_image"
                for block in content
            )
            if image_count:
                if role != "user" or image_message_seen:
                    raise ValueError("input images are not confined to one user message")
                image_message_seen = True
                if image_count != expected_count:
                    raise ValueError(
                        f"raw image message has {image_count} images, expected {expected_count}"
                    )
                if len(content) != expected_count * 3 + 1:
                    raise ValueError("raw image message has an unexpected block layout")
                for index in range(1, expected_count + 1):
                    base_index = (index - 1) * 3
                    open_block, image_block, close_block = content[
                        base_index : base_index + 3
                    ]
                    expected_name = f"sheet-{index:03d}.jpg"
                    if (
                        not isinstance(open_block, dict)
                        or open_block.get("type") != "input_text"
                        or not isinstance(open_block.get("text"), str)
                    ):
                        raise ValueError(f"image {index} lacks its exact opening tag")
                    tag_match = IMAGE_OPEN_TAG.fullmatch(open_block["text"])
                    if (
                        tag_match is None
                        or int(tag_match.group("index")) != index
                        or tag_match.group("name") != expected_name
                    ):
                        raise ValueError(f"image {index} path/name tag is out of order")
                    if close_block != {"type": "input_text", "text": "</image>"}:
                        raise ValueError(f"image {index} lacks its exact closing tag")
                    if not isinstance(image_block, dict) or set(image_block) != {
                        "type",
                        "image_url",
                        "detail",
                    }:
                        raise ValueError(f"image {index} block schema is not exact")
                    if image_block.get("type") != "input_image":
                        raise ValueError(f"image {index} block has wrong type")
                    if image_block.get("detail") != "high":
                        raise ValueError(f"image {index} detail is not high")
                    image_url = image_block.get("image_url")
                    prefix = "data:image/jpeg;base64,"
                    if not isinstance(image_url, str) or not image_url.startswith(prefix):
                        raise ValueError(f"image {index} is not an inline JPEG data URL")
                    try:
                        decoded = base64.b64decode(
                            image_url[len(prefix) :], validate=True
                        )
                    except (ValueError, base64.binascii.Error) as exc:
                        raise ValueError(f"image {index} has invalid base64") from exc
                    dimensions = jpeg_dimensions(decoded)
                    if dimensions != expected_dimensions:
                        raise ValueError(
                            f"image {index} dimensions {dimensions} != {expected_dimensions}"
                        )
                    processed_entries.append(
                        {
                            "name": expected_name,
                            "sha256": hashlib.sha256(decoded).hexdigest(),
                            "bytes": len(decoded),
                        }
                    )
                instruction_block = content[-1]
                if instruction_block != {
                    "type": "input_text",
                    "text": wrapped_instruction,
                }:
                    raise ValueError("raw image message does not end with exact wrapped task")

            if role == "assistant":
                if payload.get("phase") != "final_answer":
                    raise ValueError("assistant message is not marked final_answer")
                if (
                    len(content) != 1
                    or not isinstance(content[0], dict)
                    or set(content[0]) != {"type", "text"}
                    or content[0].get("type") != "output_text"
                    or not isinstance(content[0].get("text"), str)
                ):
                    raise ValueError("final assistant content schema is not exact")
                assistant_messages.append(
                    (payload.get("phase"), content[0]["text"], event["timestamp"])
                )

    if event_count == 0:
        raise ValueError("raw session is empty")
    if require_formal_envelope:
        if dict(event_counts) != EXPECTED_RAW_TOP_LEVEL_COUNTS:
            raise ValueError(
                f"raw top-level counts {dict(event_counts)!r} != pinned "
                f"{EXPECTED_RAW_TOP_LEVEL_COUNTS!r}"
            )
        if dict(event_msg_counts) != EXPECTED_EVENT_MSG_COUNTS:
            raise ValueError(
                f"event_msg counts {dict(event_msg_counts)!r} != pinned "
                f"{EXPECTED_EVENT_MSG_COUNTS!r}"
            )
        if dict(passive_event_item_counts) != EXPECTED_PASSIVE_EVENT_ITEM_COUNTS:
            raise ValueError(
                "passive event item counts do not equal the pinned run"
            )
    if len(processed_entries) != expected_count or not image_message_seen:
        raise ValueError("raw session does not contain the complete image message")
    if len(assistant_messages) != 1:
        raise ValueError(
            f"raw session has {len(assistant_messages)} final assistant messages"
        )
    if any(
        all_timestamps[index] > all_timestamps[index + 1]
        for index in range(len(all_timestamps) - 1)
    ):
        raise ValueError("raw session timestamps are not ordered")
    if len({entry["sha256"] for entry in processed_entries}) != expected_count:
        raise ValueError("processed session images contain duplicate byte hashes")

    if require_formal_envelope:
        if len(event_msg_user_messages) != 1:
            raise ValueError("raw event_msg layer lacks one UserMessage")
        event_user_content = event_msg_user_messages[0]
        expected_event_user_content = [
            {
                "type": "local_image",
                "path": (
                    "/workspace/materials/frame-dump/"
                    f"sheet-{index:03d}.jpg"
                ),
            }
            for index in range(1, expected_count + 1)
        ] + [
            {
                "type": "text",
                "text": wrapped_instruction,
                "text_elements": [],
            }
        ]
        if event_user_content != expected_event_user_content:
            raise ValueError(
                "event_msg UserMessage paths/task differ from response_item layer"
            )
        final_text = assistant_messages[0][1]
        if event_msg_agent_messages != [final_text]:
            raise ValueError(
                "event_msg AgentMessage differs from response_item final answer"
            )
        if task_complete_messages != [final_text]:
            raise ValueError(
                "task_complete message differs from response_item final answer"
            )

    processed_manifest = "".join(
        f"{entry['sha256']}  /workspace/materials/frame-dump/{entry['name']}\n"
        for entry in processed_entries
    ).encode("utf-8")
    aggregate = hashlib.sha256(processed_manifest).hexdigest()
    if (
        expected_processed_manifest_sha256 is not None
        and aggregate != expected_processed_manifest_sha256
    ):
        raise ValueError(
            f"processed-image manifest SHA-256 {aggregate} != pinned "
            f"{expected_processed_manifest_sha256}"
        )
    original_by_name = {entry["name"]: entry["sha256"] for entry in original_entries}
    match_count = sum(
        original_by_name.get(entry["name"]) == entry["sha256"]
        for entry in processed_entries
    )
    if (
        expected_original_processed_hash_matches is not None
        and match_count != expected_original_processed_hash_matches
    ):
        raise ValueError(
            f"original/session image hash match count {match_count} != expected "
            f"{expected_original_processed_hash_matches}"
        )

    return {
        "event_count": event_count,
        "event_type_counts": dict(sorted(event_counts.items())),
        "event_msg_type_counts": dict(sorted(event_msg_counts.items())),
        "passive_event_item_type_counts": dict(
            sorted(passive_event_item_counts.items())
        ),
        "response_item_type_counts": dict(sorted(response_item_counts.items())),
        "active_response_items": 0,
        "model_tool_calls_observed": 0,
        "input_image_count": len(processed_entries),
        "processed_image_total_bytes": sum(
            entry["bytes"] for entry in processed_entries
        ),
        "processed_image_manifest_sha256": aggregate,
        "processed_first_sha256": processed_entries[0]["sha256"],
        "processed_last_sha256": processed_entries[-1]["sha256"],
        "original_to_session_hash_match_count": match_count,
        "original_to_session_byte_equality": match_count == expected_count,
        "final_text": assistant_messages[0][1],
        "final_timestamp": assistant_messages[0][2],
        "first_response_timestamp": all_timestamps[0].isoformat(),
        "last_response_timestamp": all_timestamps[-1].isoformat(),
    }


def validate_native_stream(
    path: Path,
    expected_final_text: str,
    require_formal_envelope: bool = True,
) -> dict:
    lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    expected_headers = [
        (
            "WARNING: proceeding, even though we could not create PATH aliases: "
            "Refusing to create helper binaries under temporary dir \"/tmp\" "
            "(codex_home: AbsolutePathBuf(\"/tmp/codex-home\"))"
        ),
        "Reading additional input from stdin...",
    ]
    if lines[:2] != expected_headers:
        raise ValueError("native Codex stream has unexpected non-JSON headers")
    events = []
    for line_number, line in enumerate(lines[2:], start=3):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"malformed native Codex JSON at line {line_number}: {exc}"
            ) from exc
        if not isinstance(event, dict):
            raise TypeError(f"native Codex event {line_number} is not an object")
        events.append(event)
    if not events:
        raise ValueError("native Codex stream has no JSON events")
    allowed_event_types = {
        "thread.started",
        "turn.started",
        "item.completed",
        "error",
        "turn.completed",
    }
    unknown = [
        event.get("type")
        for event in events
        if event.get("type") not in allowed_event_types
    ]
    if unknown:
        raise ValueError(
            f"active or unknown native Codex event types: {unknown!r}"
        )
    event_type_counts = Counter(event["type"] for event in events)
    expected_event_type_counts = {
        "thread.started": 1,
        "item.completed": 3,
        "turn.started": 1,
        "error": 5,
        "turn.completed": 1,
    }
    if require_formal_envelope and dict(event_type_counts) != expected_event_type_counts:
        raise ValueError("native Codex event counts do not equal the pinned run")
    if sum(event.get("type") == "thread.started" for event in events) != 1:
        raise ValueError("native Codex stream lacks exactly one thread start")
    if sum(event.get("type") == "turn.started" for event in events) != 1:
        raise ValueError("native Codex stream lacks exactly one turn start")
    completed = [event for event in events if event.get("type") == "turn.completed"]
    if len(completed) != 1 or any(event.get("type") == "turn.failed" for event in events):
        raise ValueError("native Codex stream lacks exactly one successful turn")
    final_messages = []
    passive_item_counts: Counter[str] = Counter()
    for event in events:
        event_type = event["type"]
        item = event.get("item")
        if event_type == "thread.started":
            if set(event) != {"type", "thread_id"} or not isinstance(
                event.get("thread_id"), str
            ):
                raise ValueError("native thread.started schema is not exact")
            continue
        if event_type == "turn.started":
            if set(event) != {"type"}:
                raise ValueError("native turn.started schema is not exact")
            continue
        if event_type == "error":
            message = event.get("message")
            if set(event) != {"type", "message"} or not isinstance(message, str):
                raise ValueError("native reconnect error schema is not exact")
            if not message.startswith("Reconnecting..."):
                raise ValueError("native top-level error is not a reconnect event")
            continue
        if event_type == "turn.completed":
            if set(event) != {"type", "usage"}:
                raise ValueError("native turn.completed schema is not exact")
            continue
        if event_type != "item.completed" or set(event) != {"type", "item"}:
            raise ValueError("native item envelope is not exact")
        if not isinstance(item, dict):
            raise TypeError("native completed item is not an object")
        item_type = item.get("type")
        if item_type not in PASSIVE_NATIVE_ITEM_TYPES:
            raise ValueError(
                f"active or unknown native completed item: {item_type!r}"
            )
        passive_item_counts[str(item_type)] += 1
        if item_type == "error":
            if set(item) != {"id", "type", "message"} or not isinstance(
                item.get("message"), str
            ):
                raise ValueError("native completed error schema is not exact")
            allowed_error_prefixes = (
                "Code Mode is unavailable because code-mode host is disabled.",
                "Falling back from WebSockets to HTTPS transport.",
            )
            if not item["message"].startswith(allowed_error_prefixes):
                raise ValueError("native completed error is outside passive allowlist")
        else:
            if set(item) != {"id", "type", "text"} or not isinstance(
                item.get("text"), str
            ):
                raise ValueError("native agent_message schema is not exact")
            final_messages.append(item["text"])
    if require_formal_envelope and dict(passive_item_counts) != {
        "error": 2,
        "agent_message": 1,
    }:
        raise ValueError("native passive item counts do not equal the pinned run")
    if final_messages != [expected_final_text]:
        raise ValueError("native and raw-session final assistant text differ")
    usage = completed[0].get("usage")
    if not isinstance(usage, dict) or any(
        not isinstance(usage.get(key), int) or isinstance(usage.get(key), bool)
        for key in (
            "input_tokens",
            "cached_input_tokens",
            "cache_write_input_tokens",
            "output_tokens",
            "reasoning_output_tokens",
        )
    ):
        raise ValueError("native Codex completion usage is malformed")
    return {
        "json_event_count": len(events),
        "event_type_counts": dict(sorted(event_type_counts.items())),
        "passive_item_type_counts": dict(sorted(passive_item_counts.items())),
        "native_tool_operations": 0,
        "usage": usage,
    }


def validate_reward_consistency(payload: dict) -> tuple[float | int, dict]:
    if not isinstance(payload, dict):
        raise TypeError("reward payload is not an object")
    reward = payload.get("reward")
    if (
        not isinstance(reward, (int, float))
        or isinstance(reward, bool)
        or not math.isfinite(reward)
    ):
        raise ValueError("reward is not finite numeric data")
    details = payload.get("details")
    if not isinstance(details, dict):
        raise TypeError("reward details are malformed")
    if details.get("formula") != EXPECTED_FORMULA:
        raise ValueError("reward formula is not the pinned exact-event F1")
    counts = {}
    for key in (
        "n_predicted",
        "n_ground_truth",
        "exact_event_matches_ordered",
        "reward_denominator",
    ):
        value = details.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"reward detail {key} is not a nonnegative integer")
        counts[key] = value
    if counts["n_ground_truth"] != EXPECTED_GROUND_TRUTH_EVENTS:
        raise ValueError("reward ground-truth event count is not 16")
    denominator = counts["n_predicted"] + counts["n_ground_truth"]
    if denominator <= 0 or counts["reward_denominator"] != denominator:
        raise ValueError("reward denominator is inconsistent")
    exact_matches = counts["exact_event_matches_ordered"]
    if exact_matches > min(counts["n_predicted"], counts["n_ground_truth"]):
        raise ValueError("exact event matches exceed available events")
    recomputed = round(2 * exact_matches / denominator, 4)
    if reward != recomputed:
        raise ValueError(f"reward {reward!r} != recomputed {recomputed!r}")
    if reward != EXPECTED_REWARD:
        raise ValueError(f"reward {reward!r} != pinned {EXPECTED_REWARD!r}")
    return reward, details


def regrade_with_frozen_judge(
    judge_path: Path,
    solution_path: Path,
    stored_payload: dict,
    expected_judge_sha256: str | None = None,
) -> dict:
    """Execute the frozen pure-Python judge in memory and compare every field."""
    if expected_judge_sha256 is not None:
        require_exact_hash(judge_path, expected_judge_sha256, "frozen judge")
    source = judge_path.read_text(encoding="utf-8", errors="strict")
    namespace: dict[str, Any] = {
        "__name__": "avb_frozen_judge_for_independent_regrade",
        "__file__": str(judge_path),
    }
    exec(compile(source, str(judge_path), "exec"), namespace)  # noqa: S102
    score_predictions = namespace.get("score_predictions")
    reference_events = namespace.get("REFERENCE_EVENTS")
    if not callable(score_predictions) or not isinstance(reference_events, list):
        raise TypeError("frozen judge lacks scoring function/reference events")
    if len(reference_events) != EXPECTED_GROUND_TRUTH_EVENTS:
        raise ValueError("frozen judge reference event count is not 16")

    reason = "ok"
    predictions = []
    root_schema_issue = False
    try:
        solution = json.loads(
            solution_path.read_text(encoding="utf-8", errors="strict")
        )
        if not isinstance(solution, dict):
            root_schema_issue = True
            raise TypeError("solution root is not an object")
        root_schema_issue = set(solution) != {"break_points"}
        if "break_points" not in solution:
            raise ValueError("solution must contain the break_points key")
        predictions = solution["break_points"]
        if not isinstance(predictions, list):
            raise TypeError("break_points is not a list")
    except Exception as exc:  # noqa: BLE001
        reason = f"unreadable solution.json: {exc}"
        predictions = []

    reward, details = score_predictions(predictions)
    computed_payload = {
        "reward": reward,
        "details": {
            "reason": reason,
            "root_schema_issue": root_schema_issue,
            **details,
        },
    }
    if computed_payload != stored_payload:
        raise ValueError(
            "stored reward payload differs from independent frozen-judge regrade"
        )
    return computed_payload


def validate_metadata(metadata: Any) -> dict:
    if metadata != EXPECTED_METADATA:
        raise ValueError(f"agent metadata is not exact: {metadata!r}")
    return dict(metadata)


def classify_gateway_lines(lines: list[str]) -> list[dict]:
    if not lines:
        raise ValueError("gateway log is empty")
    parsed = []
    patterns = (
        ("start", START_LINE),
        ("allow", ALLOW_LINE),
        ("close", CLOSE_LINE),
        ("deny", DENY_LINE),
        ("error", ERROR_LINE),
        ("relay", RELAY_LINE),
    )
    for index, line in enumerate(lines, start=1):
        kind = None
        match = None
        for candidate_kind, pattern in patterns:
            candidate = pattern.fullmatch(line)
            if candidate is not None:
                kind, match = candidate_kind, candidate
                break
        if kind is None or match is None:
            raise ValueError(f"gateway line {index} is outside closed-world grammar")
        parsed.append(
            {
                "kind": kind,
                "timestamp": parse_timestamp(match.group("timestamp")),
                "match": match,
                "line": line,
            }
        )
    if parsed[0]["kind"] != "start" or sum(
        entry["kind"] == "start" for entry in parsed
    ) != 1:
        raise ValueError("gateway START must be the unique first event")
    timestamps = [entry["timestamp"] for entry in parsed]
    if any(
        timestamps[index] > timestamps[index + 1]
        for index in range(len(timestamps) - 1)
    ):
        raise ValueError("gateway timestamps are not ordered")
    return parsed


def validate_gateway(
    path: Path,
    trial_started: dt.datetime,
    trial_finished: dt.datetime,
    final_response: dt.datetime,
    expected_counts: dict[str, int],
) -> dict:
    lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    parsed = classify_gateway_lines(lines)
    if any(
        not (trial_started <= entry["timestamp"] <= trial_finished)
        for entry in parsed
    ):
        raise ValueError("gateway event lies outside completed trial window")
    if parsed[0]["timestamp"] > final_response:
        raise ValueError("gateway starts after the final response")

    counts: Counter[str] = Counter(entry["kind"] for entry in parsed)
    relay_error_counts: Counter[str] = Counter()
    for entry in parsed:
        if entry["kind"] == "relay":
            error = entry["match"].group("error")
            relay_error_counts[
                "broken_pipe" if error.startswith("BrokenPipeError") else "connection_reset"
            ] += 1
        elif entry["kind"] == "deny":
            if entry["match"].group("authority") != "ab.chatgpt.com:443":
                raise ValueError("gateway contains an unexpected denied authority")
        elif entry["kind"] == "close":
            if int(entry["match"].group("client_bytes")) <= 0 or int(
                entry["match"].group("upstream_bytes")
            ) <= 0:
                raise ValueError("gateway CLOSE has nonpositive byte counts")

    actual_counts = {
        "start": counts["start"],
        "allow": counts["allow"],
        "close": counts["close"],
        "deny": counts["deny"],
        "error": counts["error"],
        "connection_reset": relay_error_counts["connection_reset"],
        "broken_pipe": relay_error_counts["broken_pipe"],
    }
    if actual_counts != expected_counts:
        raise ValueError(
            f"gateway counts {actual_counts!r} != pinned {expected_counts!r}"
        )
    if counts["allow"] != counts["close"] + counts["error"]:
        raise ValueError("gateway connection conservation failed")

    open_connections = 0
    max_open_connections = 0
    for entry in parsed:
        if entry["kind"] == "allow":
            open_connections += 1
            max_open_connections = max(max_open_connections, open_connections)
        elif entry["kind"] == "relay":
            if open_connections <= 0:
                raise ValueError("gateway relay has no preceding unmatched ALLOW")
        elif entry["kind"] in {"close", "error"}:
            if open_connections <= 0:
                raise ValueError("gateway terminal event has no preceding unmatched ALLOW")
            open_connections -= 1
    if open_connections != 0:
        raise ValueError("gateway has unmatched ALLOW connections at end of log")

    relay_block_count = 0
    index = 0
    while index < len(parsed):
        if parsed[index]["kind"] != "relay":
            index += 1
            continue
        relay_block_count += 1
        block = []
        while index < len(parsed) and parsed[index]["kind"] == "relay":
            block.append(parsed[index])
            index += 1
        if index >= len(parsed) or parsed[index]["kind"] != "close":
            raise ValueError("relay failure block is not immediately followed by CLOSE")
        paired_close = parsed[index]
        close_match = paired_close["match"]
        directions = [entry["match"].group("direction") for entry in block]
        if len(directions) != len(set(directions)):
            raise ValueError("relay failure block repeats a direction")
        for entry in block:
            direction = entry["match"].group("direction")
            error = entry["match"].group("error")
            if error.startswith("BrokenPipeError") and direction != "client-to-upstream":
                raise ValueError("BrokenPipe relay has unexpected direction")
            expected_bytes = int(
                close_match.group(
                    "client_bytes"
                    if direction == "client-to-upstream"
                    else "upstream_bytes"
                )
            )
            if int(entry["match"].group("bytes")) != expected_bytes:
                raise ValueError("relay byte count does not match paired CLOSE")
        if paired_close["timestamp"] >= final_response:
            raise ValueError("relay failure CLOSE did not finish before final response")
        later_healthy_before_final = any(
            later["kind"] == "close"
            and paired_close["timestamp"] < later["timestamp"] <= final_response
            and int(later["match"].group("upstream_bytes")) > 0
            for later in parsed[index + 1 :]
        )
        if not later_healthy_before_final:
            raise ValueError(
                "relay failure has no later healthy CLOSE before final response"
            )
        index += 1

    close_timestamps = [
        entry["timestamp"] for entry in parsed if entry["kind"] == "close"
    ]
    if not close_timestamps or close_timestamps[-1] < final_response:
        raise ValueError("gateway log does not cover the final model response")
    return {
        **actual_counts,
        "closed_world_line_count": len(parsed),
        "connection_accounting": "ordered_unmatched-ALLOW_conservation",
        "connection_ids_present": False,
        "max_concurrent_open_connections": max_open_connections,
        "relay_block_count": relay_block_count,
        "last_close_timestamp": close_timestamps[-1].isoformat(),
    }


def recompute_harbor_task_checksum(task_dir: Path) -> str:
    try:
        from harbor.models.task.task import Task
    except ModuleNotFoundError:
        harbor_cli = shutil.which("harbor")
        if harbor_cli is None:
            raise RuntimeError("Harbor is unavailable for checksum recomputation")
        harbor_python = Path(harbor_cli).resolve().parent / "python"
        completed = subprocess.run(
            [
                str(harbor_python),
                "-c",
                (
                    "from harbor.models.task.task import Task; import sys; "
                    "print(Task(sys.argv[1]).checksum)"
                ),
                str(task_dir.resolve()),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        checksum = completed.stdout.strip()
    else:
        checksum = Task(task_dir.resolve()).checksum
    if SHA256_HEX.fullmatch(checksum) is None:
        raise ValueError(f"Harbor returned malformed task checksum: {checksum!r}")
    return checksum


def inspect_image(reference: str, docker_host: str, docker_config: Path) -> dict:
    completed = subprocess.run(
        [
            "docker",
            "--host",
            docker_host,
            "--config",
            str(docker_config),
            "image",
            "inspect",
            reference,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, list) or len(payload) != 1:
        raise ValueError("Docker image inspect did not return one image")
    image = payload[0]
    if image.get("Id") != EXPECTED_IMAGE_ID:
        raise ValueError("Docker image ID differs from the pinned image")
    if EXPECTED_IMAGE_REFERENCE not in (image.get("RepoDigests") or []):
        raise ValueError("Docker image lacks the pinned repository digest")
    if image.get("Os") != "linux" or image.get("Architecture") != "arm64":
        raise ValueError("Docker image platform is not pinned linux/arm64")
    if image.get("Size") != EXPECTED_IMAGE_SIZE:
        raise ValueError("Docker image size differs from the pinned image")
    return image


def validate_result(result: dict, config: dict, overlay: Path) -> dict:
    if not isinstance(result, dict) or not isinstance(config, dict):
        raise TypeError("trial result/config is malformed")
    if result.get("config") != config:
        raise ValueError("standalone config and result-embedded config differ")
    if result.get("trial_name") != EXPECTED_TRIAL_NAME:
        raise ValueError("unexpected trial name")
    if result.get("task_checksum") != EXPECTED_TASK_CHECKSUM:
        raise ValueError("unexpected task checksum")
    if result.get("exception_info") is not None:
        raise ValueError(f"trial exception: {result.get('exception_info')!r}")
    started = parse_timestamp(result.get("started_at"))
    finished = parse_timestamp(result.get("finished_at"))
    if started > finished:
        raise ValueError("trial timestamps are reversed")
    configured_task = (config.get("task") or {}).get("path")
    if not isinstance(configured_task, str) or Path(configured_task).resolve() != overlay.resolve():
        raise ValueError("configured task path does not match overlay")
    agent_config = config.get("agent") or {}
    if agent_config.get("import_path") != EXPECTED_AGENT_IMPORT_PATH:
        raise ValueError("configured adapter import path is not pinned")
    if agent_config.get("model_name") != EXPECTED_MODEL:
        raise ValueError("configured model is not pinned")
    kwargs = agent_config.get("kwargs") or {}
    if kwargs != {
        "version": EXPECTED_AGENT_VERSION,
        "reasoning_effort": EXPECTED_REASONING_EFFORT,
    }:
        raise ValueError("configured version/reasoning effort is not exact")
    agent_info = result.get("agent_info") or {}
    if agent_info.get("name") != "codex" or agent_info.get("version") != EXPECTED_AGENT_VERSION:
        raise ValueError("result agent identity/version is not pinned")
    if (agent_info.get("model_info") or {}).get("name") != EXPECTED_MODEL:
        raise ValueError("result model is not pinned")
    steps = result.get("step_results")
    if not isinstance(steps, list) or len(steps) != 1:
        raise ValueError("trial does not have exactly one step result")
    step = steps[0]
    if step.get("step_name") != "solve" or step.get("exception_info") is not None:
        raise ValueError("solve step failed or has unexpected identity")
    execution = step.get("agent_execution") or {}
    execution_started = parse_timestamp(execution.get("started_at"))
    execution_finished = parse_timestamp(execution.get("finished_at"))
    if not (started <= execution_started <= execution_finished <= finished):
        raise ValueError("agent execution lies outside trial envelope")
    metadata = validate_metadata((step.get("agent_result") or {}).get("metadata"))
    if ((step.get("verifier_result") or {}).get("rewards") or {}).get("reward") != EXPECTED_REWARD:
        raise ValueError("step result reward is inconsistent")
    if ((result.get("verifier_result") or {}).get("rewards") or {}).get("reward") != EXPECTED_REWARD:
        raise ValueError("trial result reward is inconsistent")
    return {
        "started": started,
        "finished": finished,
        "execution_started": execution_started,
        "execution_finished": execution_finished,
        "metadata": metadata,
    }


def validate_frozen_task_files(canonical: Path, overlay: Path) -> dict[str, str]:
    result = {}
    for relative, expected in FROZEN_TASK_HASHES.items():
        canonical_path = canonical / relative
        overlay_path = overlay / relative
        canonical_bytes = canonical_path.read_bytes()
        overlay_bytes = overlay_path.read_bytes()
        if canonical_bytes != overlay_bytes:
            raise ValueError(f"canonical/overlay frozen-file mismatch: {relative}")
        actual = hashlib.sha256(overlay_bytes).hexdigest()
        if actual != expected:
            raise ValueError(f"frozen-file hash differs: {relative}")
        result[relative] = actual
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trial-dir", required=True, type=Path)
    parser.add_argument("--gateway-log", required=True, type=Path)
    parser.add_argument("--canonical-task", required=True, type=Path)
    parser.add_argument("--overlay-task", required=True, type=Path)
    parser.add_argument("--adapter-source", required=True, type=Path)
    parser.add_argument("--base-adapter-source", required=True, type=Path)
    parser.add_argument(
        "--docker-host",
        required=True,
    )
    parser.add_argument(
        "--docker-config",
        required=True,
        type=Path,
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    validator_path = Path(__file__).resolve()
    validator_sha = sha256(validator_path)
    trial = args.trial_dir.resolve()
    canonical = args.canonical_task.resolve()
    overlay = args.overlay_task.resolve()
    session_path = locate_session_file(trial)
    paths = {
        "validator": validator_path,
        "config": trial / "config.json",
        "result": trial / "result.json",
        "native_codex": trial / "steps/solve/agent/codex.txt",
        "raw_session": session_path,
        "input_manifest": trial / "steps/solve/artifacts/input-manifest.txt",
        "frame_dump_sha256": trial / "steps/solve/artifacts/frame-dump-sha256.txt",
        "artifact_manifest": trial / "steps/solve/artifacts/manifest.json",
        "materials_listing": trial / "steps/solve/artifacts/materials-listing.txt",
        "solution": trial / "steps/solve/artifacts/solution.json",
        "reward": trial / "steps/solve/verifier/reward.json",
        "gateway": args.gateway_log.resolve(),
        "adapter_source": args.adapter_source.resolve(),
        "base_adapter_source": args.base_adapter_source.resolve(),
    }
    for relative in FROZEN_TASK_HASHES:
        paths[f"canonical:{relative}"] = canonical / relative
        paths[f"overlay:{relative}"] = overlay / relative
    output_path = validate_output_is_disjoint(
        args.output,
        paths,
        (trial, canonical, overlay),
    )
    before = snapshot_hashes(paths)

    pin_map = {
        "config": "config.json",
        "result": "result.json",
        "native_codex": "native_codex_jsonl",
        "raw_session": "raw_session_jsonl",
        "input_manifest": "input_manifest",
        "frame_dump_sha256": "frame_dump_sha256",
        "artifact_manifest": "artifact_manifest",
        "materials_listing": "materials_listing",
        "solution": "submitted_solution",
        "reward": "reward_json",
        "gateway": "gateway_log",
        "adapter_source": "adapter_source",
        "base_adapter_source": "base_adapter_source",
    }
    for path_label, pin_label in pin_map.items():
        if before[path_label] != PINNED_EVIDENCE_HASHES[pin_label]:
            raise ValueError(
                f"{path_label} SHA-256 {before[path_label]} != pinned "
                f"{PINNED_EVIDENCE_HASHES[pin_label]}"
            )

    initial_overlay_checksum = recompute_harbor_task_checksum(overlay)
    if initial_overlay_checksum != EXPECTED_TASK_CHECKSUM:
        raise ValueError("current overlay checksum differs from completed run")
    frozen_hashes = validate_frozen_task_files(canonical, overlay)

    result = load_json(paths["result"])
    config = load_json(paths["config"])
    envelope = validate_result(result, config, overlay)

    manifest_lines = paths["input_manifest"].read_text(
        encoding="utf-8", errors="strict"
    ).splitlines()
    if tuple(manifest_lines) != EXPECTED_MANIFEST_LINES:
        raise ValueError("input manifest does not equal the pinned closed-world manifest")
    source_dimensions = (
        int(manifest_lines[8].split("=", 1)[1])
        * int(manifest_lines[10].split("=", 1)[1]),
        int(manifest_lines[9].split("=", 1)[1])
        * int(manifest_lines[11].split("=", 1)[1]),
    )
    if source_dimensions != EXPECTED_ORIGINAL_DIMENSIONS:
        raise ValueError("source contact-sheet dimensions are not pinned")
    original_entries = parse_original_frame_manifest(
        paths["frame_dump_sha256"], EXPECTED_FRAME_SHEETS
    )

    artifact_manifest = load_json(paths["artifact_manifest"])
    if artifact_manifest != [
        {
            "source": "/logs/artifacts",
            "destination": "artifacts",
            "type": "directory",
            "status": "ok",
        }
    ]:
        raise ValueError("artifact collection manifest is not exact")
    if paths["materials_listing"].read_text(encoding="utf-8", errors="strict") != (
        "total 24\n"
        "drwxr-xr-x 1 root root  4096 Aug 27 06:26 .\n"
        "drwxr-xr-x 1 root root  4096 Aug 27 06:26 ..\n"
        "drwxr-xr-x 2 root root 12288 Aug 27 06:31 frame-dump\n"
    ):
        raise ValueError("materials listing is not the pinned frame-dump-only listing")

    instruction = (overlay / "steps/solve/instruction.md").read_text(
        encoding="utf-8", errors="strict"
    )
    session = validate_raw_session(
        paths["raw_session"],
        original_entries,
        expected_wrapped_instruction(instruction),
        EXPECTED_FRAME_SHEETS,
        EXPECTED_SESSION_DIMENSIONS,
        EXPECTED_PROCESSED_IMAGE_MANIFEST_SHA256,
        0,
    )
    final_timestamp = parse_timestamp(session["final_timestamp"])
    if not (
        envelope["execution_started"]
        <= parse_timestamp(session["first_response_timestamp"])
        <= final_timestamp
        <= envelope["execution_finished"]
    ):
        raise ValueError("raw session response envelope is outside agent execution")
    solution = validate_solution_materialization(
        session["final_text"], paths["solution"].read_bytes()
    )
    native = validate_native_stream(paths["native_codex"], session["final_text"])
    stored_reward_payload = load_json(paths["reward"])
    independently_regraded_payload = regrade_with_frozen_judge(
        paths["overlay:steps/solve/tests/judge.py"],
        paths["solution"],
        stored_reward_payload,
        FROZEN_TASK_HASHES["steps/solve/tests/judge.py"],
    )
    reward, reward_details = validate_reward_consistency(
        independently_regraded_payload
    )
    if solution["predicted_events"] != reward_details["n_predicted"]:
        raise ValueError("submitted event count differs from verifier n_predicted")
    gateway = validate_gateway(
        paths["gateway"],
        envelope["started"],
        envelope["finished"],
        final_timestamp,
        EXPECTED_GATEWAY_COUNTS,
    )
    image = inspect_image(
        EXPECTED_IMAGE_REFERENCE, args.docker_host, args.docker_config.resolve()
    )

    final_overlay_checksum = recompute_harbor_task_checksum(overlay)
    if final_overlay_checksum != initial_overlay_checksum:
        raise ValueError("overlay task changed during validation")
    assert_snapshot_unchanged(paths, before)
    if sha256(validator_path) != validator_sha:
        raise ValueError("validator changed during validation")

    report = {
        "schema_version": SCHEMA_VERSION,
        "validation_policy": VALIDATION_POLICY,
        "valid": True,
        "validator_sha256": validator_sha,
        "trial_name": result["trial_name"],
        "task_checksum": result["task_checksum"],
        "overlay_task_checksum_recomputed": initial_overlay_checksum,
        "trial_exception": None,
        "step_exception": None,
        "model": EXPECTED_MODEL,
        "reasoning_effort": EXPECTED_REASONING_EFFORT,
        "agent": {"name": "codex", "version": EXPECTED_AGENT_VERSION},
        "agent_import_path": EXPECTED_AGENT_IMPORT_PATH,
        "metadata": envelope["metadata"],
        "claim_boundary": {
            "proved": "observed_zero_model_tool_calls_in_preserved_raw_session",
            "model_tool_calls_observed": 0,
            "backend_tools_array_empty": "not_proven",
            "backend_tool_choice_none": "not_proven",
            "policy_is_not_backend_tools_empty_proof": True,
        },
        "frame_evidence": {
            "frame_sheet_count": EXPECTED_FRAME_SHEETS,
            "claim_scope": "ordered_session_image_payloads",
            "original_hash_manifest_line_count": len(original_entries),
            "original_hash_manifest_sha256": before["frame_dump_sha256"],
            "original_dimensions": list(EXPECTED_ORIGINAL_DIMENSIONS),
            "session_dimensions": list(EXPECTED_SESSION_DIMENSIONS),
            "session_jpeg_full_decode_passed": True,
            "session_jpeg_decoder": f"Pillow {PIL.__version__}",
            "codex_cli_preprocessing": "2560x1080_to_2048x864",
            "processed_image_manifest_sha256": session[
                "processed_image_manifest_sha256"
            ],
            "processed_image_total_bytes": session["processed_image_total_bytes"],
            "processed_first_sha256": session["processed_first_sha256"],
            "processed_last_sha256": session["processed_last_sha256"],
            "original_to_session_hash_match_count": session[
                "original_to_session_hash_match_count"
            ],
            "original_to_session_byte_equality": False,
            "cryptographic_source-to-processed_mapping": (
                "not_reconstructed_post_run"
            ),
        },
        "raw_session": {
            "sha256": before["raw_session"],
            "event_count": session["event_count"],
            "event_type_counts": session["event_type_counts"],
            "event_msg_type_counts": session["event_msg_type_counts"],
            "passive_event_item_type_counts": session[
                "passive_event_item_type_counts"
            ],
            "response_item_type_counts": session["response_item_type_counts"],
            "active_response_items": 0,
            "active_or_unknown_top_level_events": 0,
            "active_or_unknown_event_msg_items": 0,
            "model_tool_calls_observed": 0,
            "input_image_count": session["input_image_count"],
            "single_image_bearing_user_message": True,
            "exact_ordered_image_path_tags": True,
            "strict_jsonl": True,
            "operation_bearing_layers_closed_world": True,
            "non_execution_context_payloads_exact_schema": False,
        },
        "native_codex_stream": {
            "sha256": before["native_codex"],
            **native,
        },
        "solution_materialization": {
            **solution,
            "materialized_by": "harbor_adapter",
            "post_hoc_after_zero_call_audit": True,
            "submitted_solution_sha256": before["solution"],
        },
        "reward": reward,
        "reward_independently_recomputed_from_frozen_judge": True,
        "stored_reward_equals_independent_regrade": True,
        "reward_inputs": {
            "n_predicted": reward_details["n_predicted"],
            "n_ground_truth": reward_details["n_ground_truth"],
            "exact_event_matches_ordered": reward_details[
                "exact_event_matches_ordered"
            ],
            "reward_denominator": reward_details["reward_denominator"],
        },
        "soft_event_f1": reward_details.get("soft_event_f1"),
        "formula": reward_details["formula"],
        "gateway": {"sha256": before["gateway"], **gateway},
        "image": {
            "reference": EXPECTED_IMAGE_REFERENCE,
            "id": image["Id"],
            "os": image["Os"],
            "architecture": image["Architecture"],
            "size": image["Size"],
        },
        "hashes": {
            "frozen_task_files": frozen_hashes,
            "config_json": before["config"],
            "result_json": before["result"],
            "input_manifest": before["input_manifest"],
            "frame_dump_sha256": before["frame_dump_sha256"],
            "artifact_manifest": before["artifact_manifest"],
            "materials_listing": before["materials_listing"],
            "reward_json": before["reward"],
            "submitted_solution": before["solution"],
            "adapter_source": before["adapter_source"],
            "base_adapter_source": before["base_adapter_source"],
        },
        "started_at": result["started_at"],
        "finished_at": result["finished_at"],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=output_path.parent,
        prefix=f".{output_path.name}.tmp-",
        delete=False,
    ) as handle:
        handle.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
        temporary_output = Path(handle.name)
    os.replace(temporary_output, output_path)
    assert_snapshot_unchanged(paths, before)
    if sha256(validator_path) != validator_sha:
        raise ValueError("validator changed while report was written")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
