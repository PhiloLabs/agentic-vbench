#!/usr/bin/env python3
"""Ship one finished calibration arm into calibration/rollouts, checking it on the way in.

    python3 calibration/ship_arm.py --arm codex --run-dir /abs/run

Everything a reviewer needs to audit an arm lands side by side, under names that start
with the arm:

    rollouts/<arm>.jsonl           the raw trajectory, sanitized by ship_rollout.py
    rollouts/<arm>-solution.json   what the agent submitted
    rollouts/<arm>-reward.json     the shipped judge's reward.json for that submission
    rollouts/<arm>-manifest.json   how the arm was run, from run_in_image.py or run_antigravity.py
    rollouts/<arm>-audit.txt       audit_trajectory.py's report on the shipped trajectory

For Codex and Claude Code the trajectory is the session record the CLI keeps itself, which
run_in_image.py copies out of the container, and the stream the CLI printed ships beside it
as rollouts/<arm>-events.jsonl. In code mode most Codex tool calls never reach its --json
stream, so an audit of that stream alone would undercount the run. Claude Code's stream
holds the same tool calls as its record, 242 each on the 2 s run, but it stops when the
runner stops, and during the 1 s run the runner was killed while the agent worked on.

The reward is recomputed by running steps/solve/tests/judge.py on the shipped submission,
the same entry point the verifier uses, and the tool-call count is the auditor's, read off
the shipped trajectory rather than the run directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
ROLLOUTS = HERE / "rollouts"


def run(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *argv], capture_output=True, text=True)


def session_file(arm: str, run_dir: Path, record: str | None) -> Path | None:
    """The one session that ran in /workspace, out of the record the runner copied.

    The two preflights run from /tmp, so they are told apart by working directory rather
    than by size or order, and a second /workspace session would mean the arm was not one
    session. Codex writes the directory into each record's first row. Claude Code files
    each record under a directory named after it, subagent transcripts included.
    """
    if not record:
        return None
    if arm == "claude":
        found = sorted((run_dir / record / "-workspace").rglob("*.jsonl"))
    else:
        found = []
        for f in sorted((run_dir / record).rglob("rollout-*.jsonl")):
            with f.open() as fh:
                first = json.loads(fh.readline())
            if first.get("type") == "session_meta" and (first.get("payload") or {}).get("cwd") == "/workspace":
                found.append(f)
    assert len(found) == 1, f"expected one {arm} session run in /workspace, found {len(found)}"
    return found[0]


def ship(raw: Path, run_dir: Path, out: Path) -> None:
    r = run(str(HERE / "ship_rollout.py"), str(raw), "--run-dir", str(run_dir), "--out", str(out))
    assert r.returncode == 0, r.stderr
    print(r.stdout.strip())
    assert "WARNING" not in r.stdout, f"{out.name} still holds a local path"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=["codex", "claude", "antigravity"])
    ap.add_argument("--run-dir", required=True, type=Path)
    args = ap.parse_args()
    src = args.run_dir.resolve()
    man = json.loads((src / "manifest.json").read_text())
    assert man.get("solution_written"), f"{args.arm} wrote no solution, so it is not a calibration row"
    assert man.get("one_session") is True, f"{args.arm} was not one agent in one session"
    traj = src / man["trajectory"]
    assert traj.is_file(), f"no trajectory at {traj}"
    ROLLOUTS.mkdir(exist_ok=True)

    shipped_traj = ROLLOUTS / f"{args.arm}.jsonl"
    extra = {}
    session = session_file(args.arm, src, man.get("session_record")) if args.arm != "antigravity" else None
    if session:
        events = ROLLOUTS / f"{args.arm}-events.jsonl"
        ship(traj, src, events)
        ship(session, src, shipped_traj)
        extra = {"events": events.name, "session_record_file": session.name}
    else:
        ship(traj, src, shipped_traj)

    sol = ROLLOUTS / f"{args.arm}-solution.json"
    shutil.copy2(src / "solution.json", sol)
    assert hashlib.sha256(sol.read_bytes()).hexdigest() == man["solution_sha256"], (
        "the solution does not match the digest its manifest recorded")

    reward = ROLLOUTS / f"{args.arm}-reward.json"
    r = run(str(TASK / "steps" / "solve" / "tests" / "judge.py"), "--solution", str(sol),
            "--reward-json", str(reward), "--reward-txt", str(src / "reward.txt"))
    assert r.returncode == 0, r.stderr
    details = json.loads(reward.read_text())["details"]

    (ROLLOUTS / f"{args.arm}-manifest.json").write_text(
        json.dumps(dict(man, trajectory=shipped_traj.name, **extra), indent=1) + "\n")

    audit = run(str(HERE / "audit_trajectory.py"), "--run-dir", "/workspace", "--rollout", str(shipped_traj))
    (ROLLOUTS / f"{args.arm}-audit.txt").write_text(audit.stdout + audit.stderr)
    turns = re.search(r"^tool calls: (\d+)", audit.stdout, re.M)
    verdict = re.search(r"^VERDICT: (.+)$", audit.stdout, re.M)

    print(f"{args.arm}: reward {details['f1']:.4f} | entries {details['n_predicted']} | "
          f"true positives {details['true_positives']} | "
          f"action+time {details['action_time_matches']} | "
          f"tool calls {turns.group(1) if turns else 'unread'} | "
          f"audit {verdict.group(1) if verdict else 'controls failed'} (exit {audit.returncode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
