#!/usr/bin/env python3
"""Copy a raw agent transcript into calibration/rollouts, sanitized.

Three things change and nothing else. Base64 image blobs of 2000 characters or more become
a placeholder that records the length, so a reviewer still sees that a frame was viewed
and how big it was without carrying 300 MB of pixels into the repository. Absolute local
paths become the paths the same files have in the shipped image. Email addresses become
`<email>`, because a CLI can write its signed-in account into its session record. Every command the agent
ran, every tool call and every word it wrote is left alone, so the turn count in
`scores.md` can be recounted from the file rather than taken on trust.

    python3 calibration/ship_rollout.py --run-dir /abs/run \\
        --out calibration/rollouts/claude.jsonl --home /Users/someone raw.jsonl [raw2 ...]

Several raw files may be given at once and are concatenated in the order given. That is
for a harness that writes one file per process, not for a run split across agents: every
arm of this calibration is one agent in one session, and `calibration/scores.md` records
the artifact that proves it for each.

Files are read and written a line at a time, split on newline only. Codex's session record
for one run is hundreds of megabytes, and str.splitlines() would also split a JSON line at
a literal U+2028 inside a string.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

B64 = re.compile(r'"([A-Za-z0-9+/]{2000,}={0,2})"')
# The same payload inside a data URL, which is how Codex's session record carries each frame
# it viewed, both as JSON and inside the Python-repr history a context compaction stores.
DATA_URL = re.compile(r'base64,([A-Za-z0-9+/]{2000,}={0,2})')
# Claude Code records the signed-in account's address in the session context it keeps.
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", nargs="+", type=Path)
    ap.add_argument("--run-dir", required=True, help="the run directory, becomes /workspace")
    ap.add_argument("--home", default=str(Path.home()), help="the user's home, becomes /home/user")
    ap.add_argument("--materials", default=None,
                    help="the directory <run-dir>/materials points at, becomes "
                         "/workspace/materials. In local calibration materials is a "
                         "symlink out to the transcoded clips, so an `ls -la` in the "
                         "trajectory prints the target and rewriting only the run "
                         "directory leaves that scratch path in the shipped file.")
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    run_dir = args.run_dir.rstrip("/")
    materials = args.materials.rstrip("/") if args.materials else None

    n_blobs = 0
    n_emails = 0
    n_lines = 0
    leftover: list[int] = []

    def sub(m: re.Match) -> str:
        nonlocal n_blobs
        n_blobs += 1
        return f'"<elided base64 image, {len(m.group(1))} chars>"'

    def sub_url(m: re.Match) -> str:
        nonlocal n_blobs
        n_blobs += 1
        return f'base64,<elided base64 image, {len(m.group(1))} chars>'

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w") as out:
        for src in args.raw:
            with src.open(errors="replace", newline="\n") as fh:
                for line in fh:
                    line = line.rstrip("\n")
                    if not line.strip():
                        continue
                    line = DATA_URL.sub(sub_url, line)
                    line = B64.sub(sub, line)
                    line, n = EMAIL.subn("<email>", line)
                    n_emails += n
                    # materials first: it can sit outside the run directory, and rewriting
                    # the run directory first would not touch it.
                    if materials:
                        line = line.replace(materials, "/workspace/materials")
                    line = line.replace(run_dir, "/workspace")
                    line = line.replace(args.home.rstrip("/"), "/home/user")
                    n_lines += 1
                    if "/Users/" in line or "claude-501" in line or "/private/tmp/" in line:
                        leftover.append(n_lines)
                    out.write(line + "\n")

    print(f"{args.out.name}: {n_lines} lines from {len(args.raw)} file(s), "
          f"{n_blobs} image blobs elided, {n_emails} email address(es) replaced, "
          f"{args.out.stat().st_size / 1e6:.1f} MB")
    if leftover:
        print(f"  WARNING {len(leftover)} line(s) still hold a local path, first at "
              f"line {leftover[0]}")
    else:
        print("  no local path survives in the shipped file")


if __name__ == "__main__":
    main()
