#!/usr/bin/env python3
"""Run one calibration process group under a non-extendable wall-clock deadline."""

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", required=True, type=int)
    parser.add_argument("--cwd", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--stderr", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--stdin-file", type=Path)
    prompt_group.add_argument("--prompt-file", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    command_template = list(args.command)
    if command_template and command_template[0] == "--":
        command_template.pop(0)
    if not command_template:
        raise SystemExit("missing command after --")
    resume_tokens = {"--continue", "-c", "--conversation", "resume", "--resume", "-r"}
    if any(
        value in resume_tokens
        or value.startswith("--conversation=")
        or value.startswith("--resume=")
        for value in command_template
    ):
        raise SystemExit("resume and continuation commands are forbidden")
    if args.seconds != 5400:
        raise SystemExit("calibration deadline must be exactly 5400 seconds")

    cwd = args.cwd.resolve()
    output = args.output.resolve()
    stderr_path = args.stderr.resolve()
    metadata = args.metadata.resolve()
    if not cwd.is_dir():
        raise SystemExit(f"workspace does not exist: {cwd}")
    for path in (output, stderr_path, metadata):
        if path.exists():
            raise SystemExit(f"refusing to overwrite run artifact: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)

    prompt_bytes = None
    command = list(command_template)
    stdin_handle = None
    if args.stdin_file is not None:
        prompt_bytes = args.stdin_file.resolve().read_bytes()
        stdin_handle = args.stdin_file.resolve().open("rb")
    elif args.prompt_file is not None:
        prompt_bytes = args.prompt_file.resolve().read_bytes()
        prompt_text = prompt_bytes.decode("utf-8")
        if command.count("__PROMPT__") != 1:
            raise SystemExit("command must contain exactly one __PROMPT__ token")
        command = [prompt_text if value == "__PROMPT__" else value for value in command]

    started = datetime.now(timezone.utc)
    timed_out = False
    process_returncode = None

    try:
        with output.open("xb") as stdout_handle, stderr_path.open("xb") as err_handle:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdin=stdin_handle,
                stdout=stdout_handle,
                stderr=err_handle,
                start_new_session=True,
            )
            try:
                process_returncode = process.wait(timeout=args.seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
                process_returncode = process.returncode
    finally:
        if stdin_handle is not None:
            stdin_handle.close()

    finished = datetime.now(timezone.utc)
    wrapper_exit_code = 124 if timed_out else process_returncode
    record = {
        "schema_version": 1,
        "started_at_utc": started.isoformat(),
        "finished_at_utc": finished.isoformat(),
        "elapsed_seconds": round((finished - started).total_seconds(), 3),
        "deadline_seconds": args.seconds,
        "timed_out": timed_out,
        "continued_or_resumed": False,
        "cwd": str(cwd),
        "command_template": command_template,
        "prompt_sha256": sha256_bytes(prompt_bytes) if prompt_bytes else None,
        "stdout_artifact": output.name,
        "stderr_artifact": stderr_path.name,
        "process_returncode": process_returncode,
        "wrapper_exit_code": wrapper_exit_code,
    }
    with metadata.open("x", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
        handle.write("\n")

    raise SystemExit(wrapper_exit_code)


if __name__ == "__main__":
    main()
