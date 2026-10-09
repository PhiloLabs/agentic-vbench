#!/usr/bin/env python3
"""Condense a `claude -p --output-format stream-json` trajectory for committing.

The native Claude rollout is 15,343,222 bytes raw, which would make it the
largest tracked blob in this repository by an order of magnitude. The unmodified
file is published as a hash-pinned release asset instead, and this script
regenerates the committed copy from it byte for byte:

    python3 condense_trajectory.py FULL.jsonl claude-opus-4.8-native.jsonl

Two reductions, both chosen because they lose nothing a reader of the trajectory
needs:

1. `stream_event` records are dropped. With `--include-partial-messages` the
   harness emits the raw SSE deltas *and* the assembled `assistant` record for
   the same message. On this rollout the deltas open 328 content blocks and the
   assembled records carry 328 blocks (102 thinking, 79 text, 147 tool_use)
   under the same 147 message ids, so the deltas are a re-serialisation of text
   that survives in full. The one field that exists only on the delta stream is
   `message_start.ttft_ms`, which this script copies onto the assembled
   `assistant` record rather than discarding.

2. Base64 image payloads are replaced with a content-addressed placeholder. The
   repository does not commit generated images, and a screenshot's bytes are not
   readable evidence in a JSONL file anyway. The placeholder keeps the length
   and sha256 of the payload it replaces, so the claim "an image of exactly
   these bytes was returned here" stays checkable against the release asset.

Everything else -- every tool call, every tool input, every tool result, every
thinking block, the system init record, and the final result record -- is passed
through unchanged.
"""
from __future__ import annotations

import hashlib
import json
import sys
from typing import Any

PLACEHOLDER = (
    "<image omitted from the committed trajectory: {media}, {size} base64 bytes, "
    "sha256 {digest}. The unmodified trajectory is a hash-pinned release asset; "
    "see calibration/rollouts/README.md.>"
)


def placeholder(source: dict[str, Any]) -> str:
    raw = (source.get("data") or "").encode("ascii", "ignore")
    return PLACEHOLDER.format(
        media=source.get("media_type", "image"),
        size=len(raw),
        digest=hashlib.sha256(raw).hexdigest(),
    )


def strip_images(node: Any) -> tuple[Any, int]:
    """Return ``(rewritten node, images replaced)``."""
    if isinstance(node, dict):
        if node.get("type") == "image" and isinstance(node.get("source"), dict):
            return {"type": "text", "text": placeholder(node["source"])}, 1
        if isinstance(node.get("base64"), str) and "type" in node:
            # The sibling `tool_use_result.file` shape carries the same bytes as
            # the message-level image block; keep its other fields.
            kept = {key: value for key, value in node.items() if key != "base64"}
            kept["base64_omitted"] = placeholder(
                {"data": node["base64"], "media_type": node.get("type", "image")}
            )
            return kept, 1
        replaced = 0
        out: dict[str, Any] = {}
        for key, value in node.items():
            out[key], count = strip_images(value)
            replaced += count
        return out, replaced
    if isinstance(node, list):
        replaced = 0
        out_list = []
        for value in node:
            new, count = strip_images(value)
            out_list.append(new)
            replaced += count
        return out_list, replaced
    return node, 0


def condense(source_path: str, target_path: str) -> None:
    ttft: dict[str, Any] = {}
    kept = dropped = images = 0
    digest_in = hashlib.sha256()
    with open(source_path, "rb") as raw:
        for chunk in iter(lambda: raw.read(1 << 20), b""):
            digest_in.update(chunk)

    with open(source_path, encoding="utf-8") as handle, open(
        target_path, "w", encoding="utf-8"
    ) as out:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("type") == "stream_event":
                event = record.get("event", {})
                if event.get("type") == "message_start" and "ttft_ms" in record:
                    ttft[event["message"]["id"]] = record["ttft_ms"]
                dropped += 1
                continue
            if record.get("type") == "assistant":
                message_id = record.get("message", {}).get("id")
                if message_id in ttft:
                    record["ttft_ms"] = ttft.pop(message_id)
            record, count = strip_images(record)
            images += count
            kept += 1
            out.write(
                json.dumps(record, ensure_ascii=False, separators=(", ", ": ")) + "\n"
            )

    digest_out = hashlib.sha256()
    with open(target_path, "rb") as raw:
        for chunk in iter(lambda: raw.read(1 << 20), b""):
            digest_out.update(chunk)

    print(f"{kept} records kept, {dropped} stream_event records dropped")
    print(f"{images} base64 image payloads replaced with placeholders")
    if ttft:
        print(f"warning: {len(ttft)} ttft_ms values had no assembled message")
    print(f"in   sha256 {digest_in.hexdigest()}  {source_path}")
    print(f"out  sha256 {digest_out.hexdigest()}  {target_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    condense(sys.argv[1], sys.argv[2])
