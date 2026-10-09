#!/usr/bin/env python3
"""Collect reproducibility metadata from one completed manual Harbor job."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


SECRET_PATTERNS = (
    re.compile(rb"(?:^|[^A-Za-z0-9])sk-ant-[A-Za-z0-9_-]{16,}"),
    re.compile(rb"(?:^|[^A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
    re.compile(rb"(?:^|[^A-Za-z0-9])ya29\.[A-Za-z0-9_-]{20,}"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_one(root: Path, relative: str, *, required: bool = True) -> Path | None:
    matches = sorted(root.glob(f"*/{relative}"))
    if len(matches) == 1:
        return matches[0]
    if not matches and not required:
        return None
    raise SystemExit(f"expected one {relative} under {root}, found {len(matches)}")


def atif_counts(path: Path | None) -> tuple[int | None, int | None]:
    if path is None:
        return None, None
    data = json.loads(path.read_text(encoding="utf-8"))
    steps = data.get("steps")
    if not isinstance(steps, list):
        return None, None
    turns = 0
    calls = 0
    for step in steps:
        if not isinstance(step, dict) or step.get("source") != "agent":
            continue
        tool_calls = step.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            turns += 1
            calls += len(tool_calls)
    return turns, calls


def scan_secrets(root: Path) -> list[str]:
    hits: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".json", ".jsonl", ".log", ".txt"}:
            continue
        overlap = b""
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                payload = overlap + chunk
                if any(pattern.search(payload) for pattern in SECRET_PATTERNS):
                    hits.append(str(path))
                    break
                overlap = payload[-4096:]
    return hits


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-dir", required=True, type=Path)
    args = parser.parse_args()

    root = args.job_dir.resolve()
    trial_result_path = find_one(root, "result.json")
    reward_path = find_one(root, "steps/solve/verifier/reward.json")
    details_path = find_one(root, "steps/solve/verifier/verifier-details.json")
    solution_path = find_one(
        root, "steps/solve/artifacts/logs/artifacts/solution.json", required=False
    )
    trajectory_path = find_one(
        root, "steps/solve/agent/trajectory.json", required=False
    )

    result = json.loads(trial_result_path.read_text(encoding="utf-8"))
    reward = json.loads(reward_path.read_text(encoding="utf-8"))
    details = json.loads(details_path.read_text(encoding="utf-8"))
    predicted = int(details["n_predicted"])
    expected = int(details["n_ground_truth"])
    exact = int(details["exact_matches"])
    exact_precision = exact / predicted if predicted else 0.0
    exact_recall = exact / expected if expected else 0.0
    exact_iou = (
        exact / (predicted + expected - exact)
        if predicted + expected - exact
        else 0.0
    )
    tool_turns, tool_calls = atif_counts(trajectory_path)

    files = [reward_path, details_path]
    files.extend(path for path in (solution_path, trajectory_path) if path is not None)
    summary = {
        "trial": result.get("trial_name"),
        "task_checksum": result.get("task_checksum"),
        "agent_info": result.get("agent_info"),
        "started_at": result.get("started_at"),
        "finished_at": result.get("finished_at"),
        "reward": reward.get("reward"),
        "precision": reward.get("precision"),
        "recall": reward.get("recall"),
        "exact_iou": reward.get("exact_iou"),
        "exact_precision": round(exact_precision, 4),
        "exact_recall": round(exact_recall, 4),
        "exact_iou_from_counts": round(exact_iou, 4),
        "predicted": predicted,
        "schema_valid": details.get("n_schema_valid"),
        "ground_truth": expected,
        "full_chain_matches": exact,
        "tool_call_turns": tool_turns,
        "tool_calls": tool_calls,
        "tool_count_record_type": "ATIF agent-authored steps with tool_calls",
        "files": {
            str(path.relative_to(root)): {"sha256": sha256(path), "bytes": path.stat().st_size}
            for path in files
        },
    }
    secret_hits = scan_secrets(root)
    if secret_hits:
        raise SystemExit("possible credential material found in: " + ", ".join(secret_hits))
    summary["credential_scan"] = "no known API/OAuth token patterns found"
    output = root / "manual-run-summary.json"
    output.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"summary: {output}")


if __name__ == "__main__":
    main()
