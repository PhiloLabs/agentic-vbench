#!/usr/bin/env python3
"""Build a privacy-safe Antigravity JSONL trajectory from native SQLite state."""

import argparse
import collections
import hashlib
import json
import re
import sqlite3
import tarfile
from datetime import datetime, timezone
from pathlib import Path


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
HOME_RE = re.compile(r"(?<![A-Za-z0-9._-])/Users/[^/\s`\"'<>]+")
HOME_USER_BYTES_RE = re.compile(rb"/Users/([^/\s`\"'<>]+)")
TRANSCRIPT_SUFFIX = "/.system_generated/logs/transcript_full.jsonl"
STEP_TYPE_NAMES = {
    14: "user_message",
    15: "assistant_message",
    23: "context_checkpoint",
    101: "system_message",
    132: "tool_result",
}


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_snapshot(database, brain_archive):
    paths = [database, Path(f"{database}-wal"), Path(f"{database}-shm"), brain_archive]
    return {
        path.name: {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in paths
        if path.is_file()
    }


def read_varint(data, offset):
    value = 0
    shift = 0
    while offset < len(data) and shift < 70:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7
    raise ValueError("invalid protobuf varint")


def decode_fields(data):
    decoded = []
    offset = 0
    while offset < len(data):
        key, offset = read_varint(data, offset)
        number = key >> 3
        wire = key & 7
        if number == 0:
            raise ValueError("invalid zero protobuf field")
        if wire == 0:
            value, offset = read_varint(data, offset)
        elif wire == 1:
            if offset + 8 > len(data):
                raise ValueError("truncated protobuf fixed64")
            value = data[offset : offset + 8]
            offset += 8
        elif wire == 2:
            length, offset = read_varint(data, offset)
            if offset + length > len(data):
                raise ValueError("truncated protobuf bytes")
            value = data[offset : offset + length]
            offset += length
        elif wire == 5:
            if offset + 4 > len(data):
                raise ValueError("truncated protobuf fixed32")
            value = data[offset : offset + 4]
            offset += 4
        else:
            raise ValueError(f"unsupported protobuf wire type: {wire}")
        decoded.append((number, wire, value))
    return decoded


def values(message, number, wire=None):
    return [
        value
        for field_number, field_wire, value in message
        if field_number == number and (wire is None or field_wire == wire)
    ]


def exactly_one(message, number, wire, label):
    found = values(message, number, wire)
    if len(found) != 1:
        raise ValueError(f"expected one {label}; found {len(found)}")
    return found[0]


def optional_one(message, number, wire, label):
    found = values(message, number, wire)
    if len(found) > 1:
        raise ValueError(f"expected at most one {label}; found {len(found)}")
    return found[0] if found else None


def text_value(value):
    return value.decode("utf-8")


def message_value(value):
    return decode_fields(value)


def canonical_bytes(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def timestamp_value(common, field_number):
    encoded = optional_one(common, field_number, 2, f"timestamp field {field_number}")
    if encoded is None:
        return None
    timestamp = message_value(encoded)
    seconds = exactly_one(timestamp, 1, 0, "timestamp seconds")
    nanos = optional_one(timestamp, 2, 0, "timestamp nanos") or 0
    base = datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    return f"{base}.{nanos:09d}Z"


class Redactor:
    def __init__(self, local_usernames):
        self.counts = collections.Counter()
        self.local_username_re = (
            re.compile(
                r"\b(?:" + "|".join(re.escape(name) for name in local_usernames) + r")\b",
                re.I,
            )
            if local_usernames
            else None
        )

    def text(self, value):
        value, count = EMAIL_RE.subn("<redacted-email>", value)
        self.counts["email_identifiers"] += count
        value, count = HOME_RE.subn("/Users/<redacted-user>", value)
        self.counts["local_home_identifiers"] += count
        if self.local_username_re is not None:
            value, count = self.local_username_re.subn("<redacted-user>", value)
            self.counts["local_username_identifiers"] += count
        return value

    def value(self, value):
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, list):
            return [self.value(item) for item in value]
        if isinstance(value, dict):
            return {key: self.value(item) for key, item in value.items()}
        return value


def decode_signature(tool_call):
    wrapper_blob = optional_one(tool_call, 7, 2, "tool-call signature wrapper")
    if wrapper_blob is None:
        return None
    wrapper = message_value(wrapper_blob)
    signature_blob = exactly_one(wrapper, 2, 2, "tool-call signature container")
    signature_container = message_value(signature_blob)
    return exactly_one(signature_container, 1, 2, "tool-call signature")


def decode_tool_call(encoded):
    tool_call = message_value(encoded)
    call_id = text_value(exactly_one(tool_call, 1, 2, "tool-call id"))
    name = text_value(exactly_one(tool_call, 2, 2, "tool-call name"))
    arguments_text = text_value(exactly_one(tool_call, 3, 2, "tool-call arguments"))
    arguments = json.loads(arguments_text)
    signature = decode_signature(tool_call)
    return {
        "id": call_id,
        "name": name,
        "arguments": arguments,
        "arguments_text": arguments_text,
        "signature": signature,
    }


def signature_placeholder(signature):
    if signature is None:
        return None
    return {
        "kind": "omitted_provider_signature",
        "bytes": len(signature),
        "sha256": sha256_bytes(signature),
    }


def parse_media_descriptor(encoded):
    descriptor = message_value(encoded)
    mime_blob = optional_one(descriptor, 1, 2, "media MIME type")
    path_blob = optional_one(descriptor, 5, 2, "media storage path")
    if mime_blob is None or path_blob is None:
        return None
    return {
        "mime_type": text_value(mime_blob),
        "storage_path": text_value(path_blob),
    }


def media_member_name(storage_path):
    marker = "/brain/"
    if marker not in storage_path:
        raise ValueError(f"cannot map media storage path into brain archive: {storage_path}")
    return storage_path.split(marker, 1)[1]


def db_reported_media_bytes(result, storage_path):
    any_blob = optional_one(result, 6, 2, "tool-result Any payload")
    if any_blob is None:
        return None
    any_message = message_value(any_blob)
    embedded_blob = exactly_one(any_message, 2, 2, "embedded native tool result")
    embedded = message_value(embedded_blob)
    candidates = []
    for _, wire, child_blob in embedded:
        if wire != 2:
            continue
        try:
            child = message_value(child_blob)
        except ValueError:
            continue
        for descriptor_blob in values(child, 15, 2):
            try:
                descriptor = parse_media_descriptor(descriptor_blob)
            except (UnicodeDecodeError, ValueError):
                continue
            if descriptor and descriptor["storage_path"] == storage_path:
                byte_count = optional_one(child, 12, 0, "DB-reported media byte count")
                if byte_count is not None:
                    candidates.append(byte_count)
    if len(candidates) > 1 and len(set(candidates)) != 1:
        raise ValueError(f"conflicting DB-reported media sizes for {storage_path}")
    return candidates[0] if candidates else None


def hash_tar_member(archive, member_name):
    member = archive.getmember(member_name)
    handle = archive.extractfile(member)
    if handle is None:
        raise ValueError(f"brain archive member is not a regular file: {member_name}")
    body = handle.read()
    return {
        "bytes": len(body),
        "sha256": sha256_bytes(body),
    }


def decode_common(outer):
    return message_value(exactly_one(outer, 5, 2, "step common metadata"))


def base_event(sequence, idx, step_type, status, common):
    event = {
        "schema_version": 1,
        "sequence": sequence,
        "db_step_index": idx,
        "db_step_type": step_type,
        "db_status": status,
        "event_type": STEP_TYPE_NAMES[step_type],
        "created_at_utc": timestamp_value(common, 1),
    }
    completed_at = timestamp_value(common, 8)
    if completed_at is not None:
        event["completed_at_utc"] = completed_at
    return event


def decode_event(sequence, row, redactor, archive, media_cache):
    idx, step_type, status, encoded = row
    outer = message_value(encoded)
    if exactly_one(outer, 1, 0, "outer step type") != step_type:
        raise ValueError(f"step type mismatch at DB index {idx}")
    if exactly_one(outer, 4, 0, "outer step status") != status:
        raise ValueError(f"step status mismatch at DB index {idx}")
    if step_type not in STEP_TYPE_NAMES:
        raise ValueError(f"unsupported step type {step_type} at DB index {idx}")

    common = decode_common(outer)
    event = base_event(sequence, idx, step_type, status, common)
    source_primary_text = None
    source_tool_calls = []

    if step_type == 14:
        payload = message_value(exactly_one(outer, 19, 2, "user payload"))
        source_primary_text = text_value(exactly_one(payload, 2, 2, "user text"))
        event.update({"role": "user", "content": redactor.text(source_primary_text)})
    elif step_type == 15:
        payload = message_value(exactly_one(outer, 20, 2, "assistant payload"))
        source_primary_text = text_value(exactly_one(payload, 1, 2, "assistant text"))
        duplicate = text_value(exactly_one(payload, 8, 2, "assistant duplicate text"))
        if duplicate != source_primary_text:
            raise ValueError(f"assistant text copies disagree at DB index {idx}")
        message_id = text_value(exactly_one(payload, 6, 2, "assistant message id"))
        for position, tool_blob in enumerate(values(payload, 7, 2)):
            call = decode_tool_call(tool_blob)
            source_tool_calls.append(call)
            public_call = {
                "position": position,
                "id": call["id"],
                "name": call["name"],
                "arguments": redactor.value(call["arguments"]),
            }
            placeholder = signature_placeholder(call["signature"])
            if placeholder is not None:
                public_call["provider_signature"] = placeholder
            event.setdefault("tool_calls", []).append(public_call)
        event.update(
            {
                "role": "assistant",
                "model_message_id": message_id,
                "content": redactor.text(source_primary_text),
            }
        )
    elif step_type == 23:
        payload = message_value(exactly_one(outer, 30, 2, "checkpoint payload"))
        source_primary_text = text_value(exactly_one(payload, 5, 2, "checkpoint summary"))
        event.update({"role": "system", "content": redactor.text(source_primary_text)})
    elif step_type == 101:
        payload = message_value(exactly_one(outer, 114, 2, "system-message payload"))
        source_primary_text = text_value(exactly_one(payload, 1, 2, "system-message text"))
        subtype_blob = optional_one(payload, 3, 2, "system-message subtype")
        event.update(
            {
                "role": "system",
                "content": redactor.text(source_primary_text),
            }
        )
        if subtype_blob is not None:
            event["system_subtype"] = text_value(subtype_blob)
    elif step_type == 132:
        call_blob = exactly_one(common, 4, 2, "tool-result request metadata")
        call = decode_tool_call(call_blob)
        source_tool_calls.append(call)
        tool_payload = message_value(exactly_one(outer, 140, 2, "tool-result payload"))
        result_blob = optional_one(tool_payload, 2, 2, "tool-result body")
        result_reference = None
        media = []
        finalized_database_text = None
        if result_blob is not None:
            result = message_value(result_blob)
            content_blob = optional_one(result, 1, 2, "tool-result text")
            source_primary_text = text_value(content_blob) if content_blob is not None else ""
            finalized_database_text = source_primary_text
            reference_blob = optional_one(result, 7, 2, "tool-result reference")
            if reference_blob is not None:
                result_reference = text_value(reference_blob)
            for descriptor_blob in values(result, 4, 2):
                descriptor = parse_media_descriptor(descriptor_blob)
                if descriptor is None:
                    raise ValueError(f"unrecognized media descriptor at DB index {idx}")
                storage_path = descriptor["storage_path"]
                member_name = media_member_name(storage_path)
                if member_name not in media_cache:
                    media_cache[member_name] = hash_tar_member(archive, member_name)
                body = media_cache[member_name]
                reported_bytes = db_reported_media_bytes(result, storage_path)
                if reported_bytes is not None and reported_bytes != body["bytes"]:
                    raise ValueError(f"media size mismatch at DB index {idx}: {member_name}")
                media.append(
                    {
                        "kind": "omitted_media_body",
                        "mime_type": descriptor["mime_type"],
                        "bytes": body["bytes"],
                        "sha256": body["sha256"],
                        "source_reference": redactor.text(storage_path),
                    }
                )
        else:
            error_payload = message_value(exactly_one(outer, 31, 2, "invalid tool error"))
            error_blob = exactly_one(error_payload, 2, 2, "invalid tool error text")
            source_primary_text = text_value(error_blob)

        result_status = "invalid_pre_execution" if status == 7 else "completed"
        background_blob = optional_one(outer, 148, 2, "background-task metadata")
        if background_blob is not None:
            background = message_value(background_blob)
            task_id = text_value(exactly_one(background, 1, 2, "background task id"))
            task_log = text_value(exactly_one(background, 2, 2, "background task log"))
            task_description = text_value(
                exactly_one(background, 4, 2, "background task description")
            )
            source_primary_text = (
                f"Tool is running as a background task with task id: {task_id}\n"
                f"Task Description: {task_description}\n"
                f"Task logs are available at: {task_log}"
            )
            result_reference = task_log
            result_status = "running"
        event.update(
            {
                "role": "tool",
                "tool_call_id": call["id"],
                "tool_name": call["name"],
                "arguments": redactor.value(call["arguments"]),
                "result_status": result_status,
                "content": redactor.text(source_primary_text),
            }
        )
        if result_reference is not None:
            event["result_reference"] = redactor.text(result_reference)
        if media:
            event["media"] = media
        if background_blob is not None and finalized_database_text:
            event["finalized_database_result"] = redactor.text(finalized_database_text)

    return event, source_primary_text, source_tool_calls


def transcript_validation(transcript_member, transcript_bytes, decoded_rows):
    native_rows = [json.loads(line) for line in transcript_bytes.splitlines()]
    native_by_index = {row["step_index"]: row for row in native_rows}
    invalid_indices = [
        item["db_step_index"]
        for item in decoded_rows
        if item["event"]["event_type"] == "tool_result"
        and item["event"]["result_status"] == "invalid_pre_execution"
    ]
    expected_indices = [
        item["db_step_index"]
        for item in decoded_rows
        if item["db_step_index"] not in invalid_indices
    ]
    if [row["step_index"] for row in native_rows] != expected_indices:
        raise ValueError("native transcript DB-index order does not match the database")

    expected_native_types = {
        "user_message": "USER_INPUT",
        "assistant_message": "PLANNER_RESPONSE",
        "tool_result": "GENERIC",
        "system_message": "SYSTEM_MESSAGE",
        "context_checkpoint": "CHECKPOINT",
    }
    exact_content_matches = 0
    contained_content_matches = 0
    assistant_tool_stream = []
    native_tool_stream = []
    rendered_status_matches = 0
    for item in decoded_rows:
        index = item["db_step_index"]
        if index in invalid_indices:
            continue
        event = item["event"]
        native = native_by_index[index]
        if native["type"] != expected_native_types[event["event_type"]]:
            raise ValueError(f"native transcript type mismatch at DB index {index}")
        primary = item["source_primary_text"]
        if event["event_type"] == "assistant_message":
            if native["content"] != primary:
                raise ValueError(f"assistant content mismatch at DB index {index}")
            exact_content_matches += 1
            source_calls = item["source_tool_calls"]
            native_calls = native.get("tool_calls", [])
            if len(source_calls) != len(native_calls):
                raise ValueError(f"native tool-call count mismatch at DB index {index}")
            for source_call, native_call in zip(source_calls, native_calls):
                source_value = {
                    "name": source_call["name"],
                    "args": source_call["arguments"],
                }
                if source_value != native_call:
                    raise ValueError(f"native tool-call mismatch at DB index {index}")
                assistant_tool_stream.append(source_value)
                native_tool_stream.append(native_call)
        else:
            if primary not in native["content"]:
                raise ValueError(f"primary text missing from native transcript at DB index {index}")
            contained_content_matches += 1
        if event["event_type"] == "tool_result":
            expected_status = "RUNNING" if event["result_status"] == "running" else "DONE"
            if native["status"] != expected_status:
                raise ValueError(f"native result status mismatch at DB index {index}")
            rendered_status_matches += 1

    if assistant_tool_stream != native_tool_stream:
        raise ValueError("native ordered tool stream differs from database tool stream")
    return {
        "member": transcript_member,
        "bytes": len(transcript_bytes),
        "sha256": sha256_bytes(transcript_bytes),
        "lines": len(native_rows),
        "db_step_indices_match_in_order": True,
        "excluded_invalid_pre_execution_db_indices": invalid_indices,
        "event_types_match": len(native_rows),
        "assistant_content_exact_matches": exact_content_matches,
        "other_primary_content_contained_matches": contained_content_matches,
        "tool_result_status_matches": rendered_status_matches,
        "ordered_tool_name_and_arguments_matches": len(assistant_tool_stream),
    }


def stream_digest(items):
    return sha256_bytes(canonical_bytes(items))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--brain-archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--audit-output", required=True, type=Path)
    args = parser.parse_args()

    database = args.database.resolve()
    brain_archive = args.brain_archive.resolve()
    if not database.is_file() or not brain_archive.is_file():
        raise SystemExit("database and brain archive must exist")
    source_before = source_snapshot(database, brain_archive)

    uri = f"{database.as_uri()}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.execute("PRAGMA query_only = ON")
        rows = connection.execute(
            "SELECT idx, step_type, status, step_payload FROM steps ORDER BY idx"
        ).fetchall()
    if [row[0] for row in rows] != list(range(len(rows))):
        raise ValueError("database step indices are not contiguous from zero")

    local_usernames = sorted(
        {
            match.group(1).decode("utf-8")
            for row in rows
            for match in HOME_USER_BYTES_RE.finditer(row[3])
        }
    )
    redactor = Redactor(local_usernames)
    decoded_rows = []
    media_cache = {}
    with tarfile.open(brain_archive, "r") as archive:
        transcript_members = [
            member.name
            for member in archive.getmembers()
            if member.isfile() and member.name.endswith(TRANSCRIPT_SUFFIX)
        ]
        if len(transcript_members) != 1:
            raise ValueError(
                f"expected one native validation transcript; found {len(transcript_members)}"
            )
        transcript_member = transcript_members[0]
        transcript_handle = archive.extractfile(transcript_member)
        if transcript_handle is None:
            raise ValueError("native validation transcript is missing from brain archive")
        transcript_bytes = transcript_handle.read()
        for sequence, row in enumerate(rows):
            event, source_primary_text, source_tool_calls = decode_event(
                sequence,
                row,
                redactor,
                archive,
                media_cache,
            )
            decoded_rows.append(
                {
                    "db_step_index": row[0],
                    "event": event,
                    "source_primary_text": source_primary_text,
                    "source_tool_calls": source_tool_calls,
                }
            )

    source_event_counts = collections.Counter(
        (row[1], row[2]) for row in rows
    )
    events = [item["event"] for item in decoded_rows]
    event_counts = collections.Counter(event["event_type"] for event in events)
    request_occurrences = [
        {
            "request_step_index": item["db_step_index"],
            "request_position": position,
            "call": call,
        }
        for item in decoded_rows
        if item["event"]["event_type"] == "assistant_message"
        for position, call in enumerate(item["source_tool_calls"])
    ]
    request_calls = [occurrence["call"] for occurrence in request_occurrences]
    result_occurrences = [
        {
            "result_step_index": item["db_step_index"],
            "call": item["source_tool_calls"][0],
            "event": item["event"],
        }
        for item in decoded_rows
        if item["event"]["event_type"] == "tool_result"
    ]
    result_calls = [occurrence["call"] for occurrence in result_occurrences]
    if len(request_calls) != len(result_calls):
        raise ValueError("tool request/result counts differ")
    request_stream = [
        {"id": call["id"], "name": call["name"], "arguments": call["arguments"]}
        for call in request_calls
    ]
    result_stream = [
        {"id": call["id"], "name": call["name"], "arguments": call["arguments"]}
        for call in result_calls
    ]
    if request_stream != result_stream:
        raise ValueError("ordered tool request/result metadata streams differ")
    for request, result in zip(request_occurrences, result_occurrences):
        result["event"]["request_step_index"] = request["request_step_index"]
        result["event"]["request_position"] = request["request_position"]
    if any(
        request["signature"] != result["signature"]
        for request, result in zip(request_calls, result_calls)
    ):
        raise ValueError("tool request/result provider signatures differ")

    validation = transcript_validation(transcript_member, transcript_bytes, decoded_rows)
    output_bytes = b"".join(canonical_bytes(event) + b"\n" for event in events)
    output_text = output_bytes.decode("utf-8")
    if (
        EMAIL_RE.search(output_text)
        or HOME_RE.search(output_text)
        or (
            redactor.local_username_re is not None
            and redactor.local_username_re.search(output_text)
        )
    ):
        raise ValueError("privacy identifier remains in public trajectory")
    if "data:image/" in output_text or "base64," in output_text:
        raise ValueError("embedded media body remains in public trajectory")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(output_bytes)

    signature_placeholders = sum(
        1 for call in request_calls if call["signature"] is not None
    )
    media_placeholders = sum(len(event.get("media", [])) for event in events)
    model_message_ids = [
        event["model_message_id"]
        for event in events
        if event["event_type"] == "assistant_message"
    ]
    public_tool_stream = [
        {
            "id": event["tool_call_id"],
            "name": event["tool_name"],
            "arguments": event["arguments"],
        }
        for event in events
        if event["event_type"] == "tool_result"
    ]
    public_request_stream = [
        {
            "id": call["id"],
            "name": call["name"],
            "arguments": call["arguments"],
        }
        for event in events
        if event["event_type"] == "assistant_message"
        for call in event.get("tool_calls", [])
    ]
    if public_request_stream != public_tool_stream:
        raise ValueError("published tool request/result metadata streams differ")
    call_id_counts = collections.Counter(call["id"] for call in request_calls)
    repeated_call_ids = {
        call_id: [
            {
                "request_step_index": request["request_step_index"],
                "result_step_index": result["result_step_index"],
            }
            for request, result in zip(request_occurrences, result_occurrences)
            if request["call"]["id"] == call_id
        ]
        for call_id, count in sorted(call_id_counts.items())
        if count > 1
    }
    source_after = source_snapshot(database, brain_archive)
    if source_before != source_after:
        raise ValueError("native source files changed during extraction")

    audit = {
        "schema_version": 2,
        "kind": "database_derived_public_agent_tool_trajectory",
        "source": {
            "database": {
                "path": database.name,
                **source_before[database.name],
                "sqlite_access": "URI mode=ro&immutable=1 with PRAGMA query_only=ON",
                "table": "steps",
            },
            "extractor": {
                "path": "calibration/runpack/" + Path(__file__).name,
                "bytes": Path(__file__).stat().st_size,
                "sha256": sha256_file(Path(__file__)),
            },
            "brain_archive": {
                "path": brain_archive.name,
                **source_before[brain_archive.name],
                "uses": [
                    "hash media bodies referenced by the database without publishing them",
                    "validate database-derived semantics against the native rendered transcript",
                ],
            },
            "files_unchanged_during_extraction": source_before == source_after,
            "pre_extraction": source_before,
            "post_extraction": source_after,
        },
        "destination": {
            "path": args.output.name,
            "bytes": len(output_bytes),
            "sha256": sha256_bytes(output_bytes),
            "lines": len(events),
        },
        "extraction": {
            "db_rows": len(rows),
            "db_index_range": [rows[0][0], rows[-1][0]],
            "db_indices_contiguous_and_preserved": True,
            "source_step_type_status_counts": {
                f"type_{step_type}_status_{status}": count
                for (step_type, status), count in sorted(source_event_counts.items())
            },
            "published_event_counts": dict(sorted(event_counts.items())),
            "protobuf_field_map": {
                "14.field19.field2": "user message",
                "15.field20.field1": "assistant message",
                "15.field20.field6": "model message id",
                "15.field20.field7": "ordered tool request",
                "23.field30.field5": "checkpoint summary",
                "101.field114.field1": "system message",
                "132.field5.field4": "tool id, name, arguments, and provider signature",
                "132.field140.field2.field1": "tool textual result",
                "132.field140.field2.field4": "media reference",
                "132.field148": "background-task launch metadata",
                "132.field31.field2": "invalid pre-execution error",
            },
        },
        "preservation": {
            "database_rows_emitted_one_to_one": len(events),
            "ordered_db_step_index_stream_sha256": stream_digest(
                [event["db_step_index"] for event in events]
            ),
            "model_message_ids": len(model_message_ids),
            "unique_model_message_ids": len(set(model_message_ids)),
            "ordered_model_message_id_stream_sha256": stream_digest(model_message_ids),
            "tool_requests": len(request_calls),
            "tool_results_including_running_and_invalid": len(result_calls),
            "unique_tool_call_ids": len({call["id"] for call in request_calls}),
            "repeated_tool_call_ids_are_source_data": repeated_call_ids,
            "repeated_ids_disambiguated_by_request_and_result_step_indices": True,
            "request_result_id_name_arguments_order_exact": True,
            "request_result_provider_signatures_exact": True,
            "published_request_result_id_name_arguments_order_exact": True,
            "background_task_launches_reconstructed_from_field148": sum(
                event.get("result_status") == "running" for event in events
            ),
            "background_final_database_results_retained_separately": True,
            "source_tool_stream_sha256": stream_digest(request_stream),
            "published_redacted_tool_stream_sha256": stream_digest(public_tool_stream),
            "native_rendered_transcript_validation": validation,
        },
        "privacy": {
            "replacements": dict(sorted(redactor.counts.items())),
            "checks": {
                "email_identifiers_absent": EMAIL_RE.search(output_text) is None,
                "local_home_identifiers_absent": HOME_RE.search(output_text) is None,
                "local_username_identifiers_absent": (
                    redactor.local_username_re is None
                    or redactor.local_username_re.search(output_text) is None
                ),
                "embedded_data_uri_or_base64_marker_absent": (
                    "data:image/" not in output_text and "base64," not in output_text
                ),
            },
        },
        "binary_handling": {
            "provider_signature_bodies_replaced": signature_placeholders,
            "provider_signature_placeholders_include_sha256_and_bytes": True,
            "media_bodies_replaced": media_placeholders,
            "unique_media_bodies": len(media_cache),
            "media_placeholders_include_sha256_and_bytes": True,
            "media_body_source": "untouched antigravity-native-brain.tar members referenced by database media metadata",
            "database_contains_media_references_not_inline_media_bodies": True,
        },
        "source_untouched": True,
    }
    args.audit_output.parent.mkdir(parents=True, exist_ok=True)
    args.audit_output.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
