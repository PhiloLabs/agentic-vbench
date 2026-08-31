#!/usr/bin/env python3
"""Stage a fresh, hash-pinned local workspace for one calibration run."""

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_SOURCE_SHA256 = (
    "7dfc9e139254cc9480948af734988bdebc796c89c6e5d439055a248c251130cb"
)
HARNESSES = ("antigravity", "codex", "claude")


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_exclusive(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(content)


def probe_source(path):
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height:format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def completed_artifact(task_root, section):
    artifact = section.get("artifact")
    expected_sha256 = section.get("sha256")
    if not section.get("complete") or not artifact or not expected_sha256:
        return False
    path = task_root / "annotations" / artifact
    return path.is_file() and sha256_file(path) == expected_sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--harness", required=True, choices=HARNESSES)
    parser.add_argument("--artifact-dir", required=True, type=Path)
    args = parser.parse_args()

    task_root = Path(__file__).resolve().parents[2]
    source = args.source.resolve()
    workspace = args.workspace.resolve()
    artifact_dir = args.artifact_dir.resolve()
    status_path = task_root / "annotations" / "status.json"
    instruction_path = task_root / "steps" / "solve" / "instruction.md"

    status = json.loads(status_path.read_text())
    independent = status.get("independent_review", {})
    adjudication = status.get("adjudication", {})
    takeoff_extension = status.get("dismount_takeoff_extension", {})
    gate_complete = (
        status.get("state") == "complete"
        and independent.get("blind_full_video_scan") is True
        and adjudication.get("all_differences_resolved_against_video") is True
        and adjudication.get("school_labels_complete") is True
        and adjudication.get("gymnast_names_complete") is True
        and adjudication.get("beam_scores_complete") is True
        and adjudication.get("score_times_complete") is True
        and adjudication.get("start_end_source_frame_snap_complete") is True
        and takeoff_extension.get("complete") is True
        and completed_artifact(task_root, independent)
        and completed_artifact(task_root, adjudication)
        and completed_artifact(task_root, takeoff_extension)
    )
    if not gate_complete:
        raise SystemExit(
            "annotation gate is not complete; do not start strong-agent calibration"
        )
    if workspace.exists():
        raise SystemExit(f"refusing existing workspace: {workspace}")
    if not source.is_file():
        raise SystemExit(f"source video not found: {source}")

    source_sha256 = sha256_file(source)
    if source_sha256 != EXPECTED_SOURCE_SHA256:
        raise SystemExit(
            f"source SHA-256 mismatch: expected {EXPECTED_SOURCE_SHA256}, "
            f"got {source_sha256}"
        )

    canonical_prompt = instruction_path.read_text()
    rendered_prompt = canonical_prompt.replace("/workspace", str(workspace))
    prompt_artifact = artifact_dir / f"{args.harness}-initial-prompt.md"
    manifest_artifact = artifact_dir / f"{args.harness}-input-manifest.json"
    if prompt_artifact.exists() or manifest_artifact.exists():
        raise SystemExit(
            f"refusing to overwrite existing {args.harness} input artifacts"
        )

    (workspace / "materials").mkdir(parents=True)
    (workspace / "output").mkdir()
    (workspace / "work").mkdir()
    shutil.copy2(source, workspace / "materials" / "source.mp4")
    if sha256_file(workspace / "materials" / "source.mp4") != source_sha256:
        raise SystemExit("staged source copy failed SHA-256 verification")
    (workspace / "prompt.md").write_text(rendered_prompt)

    manifest = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "harness": args.harness,
        "workspace": str(workspace),
        "source": {
            "sha256": source_sha256,
            "bytes": source.stat().st_size,
            "probe": probe_source(source),
        },
        "annotation_status_sha256": sha256_file(status_path),
        "task_toml_sha256": sha256_file(task_root / "task.toml"),
        "judge_sha256": sha256_file(
            task_root / "steps" / "solve" / "tests" / "judge.py"
        ),
        "canonical_prompt_sha256": sha256_file(instruction_path),
        "rendered_prompt_sha256": hashlib.sha256(
            rendered_prompt.encode("utf-8")
        ).hexdigest(),
        "path_localization_only": {
            "from": "/workspace",
            "to": str(workspace),
        },
        "workspace_started_empty": True,
    }

    write_exclusive(prompt_artifact, rendered_prompt)
    write_exclusive(
        manifest_artifact,
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )
    (workspace / "input-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    print(workspace)


if __name__ == "__main__":
    main()
