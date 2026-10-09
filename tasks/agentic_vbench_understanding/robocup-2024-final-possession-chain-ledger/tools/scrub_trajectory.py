#!/usr/bin/env python3
"""Deterministically redact local paths and opaque payloads from JSONL trajectories."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


OPAQUE_KEYS = {
    "encrypted_content",
    "encryptedContent",
    "image",
    "image_url",
    "imageUrl",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--replace-path",
        action="append",
        default=[],
        metavar="FROM=TO",
        help="literal path replacement; may be supplied more than once",
    )
    return parser.parse_args()


def placeholder(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"[redacted sha256={digest} chars={len(value)}]"


def scrub(value: Any, replacements: list[tuple[str, str]], key: str = "") -> Any:
    if isinstance(value, dict):
        return {
            item_key: scrub(item_value, replacements, item_key)
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [scrub(item, replacements, key) for item in value]
    if isinstance(value, str):
        if key in OPAQUE_KEYS and (
            key.startswith("encrypted")
            or value.startswith("data:image/")
            or len(value) >= 4096
        ):
            return placeholder(value)
        for source, target in replacements:
            value = value.replace(source, target)
    return value


def main() -> None:
    args = parse_args()
    replacements = []
    for replacement in args.replace_path:
        if "=" not in replacement:
            raise ValueError(f"expected FROM=TO: {replacement}")
        source, target = replacement.split("=", 1)
        replacements.append((source, target))

    with args.input.open("r", encoding="utf-8") as source, args.output.open(
        "w", encoding="utf-8"
    ) as destination:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"invalid JSONL at line {line_number}") from error
            destination.write(
                json.dumps(
                    scrub(record, replacements),
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            )

    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(f"{digest}  {args.output}")


if __name__ == "__main__":
    main()
