#!/usr/bin/env python3
"""Create a deterministic privacy-safe JSONL publication derivative."""

import argparse
import base64
import collections
import hashlib
import json
import re
from pathlib import Path


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
HOME_RE = re.compile(r"(?<![A-Za-z0-9._-])/Users/[^/\s`\"'<>]+")
HOME_USER_RE = re.compile(r"/Users/([^/\s`\"'<>]+)")
LS_OWNER_RE = re.compile(
    r"[bcdlps-][rwxStTs-]{9}[+@.]?\s+\d+\s+"
    r"([A-Za-z_][A-Za-z0-9_.-]{0,31})\s+(?:admin|staff|wheel)\s+\d+\b"
)
IMAGE_PLACEHOLDER_RE = re.compile(
    r"^<omitted-image-payload-under-rights-exception "
    r"sha256=[0-9a-f]{64} bytes=[0-9]+>$"
)
MEDIA_SIGNATURES = ("/9j/", "iVBOR", "R0lGOD", "UklGR", "data:image/")
CREDENTIAL_PATTERNS = {
    "api_key": re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{16,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "bearer_token": re.compile(r"\bBearer\s+[A-Za-z0-9._~-]{20,}\b", re.I),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
IDENTIFIER_KEYS = {
    "call_id",
    "id",
    "parent_tool_use_id",
    "session_id",
    "thread_id",
    "tool_call_id",
    "tool_use_id",
    "uuid",
}


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def record_bytes(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def image_kind(value):
    if value.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if value.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if value.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if value.startswith(b"RIFF") and value[8:12] == b"WEBP":
        return "webp"
    return None


def placeholder_for_base64(value, stats, field_name):
    decoded = base64.b64decode(value, validate=True)
    kind = image_kind(decoded)
    if kind is None:
        raise ValueError(f"non-image payload found in {field_name}")
    digest = sha256_bytes(decoded)
    stats["image_occurrences"] += 1
    stats["image_base64_characters"] += len(value)
    stats["image_decoded_bytes"] += len(decoded)
    stats[f"image_field:{field_name}"] += 1
    stats[f"image_kind:{kind}"] += 1
    stats.setdefault("image_hashes", set()).add(digest)
    return (
        "<omitted-image-payload-under-rights-exception "
        f"sha256={digest} bytes={len(decoded)}>"
    )


class Redactor:
    def __init__(self, source_text):
        usernames = set(HOME_USER_RE.findall(source_text))
        usernames.update(LS_OWNER_RE.findall(source_text))
        self.local_usernames = sorted(usernames)
        self.local_username_re = (
            re.compile(
                r"\b(?:" + "|".join(re.escape(name) for name in usernames) + r")\b",
                re.I,
            )
            if usernames
            else None
        )
        self.stats = collections.Counter()
        self.stats["image_hashes"] = set()

    def text(self, value):
        value, count = EMAIL_RE.subn("<redacted-email>", value)
        self.stats["email_identifiers"] += count
        value, count = HOME_RE.subn("/Users/<redacted-user>", value)
        self.stats["local_home_identifiers"] += count
        if self.local_username_re is not None:
            value, count = self.local_username_re.subn("<redacted-user>", value)
            self.stats["local_username_identifiers"] += count
        return value

    def preview_text(self, value):
        value = EMAIL_RE.sub("<redacted-email>", value)
        value = HOME_RE.sub("/Users/<redacted-user>", value)
        if self.local_username_re is not None:
            value = self.local_username_re.sub("<redacted-user>", value)
        return value

    def value(self, value, redact_images):
        if isinstance(value, dict):
            result = dict(value)
            if redact_images:
                source = result.get("source")
                if (
                    result.get("type") == "image"
                    and isinstance(source, dict)
                    and source.get("type") == "base64"
                    and isinstance(source.get("data"), str)
                    and not IMAGE_PLACEHOLDER_RE.fullmatch(source["data"])
                ):
                    source = dict(source)
                    source["data"] = placeholder_for_base64(
                        source["data"], self.stats, "image_source_data"
                    )
                    result["source"] = source
                if (
                    isinstance(result.get("type"), str)
                    and result["type"].startswith("image/")
                    and isinstance(result.get("base64"), str)
                    and not IMAGE_PLACEHOLDER_RE.fullmatch(result["base64"])
                ):
                    result["base64"] = placeholder_for_base64(
                        result["base64"],
                        self.stats,
                        "tool_use_result_file_base64",
                    )
            return {
                key: self.value(item, redact_images)
                for key, item in result.items()
            }
        if isinstance(value, list):
            return [self.value(item, redact_images) for item in value]
        if isinstance(value, str):
            return self.text(value)
        return value


def walk(value, path=()):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from walk(item, path + (key,))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk(item, path + (index,))
    else:
        yield path, value


def path_sort_key(path):
    return tuple(
        (0, item) if isinstance(item, int) else (1, item)
        for item in path
    )


def identifier_stream(records):
    return [
        {"record": record_index, "path": path, "value": value}
        for record_index, record in enumerate(records)
        for path, value in sorted(walk(record), key=lambda item: path_sort_key(item[0]))
        if path and path[-1] in IDENTIFIER_KEYS and isinstance(value, (str, int))
    ]


def signature_stream(records):
    return [
        value
        for record in records
        for path, value in sorted(walk(record), key=lambda item: path_sort_key(item[0]))
        if path and path[-1] == "signature" and isinstance(value, str)
    ]


def compare_records(source_records, destination_records, redactor):
    if len(source_records) != len(destination_records):
        raise ValueError("record count changed")
    changed_records = 0
    changed_scalars = 0
    identity_scalars = 0
    image_scalars = 0
    for record_index, (source, destination) in enumerate(
        zip(source_records, destination_records)
    ):
        source_values = dict(walk(source))
        destination_values = dict(walk(destination))
        if source_values.keys() != destination_values.keys():
            raise ValueError(f"JSON structure changed at record {record_index}")
        record_changed = False
        for path, source_value in source_values.items():
            destination_value = destination_values[path]
            if source_value == destination_value:
                continue
            record_changed = True
            changed_scalars += 1
            if (
                isinstance(source_value, str)
                and isinstance(destination_value, str)
                and redactor.preview_text(source_value) == destination_value
            ):
                identity_scalars += 1
                continue
            if (
                isinstance(source_value, str)
                and isinstance(destination_value, str)
                and IMAGE_PLACEHOLDER_RE.fullmatch(destination_value)
                and path[-1] in {"data", "base64"}
            ):
                image_scalars += 1
                continue
            raise ValueError(
                f"unapproved scalar change at record {record_index}, path {path}"
            )
        changed_records += int(record_changed)
    return {
        "records_with_changes": changed_records,
        "changed_scalar_values": changed_scalars,
        "identity_scalar_values": identity_scalars,
        "image_scalar_values": image_scalars,
    }


def credential_scan(value):
    return {
        name: len(pattern.findall(value))
        for name, pattern in CREDENTIAL_PATTERNS.items()
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audit-output", required=True, type=Path)
    parser.add_argument("--redact-image-bodies", action="store_true")
    args = parser.parse_args()

    source = args.source.resolve()
    source_bytes = source.read_bytes()
    source_sha256 = sha256_bytes(source_bytes)
    source_text = source_bytes.decode("utf-8")
    source_lines = source_text.splitlines()
    source_records = [json.loads(line) for line in source_lines]

    redactor = Redactor(source_text)
    destination_records = [
        redactor.value(record, args.redact_image_bodies)
        for record in source_records
    ]
    destination_bytes = b"".join(
        record_bytes(record) + b"\n" for record in destination_records
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(destination_bytes)

    reparsed_records = [json.loads(line) for line in destination_bytes.splitlines()]
    if reparsed_records != destination_records:
        raise ValueError("written JSONL did not round-trip")
    comparison = compare_records(source_records, reparsed_records, redactor)
    source_identifiers = identifier_stream(source_records)
    destination_identifiers = identifier_stream(reparsed_records)
    if source_identifiers != destination_identifiers:
        raise ValueError("ordered identifier and tool-link stream changed")
    source_signatures = signature_stream(source_records)
    destination_signatures = signature_stream(reparsed_records)
    if source_signatures != destination_signatures:
        raise ValueError("signature stream changed")

    destination_text = destination_bytes.decode("utf-8")
    local_username_remaining = (
        redactor.local_username_re.search(destination_text)
        if redactor.local_username_re is not None
        else None
    )
    media_signatures = {
        signature: destination_text.count(signature)
        for signature in MEDIA_SIGNATURES
    }
    credentials = credential_scan(destination_text)
    if EMAIL_RE.search(destination_text) or HOME_RE.search(destination_text):
        raise ValueError("email or local-home identity remains")
    if local_username_remaining is not None:
        raise ValueError("local username identity remains")
    if args.redact_image_bodies and any(media_signatures.values()):
        raise ValueError("encoded media signature remains")
    if any(credentials.values()):
        raise ValueError("credential signature remains")
    if sha256_file(source) != source_sha256:
        raise ValueError("source changed during redaction")

    stats = redactor.stats
    image_hashes = stats.pop("image_hashes")
    audit = {
        "schema_version": 2,
        "kind": "privacy_safe_jsonl_publication_derivative",
        "source": {
            "path": source.name,
            "bytes": len(source_bytes),
            "sha256": source_sha256,
            "records": len(source_records),
        },
        "destination": {
            "path": args.output.name,
            "bytes": len(destination_bytes),
            "sha256": sha256_bytes(destination_bytes),
            "records": len(reparsed_records),
        },
        "replacements": {
            "email_identifiers": stats["email_identifiers"],
            "local_home_identifiers": stats["local_home_identifiers"],
            "local_username_identifiers": stats["local_username_identifiers"],
            "local_identity_tokens_discovered": len(redactor.local_usernames),
            "image_payloads": {
                "enabled": args.redact_image_bodies,
                "occurrences": stats["image_occurrences"],
                "base64_characters": stats["image_base64_characters"],
                "decoded_bytes": stats["image_decoded_bytes"],
                "unique_sha256": len(image_hashes),
                "by_field": {
                    "image_source_data": stats["image_field:image_source_data"],
                    "tool_use_result_file_base64": stats[
                        "image_field:tool_use_result_file_base64"
                    ],
                },
                "by_kind": {
                    kind: stats[f"image_kind:{kind}"]
                    for kind in ("jpeg", "png", "gif", "webp")
                },
            },
        },
        "preservation": {
            "record_order_preserved": True,
            "json_structure_preserved": True,
            **comparison,
            "ordered_record_type_stream_sha256": sha256_bytes(
                canonical_bytes([record.get("type") for record in source_records])
            ),
            "ordered_identifier_and_tool_link_values": len(source_identifiers),
            "ordered_identifier_and_tool_link_stream_sha256": sha256_bytes(
                canonical_bytes(source_identifiers)
            ),
            "signature_strings_preserved": len(source_signatures),
            "signature_stream_sha256": sha256_bytes(
                canonical_bytes(source_signatures)
            ),
        },
        "checks": {
            "source_untouched": True,
            "email_identifiers_absent": EMAIL_RE.search(destination_text) is None,
            "local_home_identifiers_absent": HOME_RE.search(destination_text) is None,
            "local_username_identifiers_absent": local_username_remaining is None,
            "encoded_media_signature_occurrences": media_signatures,
            "credential_signature_occurrences": credentials,
        },
    }
    args.audit_output.parent.mkdir(parents=True, exist_ok=True)
    args.audit_output.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
