#!/usr/bin/env python3
"""Build a clean local-video Harbor task copy for one manual calibration run."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[2]
VIDEO_SHA256 = "076bcc59fc48443d24a72a87162021470b9e645b41c858c3ffa5b5b25bae36cd"
BASE_IMAGE = (
    "python:3.12-slim@sha256:"
    "2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def task_commit() -> str:
    result = subprocess.run(
        ["git", "-C", str(TASK_DIR), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def worktree_dirty(*paths: str) -> bool:
    command = ["git", "-C", str(TASK_DIR), "status", "--porcelain"]
    if paths:
        command.extend(["--", *paths])
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def validate_video(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise SystemExit(f"video does not exist: {path}")
    digest = sha256(path)
    if digest != VIDEO_SHA256:
        raise SystemExit(f"video SHA256 mismatch: {digest}")
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return {"host_ffprobe": "unavailable; Docker build performs stream validation"}
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate,nb_read_frames:format=duration",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    probe = json.loads(result.stdout)
    stream = probe["streams"][0]
    if (
        stream.get("width") != 1280
        or stream.get("height") != 720
        or stream.get("r_frame_rate") != "50/1"
    ):
        raise SystemExit(f"unexpected video stream: {stream}")
    return probe


def validate_version(value: str) -> str:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?", value):
        raise SystemExit(f"invalid CLI version: {value}")
    return value


def dockerfile(agent: str, cli_version: str | None) -> str:
    packages = "ffmpeg ca-certificates curl procps ripgrep nodejs npm"
    install = ""
    if agent == "claude":
        if cli_version is None:
            raise SystemExit("--cli-version is required for Claude")
        version = validate_version(cli_version)
        install = (
            "RUN curl -fsSL https://downloads.claude.ai/claude-code-releases/"
            f"bootstrap.sh | bash -s -- {version} \\\n"
            " && /root/.local/bin/claude --version\n"
        )
    elif agent == "antigravity":
        install = ""
    else:
        raise SystemExit(f"unsupported agent: {agent}")

    return f"""FROM {BASE_IMAGE}

RUN apt-get update && apt-get install -y --no-install-recommends \\
        {packages} \\
    && rm -rf /var/lib/apt/lists/*

{install}
COPY match.mp4 /baked/match.mp4
RUN echo \"{VIDEO_SHA256}  /baked/match.mp4\" | sha256sum -c - \\
 && ffprobe -v error -select_streams v:0 \\
      -show_entries stream=width,height,r_frame_rate -show_entries format=duration \\
      -of default=noprint_wrappers=1 /baked/match.mp4 >/tmp/video-probe \\
 && grep -qx 'width=1280' /tmp/video-probe \\
 && grep -qx 'height=720' /tmp/video-probe \\
 && grep -qx 'r_frame_rate=50/1' /tmp/video-probe \\
 && grep -qx 'duration=880.640000' /tmp/video-probe \\
 && rm /tmp/video-probe

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=True, choices=("claude", "antigravity"))
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cli-version")
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite existing directory: {output}")

    probe = validate_video(args.video.resolve())
    output.mkdir(parents=True)
    shutil.copy2(TASK_DIR / "task.toml", output / "task.toml")
    shutil.copytree(TASK_DIR / "steps", output / "steps")
    environment = output / "environment"
    environment.mkdir()
    shutil.copy2(args.video.resolve(), environment / "match.mp4")
    (environment / "Dockerfile").write_text(
        dockerfile(args.agent, args.cli_version), encoding="utf-8"
    )

    manifest = {
        "agent": args.agent,
        "task_commit": task_commit(),
        "source_worktree_dirty": worktree_dirty(),
        "scored_payload_dirty": worktree_dirty("task.toml", "steps"),
        "instruction_sha256": sha256(output / "steps/solve/instruction.md"),
        "judge_sha256": sha256(output / "steps/solve/tests/judge.py"),
        "ground_truth_sha256": sha256(
            output / "steps/solve/tests/ground_truth.json"
        ),
        "video_sha256": VIDEO_SHA256,
        "video_probe": probe,
        "base_image": BASE_IMAGE,
        "cli_version_requested": args.cli_version,
        "model_visible_files": ["/workspace/materials/match.mp4"],
        "excluded": [
            "calibration rollouts",
            "prior solutions",
            "prior rewards",
            "prior trajectories",
            "ground truth and verifier files from /workspace",
        ],
    }
    (output / "MANUAL_RUN_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))
    print(f"prepared clean task: {output}")


if __name__ == "__main__":
    main()
