#!/usr/bin/env python3
"""Relay commands from a workspace folder into the frozen task container.

The agent cannot reach the docker socket from inside its own sandbox, so it
never tries. It writes a command into _bridge/in/<id>.cmd and reads the result
from _bridge/out/<id>.out. This process, which is not sandboxed, is the only
thing that talks to docker.
"""
import os, subprocess, sys, time

BR  = sys.argv[1]
CT  = sys.argv[2] if len(sys.argv) > 2 else "avb_ag"
IN  = os.path.join(BR, "in")
OUT = os.path.join(BR, "out")
LOG = open(os.path.join(BR, "daemon.log"), "a", buffering=1)

os.makedirs(IN, exist_ok=True)
os.makedirs(OUT, exist_ok=True)
LOG.write(f"daemon up, container={CT}\n")

while True:
    for name in sorted(os.listdir(IN)):
        if not name.endswith(".cmd"):
            continue
        src = os.path.join(IN, name)
        try:
            cmd = open(src).read()
        except OSError:
            continue
        os.remove(src)
        rid = name[:-4]
        LOG.write(f"run {rid}: {cmd[:200]!r}\n")
        try:
            r = subprocess.run(
                ["docker", "exec", "-w", "/workspace", CT, "bash", "-lc", cmd],
                capture_output=True, text=True, timeout=1800, errors="replace")
            body = r.stdout + (("\n--- stderr ---\n" + r.stderr) if r.stderr else "")
            code = r.returncode
        except subprocess.TimeoutExpired:
            body, code = "command timed out after 1800s", 124
        tmp = os.path.join(OUT, rid + ".part")
        with open(tmp, "w") as f:
            f.write(f"exit_code: {code}\n{body}")
        os.rename(tmp, os.path.join(OUT, rid + ".out"))
        LOG.write(f"done {rid}: exit {code}, {len(body)} bytes\n")
    time.sleep(0.2)
