#!/usr/bin/env python3
"""Deterministically redact bulky or account-scoped fields from a JSONL session."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DATA_URL = re.compile(
    rb'"data:image/([A-Za-z0-9.+-]+);base64,([A-Za-z0-9+/=]+)"'
)
ENCRYPTED_CONTENT_KEY = re.compile(rb'(?<!\\)"encrypted_content"\s*:\s*')
RATE_LIMITS_KEY = re.compile(rb'(?<!\\)"rate_limits"\s*:\s*')
REDACTION_KEYS = frozenset({"redacted", "bytes", "sha256"})


@dataclass(frozen=True)
class Redaction:
    start: int
    end: int
    replacement: bytes
    kind: str
    metadata: dict[str, object]


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def compact_redaction(length: int, digest: str) -> bytes:
    return (
        f'{{"redacted":true,"bytes":{length},"sha256":"{digest}"}}'
    ).encode("ascii")


def json_string_end(payload: bytes, start: int) -> int:
    if start >= len(payload) or payload[start] != ord('"'):
        raise ValueError("expected JSON string")
    escaped = False
    for index in range(start + 1, len(payload)):
        byte = payload[index]
        if escaped:
            escaped = False
        elif byte == ord("\\"):
            escaped = True
        elif byte == ord('"'):
            return index + 1
    raise ValueError("unterminated JSON string")


def json_container_end(payload: bytes, start: int) -> int:
    if start >= len(payload) or payload[start] not in (ord("{"), ord("[")):
        raise ValueError("expected JSON container")
    stack = [payload[start]]
    in_string = False
    escaped = False
    for index in range(start + 1, len(payload)):
        byte = payload[index]
        if in_string:
            if escaped:
                escaped = False
            elif byte == ord("\\"):
                escaped = True
            elif byte == ord('"'):
                in_string = False
            continue
        if byte == ord('"'):
            in_string = True
        elif byte in (ord("{"), ord("[")):
            stack.append(byte)
        elif byte in (ord("}"), ord("]")):
            expected = ord("{") if byte == ord("}") else ord("[")
            if not stack or stack[-1] != expected:
                raise ValueError("unbalanced JSON container")
            stack.pop()
            if not stack:
                return index + 1
    raise ValueError("unterminated JSON container")


def key_value_start(payload: bytes, key_match: re.Match[bytes]) -> int:
    start = key_match.end()
    while start < len(payload) and payload[start] in b" \t\r\n":
        start += 1
    return start


def find_image_redactions(payload: bytes) -> list[Redaction]:
    redactions: list[Redaction] = []
    for ordinal, match in enumerate(DATA_URL.finditer(payload), start=1):
        mime_subtype = match.group(1).decode("ascii")
        decoded = base64.b64decode(match.group(2), validate=True)
        digest = sha256_bytes(decoded)
        redactions.append(
            Redaction(
                start=match.start(),
                end=match.end(),
                replacement=compact_redaction(len(decoded), digest),
                kind="image",
                metadata={
                    "ordinal": ordinal,
                    "mime_type": f"image/{mime_subtype}",
                    "decoded_bytes": len(decoded),
                    "sha256": digest,
                },
            )
        )
    return redactions


def find_encrypted_content_redactions(payload: bytes) -> list[Redaction]:
    redactions: list[Redaction] = []
    for ordinal, match in enumerate(ENCRYPTED_CONTENT_KEY.finditer(payload), start=1):
        start = key_value_start(payload, match)
        end = json_string_end(payload, start)
        decoded = json.loads(payload[start:end].decode("utf-8"))
        if not isinstance(decoded, str):
            raise ValueError("encrypted_content must be a JSON string")
        decoded_bytes = decoded.encode("utf-8")
        digest = sha256_bytes(decoded_bytes)
        redactions.append(
            Redaction(
                start=start,
                end=end,
                replacement=compact_redaction(len(decoded_bytes), digest),
                kind="encrypted_content",
                metadata={
                    "ordinal": ordinal,
                    "decoded_bytes": len(decoded_bytes),
                    "sha256": digest,
                },
            )
        )
    return redactions


def find_rate_limit_redactions(payload: bytes) -> list[Redaction]:
    redactions: list[Redaction] = []
    for ordinal, match in enumerate(RATE_LIMITS_KEY.finditer(payload), start=1):
        start = key_value_start(payload, match)
        end = json_container_end(payload, start)
        serialized = payload[start:end]
        parsed = json.loads(serialized)
        if not isinstance(parsed, dict):
            raise ValueError("rate_limits must be a JSON object")
        digest = sha256_bytes(serialized)
        redactions.append(
            Redaction(
                start=start,
                end=end,
                replacement=compact_redaction(len(serialized), digest),
                kind="rate_limits",
                metadata={
                    "ordinal": ordinal,
                    "serialized_bytes": len(serialized),
                    "sha256": digest,
                },
            )
        )
    return redactions


def validate_nonoverlapping(redactions: list[Redaction]) -> None:
    for previous, current in zip(redactions, redactions[1:]):
        if previous.end > current.start:
            raise ValueError(
                f"overlapping {previous.kind} and {current.kind} redactions"
            )


def apply_redactions(
    payload: bytes, redactions: list[Redaction]
) -> tuple[bytes, str]:
    output = bytearray()
    outside_digest = hashlib.sha256()
    cursor = 0
    for redaction in redactions:
        preserved = payload[cursor : redaction.start]
        output.extend(preserved)
        outside_digest.update(preserved)
        output.extend(redaction.replacement)
        cursor = redaction.end
    preserved = payload[cursor:]
    output.extend(preserved)
    outside_digest.update(preserved)
    return bytes(output), outside_digest.hexdigest()


def jsonl_events(payload: bytes) -> list[Any]:
    events: list[Any] = []
    for line_number, line in enumerate(payload.splitlines(), start=1):
        if not line.strip():
            raise ValueError(f"blank JSONL line {line_number}")
        events.append(json.loads(line))
    return events


def is_redaction(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == REDACTION_KEYS
        and value.get("redacted") is True
        and isinstance(value.get("bytes"), int)
        and isinstance(value.get("sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is not None
    )


def audit_projection(value: Any, key: str | None = None) -> Any:
    if key == "encrypted_content":
        return "<encrypted-content-redacted>"
    if key == "rate_limits":
        return "<account-rate-limits-redacted>"
    if isinstance(value, str) and value.startswith("data:image/") and ";base64," in value:
        return "<image-payload-redacted>"
    if is_redaction(value):
        return "<image-payload-redacted>"
    if isinstance(value, dict):
        return {
            child_key: audit_projection(child_value, child_key)
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [audit_projection(item) for item in value]
    return value


def projection_sha256(events: list[Any]) -> str:
    digest = hashlib.sha256()
    for event in events:
        digest.update(
            json.dumps(
                audit_projection(event),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def aggregate(entries: list[dict[str, object]], size_key: str) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(
            (
                f'{entry["ordinal"]}\t{entry[size_key]}\t'
                f'{entry["sha256"]}\n'
            ).encode("ascii")
        )
    return digest.hexdigest()


def sanitize(source: Path, destination: Path, manifest_path: Path) -> dict:
    original = source.read_bytes()
    redactions = sorted(
        find_image_redactions(original)
        + find_encrypted_content_redactions(original)
        + find_rate_limit_redactions(original),
        key=lambda item: item.start,
    )
    validate_nonoverlapping(redactions)

    images = [item.metadata for item in redactions if item.kind == "image"]
    encrypted = [
        item.metadata for item in redactions if item.kind == "encrypted_content"
    ]
    rate_limits = [
        item.metadata for item in redactions if item.kind == "rate_limits"
    ]
    if not images:
        raise ValueError("no base64 image payloads found")
    if not encrypted:
        raise ValueError("no encrypted_content payloads found")
    if not rate_limits:
        raise ValueError("no rate_limits metadata found")

    sanitized, outside_digest = apply_redactions(original, redactions)
    original_events = jsonl_events(original)
    sanitized_events = jsonl_events(sanitized)
    if len(original_events) != len(sanitized_events):
        raise ValueError("JSONL event count changed")
    original_projection = projection_sha256(original_events)
    sanitized_projection = projection_sha256(sanitized_events)
    if original_projection != sanitized_projection:
        raise ValueError("non-redacted JSON evidence changed")

    destination.write_bytes(sanitized)
    manifest = {
        "schema_version": "avb-frame-dump-session-sanitization-v2",
        "transformations": [
            {
                "target": "quoted data:image/*;base64 values",
                "replacement": (
                    "{redacted:true,bytes:<decoded bytes>,sha256:<decoded sha256>}"
                ),
                "count": len(images),
            },
            {
                "target": "payload.encrypted_content string values",
                "replacement": (
                    "{redacted:true,bytes:<decoded UTF-8 bytes>,"
                    "sha256:<decoded SHA-256>}"
                ),
                "count": len(encrypted),
            },
            {
                "target": "payload.rate_limits object values",
                "replacement": (
                    "{redacted:true,bytes:<serialized bytes>,"
                    "sha256:<serialized SHA-256>}"
                ),
                "count": len(rate_limits),
            },
        ],
        "original": {
            "file": source.name,
            "bytes": len(original),
            "sha256": sha256_bytes(original),
            "jsonl_events": len(original_events),
            "base64_image_payloads": len(images),
            "encrypted_content_values": len(encrypted),
            "rate_limits_objects": len(rate_limits),
        },
        "sanitized": {
            "file": destination.name,
            "bytes": len(sanitized),
            "sha256": sha256_bytes(sanitized),
            "jsonl_events": len(sanitized_events),
            "redacted_values": len(redactions),
        },
        "preservation": {
            "bytes_outside_redacted_values_identical": True,
            "outside_redacted_value_segments_sha256": outside_digest,
            "event_order_preserved": True,
            "timeline_and_operation_evidence_preserved": True,
            "audit_projection_sha256": original_projection,
            "image_order_preserved": True,
        },
        "images": {
            "count": len(images),
            "decoded_bytes_total": sum(
                int(image["decoded_bytes"]) for image in images
            ),
            "ordinal_bytes_sha256_aggregate": aggregate(images, "decoded_bytes"),
            "entries": images,
        },
        "encrypted_content": {
            "count": len(encrypted),
            "decoded_bytes_total": sum(
                int(entry["decoded_bytes"]) for entry in encrypted
            ),
            "ordinal_bytes_sha256_aggregate": aggregate(
                encrypted, "decoded_bytes"
            ),
            "entries": encrypted,
        },
        "account_rate_limits": {
            "count": len(rate_limits),
            "serialized_bytes_total": sum(
                int(entry["serialized_bytes"]) for entry in rate_limits
            ),
            "ordinal_bytes_sha256_aggregate": aggregate(
                rate_limits, "serialized_bytes"
            ),
            "entries": rate_limits,
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    manifest = sanitize(args.source, args.destination, args.manifest)
    print(json.dumps(manifest["original"], sort_keys=True))
    print(json.dumps(manifest["sanitized"], sort_keys=True))


if __name__ == "__main__":
    main()
