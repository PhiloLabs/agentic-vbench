#!/usr/bin/env python3
"""Stop an in-image calibration arm when its budget runs out.

    python3 calibration/budget_watchdog.py --container <name>

run_in_image.py stops an arm at its budget with `pkill -u agent -f <cli>` inside the
container. The task image is python:3.12-slim, which ships no procps, so that pkill is not
found, the `|| true` after it hides the failure, and the CLI would keep running through the
runner's 60 s grace. This watchdog enforces the budget the runner meant to enforce. It finds
the `sh -lc cd /workspace && ...` command run_in_image.py started as the agent, reads its age
from the container's own /proc, and once that age reaches the budget it sends SIGKILL to
every process the agent user owns.

The age comes from the container's clock, which stops while the Docker VM is paused, so time
the host spends asleep is not charged to the agent. The runner's timer, time.monotonic() on
macOS, does not count host sleep either.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arm_protocol  # noqa: E402  the budget, read from task.toml

AGENT_COMMAND = "sh -lc cd /workspace && "

# One exec prints the container's uptime and clock tick, then "pid stat" for each process
# whose command line starts with the command run_in_image.py runs as the agent.
PROBE = ('cut -d" " -f1 /proc/uptime; getconf CLK_TCK; '
         'for p in /proc/[0-9]*; do '
         'c=$(tr "\\0" " " < "$p/cmdline" 2>/dev/null); '
         'case "$c" in "' + AGENT_COMMAND + '"*) echo "${p#/proc/} $(cat "$p/stat" 2>/dev/null)";; esac; '
         'done')

# Linux's kill(-1, sig) reaches every process the caller may signal except init and itself.
KILL_AGENT = "import os, signal; os.kill(-1, signal.SIGKILL)"


def stamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def running(container: str) -> bool:
    r = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", container],
                       capture_output=True, text=True)
    return r.returncode == 0 and r.stdout.strip() == "true"


def agent_age(container: str) -> float | None:
    """Age in seconds of the oldest agent command in the container, None if there is none."""
    r = subprocess.run(["docker", "exec", container, "sh", "-c", PROBE], capture_output=True, text=True)
    lines = r.stdout.splitlines()
    if r.returncode != 0 or len(lines) < 2:
        return None
    uptime, tick = float(lines[0]), int(lines[1])
    ages = []
    for line in lines[2:]:
        _, _, stat = line.partition(" ")
        if ") " not in stat:
            continue
        start = int(stat.rsplit(") ", 1)[1].split()[19])  # stat field 22, starttime in ticks
        ages.append(uptime - start / tick)
    return max(ages) if ages else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--container", required=True)
    ap.add_argument("--budget-sec", type=float, default=None,
                    help="only for testing the watchdog on a throwaway container; arms use task.toml's")
    args = ap.parse_args()
    budget = args.budget_sec if args.budget_sec is not None else arm_protocol.budget_sec()
    age = agent_age(args.container)
    if age is None:
        print(f"{stamp()} no agent command is running in {args.container}")
        return 1
    print(f"{stamp()} {args.container}: agent command {age:.1f} s old, budget {budget:.0f} s", flush=True)
    while True:
        if not running(args.container):
            print(f"{stamp()} {args.container} was removed before the budget ran out", flush=True)
            return 0
        age = agent_age(args.container)
        if age is None:
            print(f"{stamp()} the agent command ended on its own at under {budget:.0f} s", flush=True)
            return 0
        left = budget - age
        if left <= 0:
            break
        time.sleep(min(30.0, left - 2) if left > 3 else max(0.05, left))

    kill = subprocess.run(["docker", "exec", "-u", "agent", args.container, "python3", "-c", KILL_AGENT],
                          capture_output=True, text=True)
    after = agent_age(args.container) if running(args.container) else None
    print(f"{stamp()} budget reached with the agent command {age:.1f} s old. SIGKILL sent to the "
          f"agent user's processes (exit {kill.returncode}), agent command "
          f"{'STILL RUNNING' if after is not None else 'gone'}", flush=True)
    return 0 if after is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
