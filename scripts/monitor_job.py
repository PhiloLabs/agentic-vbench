#!/usr/bin/env python3
"""Summarise per-trial state for a running harbor job. Reports:
  - which trials have a finished result.json (and their reward)
  - which trials have started but are still running (no result.json yet)
  - which trials have exception_info populated (crashed / early-terminated)

Usage:
    python scripts/monitor_job.py jobs/<job-name>/
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        print("usage: monitor_job.py <job-dir>", file=sys.stderr)
        sys.exit(2)

    job_dir = Path(sys.argv[1])
    trials = sorted(p for p in job_dir.iterdir()
                    if p.is_dir() and not p.name.startswith("."))

    done, running, errored = [], [], []
    rewards = []

    for t in trials:
        result = t / "result.json"
        if not result.exists():
            running.append(t.name)
            continue
        try:
            data = json.loads(result.read_text())
        except json.JSONDecodeError:
            running.append(t.name + " [unparseable]")
            continue

        exc = data.get("exception_info")
        if exc:
            errored.append((t.name, exc.get("type", "?"), (exc.get("message") or "")[:80]))
            continue

        rew = (data.get("verifier_result") or {}).get("rewards", {}).get("reward")
        if rew is None:
            running.append(t.name + " [no reward yet]")
        else:
            done.append((t.name, rew))
            rewards.append(rew)

    print(f"=== {job_dir} ===")
    print(f"  done:    {len(done)}")
    print(f"  running: {len(running)}")
    print(f"  errored: {len(errored)}")
    if rewards:
        mean = sum(rewards) / len(rewards)
        print(f"  mean reward (so far): {mean:.4f}  min={min(rewards):.3f}  max={max(rewards):.3f}")
    if errored:
        print("\nerrored trials:")
        for name, typ, msg in errored:
            print(f"  - {name}  [{typ}]  {msg}")
    if running:
        print("\nstill running:")
        for n in running:
            print(f"  - {n}")
    if done:
        print("\ndone (reward):")
        for name, rew in sorted(done, key=lambda x: -x[1]):
            print(f"  - {rew:.3f}  {name}")


if __name__ == "__main__":
    main()
