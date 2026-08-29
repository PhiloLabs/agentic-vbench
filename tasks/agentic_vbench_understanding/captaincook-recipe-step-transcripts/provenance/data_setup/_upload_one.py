#!/usr/bin/env python3
"""Upload one file to a HuggingFace dataset repo, and survive a stalled connection.

    python3 _upload_one.py <repo> <local file> <path in repo> [attempts] [stall_sec]

`hf upload` does not fail when the connection dies under it. On this machine, behind a
VPN that reassigns the client address, it keeps redrawing its progress bar with the byte
count frozen and its socket in CLOSE_WAIT, indefinitely. A retry loop that waits for the
process to exit therefore never retries: three separate uploads were lost to this before
the pattern was recognised, one of them after fourteen hours.

So progress is watched rather than exit status. If the transferred byte count has not
moved for `stall_sec`, the child is killed and the attempt is retried. Success is not
taken from the exit code either: the caller re-lists the repo and compares digests.
"""
from __future__ import annotations

import re
import subprocess
import sys
import time

PROG = re.compile(rb"(\d+(?:\.\d+)?)([kKMG])B?\s*/\s*\d")


def attempt(repo: str, local: str, dest: str, stall: float) -> int:
    p = subprocess.Popen(["hf", "upload", repo, local, dest, "--repo-type", "dataset"],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0)
    seen, last_move, last_val = b"", time.time(), -1.0
    try:
        while True:
            if p.poll() is not None:
                return p.returncode
            chunk = p.stdout.read(4096)
            if chunk:
                seen = (seen + chunk)[-4096:]
                m = None
                for m in PROG.finditer(seen):
                    pass
                if m:
                    scale = {b"k": 1e3, b"K": 1e3, b"M": 1e6, b"G": 1e9}[m.group(2)]
                    val = float(m.group(1)) * scale
                    if val > last_val:
                        last_val, last_move = val, time.time()
            if time.time() - last_move > stall:
                print(f"  stalled at {last_val/1e6:.1f} MB for {stall:.0f}s, killing",
                      flush=True)
                p.kill()
                p.wait()
                return 99
            time.sleep(0.5)
    finally:
        if p.poll() is None:
            p.kill()


def main() -> int:
    repo, local, dest = sys.argv[1], sys.argv[2], sys.argv[3]
    attempts = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    stall = float(sys.argv[5]) if len(sys.argv) > 5 else 120.0
    for i in range(1, attempts + 1):
        print(f"  {dest} attempt {i}/{attempts}", flush=True)
        rc = attempt(repo, local, dest, stall)
        if rc == 0:
            return 0
        time.sleep(min(60, 10 * i))
    print(f"  {dest}: gave up after {attempts} attempts", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
