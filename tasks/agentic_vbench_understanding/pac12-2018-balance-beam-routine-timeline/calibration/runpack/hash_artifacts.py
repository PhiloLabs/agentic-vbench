#!/usr/bin/env python3
"""Write a SHA-256 manifest for untouched calibration artifacts."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("artifacts", nargs="+", type=Path)
    args = parser.parse_args()

    if args.output.exists():
        raise SystemExit(f"refusing to overwrite manifest: {args.output}")

    records = []
    for artifact in args.artifacts:
        if not artifact.is_file():
            raise SystemExit(f"artifact not found: {artifact}")
        records.append(
            {
                "path": artifact.name,
                "bytes": artifact.stat().st_size,
                "sha256": sha256_file(artifact),
            }
        )

    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifacts": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")


if __name__ == "__main__":
    main()
