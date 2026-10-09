#!/usr/bin/env python3
"""Run the Antigravity arm inside the task image, under Harbor.

    python3 calibration/run_antigravity.py --run-dir /abs/run [--token /abs/antigravity-oauth-token]

Harbor owns this arm's container, its egress control, the credential seeding and the
artifact collection, so none of that is re-implemented here. What this file adds is what
Harbor does not hold on its own:

1. arm_protocol's lock and capacity check, so this arm never starts without room on the
   Docker engine for the CPUs task.toml declares, and the manifest records what was running;
2. the budget read from task.toml and handed to agy as its own print timeout, because agy
   otherwise stops every run at five minutes whatever the task grants;
3. a pinned Harbor, and the full command line written into the manifest;
4. the trajectory, solution and reward copied out of Harbor's job directory next to a
   manifest in the same shape as the other two arms, with the solution regraded by the
   shipped judge and required to agree with the verifier's reward;
5. the one-agent check. harbor_agents.py installs calibration/antigravity_hooks.json, which
   denies agy's subagent tools, and copies every session agy recorded. The manifest counts
   those sessions, and only a run with exactly one is marked one_session.

calibration/harbor_agents.py carries the flags, the hook and the transcript path the stock
adapter misses; calibration/antigravity_in_image.md records why, and the hosts below.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TASK / "provenance" / "ablations"))
import arm_protocol  # noqa: E402
from run_measured import grade  # noqa: E402

HARBOR = "harbor==0.21.0"
AGENT = "calibration.harbor_agents:AntigravityCliWithEffort"
HOOKS = HERE / "antigravity_hooks.json"
# Hosts the vendor's installer reads, open only while the agent is installed.
ENVIRONMENT_HOSTS = [
    "antigravity.google",
    "antigravity-cli-auto-updater-974169037036.us-central1.run.app",
    "storage.googleapis.com",
]
# Hosts agy needs to authenticate and reach its model, open only while the agent runs.
AGENT_HOSTS = [
    "daily-cloudcode-pa.googleapis.com",
    "cloudcode-pa.googleapis.com",
    "generativelanguage.googleapis.com",
    "oauth2.googleapis.com",
    "accounts.google.com",
    "www.googleapis.com",
    "lh3.googleusercontent.com",
    "antigravity.google",
]
DEFAULT_TOKEN = Path.home() / ".gemini" / "antigravity-cli" / "antigravity-oauth-token"


def subagent_calls(transcript: Path) -> int:
    """Tool calls to any subagent tool in a transcript, which the hook should have denied."""
    n = 0
    for line in transcript.open(errors="replace"):
        try:
            row = json.loads(line)
        except Exception:
            continue
        n += sum(1 for c in row.get("tool_calls") or [] if "subagent" in str(c.get("name", "")))
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True, type=Path)
    ap.add_argument("--token", type=Path, default=DEFAULT_TOKEN,
                    help="agy's plaintext OAuth token file, made once by Harbor's sign-in helper")
    ap.add_argument("--model", default="google/gemini-3.6-flash")
    ap.add_argument("--effort", default="high")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    run_dir = args.run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    token = args.token.expanduser().resolve()
    assert token.is_file(), f"no agy token at {token}"
    assert token.stat().st_size <= 100_000, f"{token} is not a token file"
    hooks = json.loads(HOOKS.read_text())
    budget = arm_protocol.budget_sec()
    cpus, memory_mb = arm_protocol.declared_resources()
    job = "antigravity-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    argv = ["uvx", "--from", HARBOR, "harbor", "run",
            "--path", str(TASK), "--agent", AGENT, "--model", args.model,
            "--ak", f"reasoning_effort={args.effort}", "--ak", f"print_timeout={int(budget)}s",
            "--env", "docker", "--n-concurrent", "1", "--n-attempts", "1",
            "--jobs-dir", str(run_dir / "jobs"), "--job-name", job, "--yes"]
    for h in ENVIRONMENT_HOSTS:
        argv += ["--allow-environment-host", h]
    for h in AGENT_HOSTS:
        argv += ["--allow-agent-host", h]
    # The token path goes through the environment, never the command line, so it is not in
    # Harbor's logs or in the manifest. PYTHONPATH makes the calibration package importable.
    env = dict(os.environ, AGY_AUTH_JSON_PATH=str(token), PYTHONPATH=str(TASK))
    prompt_sha = hashlib.sha256((TASK / "steps" / "solve" / "instruction.md").read_bytes()).hexdigest()

    print("command:", " ".join(argv))
    print(f"budget {budget:.0f} s, {cpus} CPUs, model {args.model} at {args.effort}, prompt {prompt_sha[:16]}")
    print(f"hook installed as ~/.gemini/config/hooks.json: {list(hooks)}")
    if args.dry_run:
        print("running now:", arm_protocol.running_containers())
        return 0

    with arm_protocol.Lock("antigravity"):
        running_at_start = arm_protocol.running_containers()
        blockers = arm_protocol.capacity_blockers(cpus)
        assert not blockers, (f"no room on the Docker engine for this arm's declared {cpus} CPUs "
                              f"beside what is running: {blockers}")
        started = time.time()
        with (run_dir / "harbor.log").open("w") as log:
            proc = subprocess.run(argv, cwd=TASK, env=env, stdout=log, stderr=subprocess.STDOUT)
        wall = time.time() - started

    # A trial is a result.json beside its own config.json. This task declares its agent work
    # as steps/solve, so Harbor files the agent, artifacts and verifier under that step.
    results = sorted((run_dir / "jobs" / job).rglob("result.json"))
    trials = [p.parent for p in results if (p.parent / "config.json").is_file()
              and ((p.parent / "steps" / "solve").is_dir() or (p.parent / "agent").is_dir())]
    assert len(trials) == 1, f"expected one trial under {run_dir / 'jobs' / job}, found {len(trials)}"
    trial = trials[0]
    result = json.loads((trial / "result.json").read_text())
    step = trial / "steps" / "solve" if (trial / "steps" / "solve").is_dir() else trial

    sessions = sorted((step / "agent" / "sessions").glob("*.jsonl"))
    if sessions:
        shutil.copytree(step / "agent" / "sessions", run_dir / "sessions", dirs_exist_ok=True)
    traj = step / "agent" / "antigravity-cli.trajectory.jsonl"
    attempted = None
    if traj.is_file():
        shutil.copy2(traj, run_dir / "antigravity.jsonl")
        attempted = subagent_calls(traj)
    solutions = sorted(step.rglob("solution.json"))
    wrote = bool(solutions)
    if wrote:
        shutil.copy2(solutions[0], run_dir / "solution.json")
    reward_path = step / "verifier" / "reward.json"
    reward = json.loads(reward_path.read_text())["reward"] if reward_path.is_file() else None
    entries = None
    if wrote:
        seq = json.loads((run_dir / "solution.json").read_text()).get("sequence", [])
        entries = len(seq)
        regraded = grade(seq)["f1"]
        assert reward is None or abs(regraded - reward) < 1e-9, (
            f"the verifier said {reward} but regrading the solution gives {regraded}")

    manifest = {
        "arm": "antigravity", "model": args.model, "reasoning_effort": args.effort,
        "harness_version": f"Harbor 0.21.0 / Antigravity CLI "
                           f"{(result.get('agent_info') or {}).get('version', 'unknown')}, "
                           f"run inside the task image",
        "harness_agent": AGENT,
        "one_session": len(sessions) == 1,
        "sessions_recorded": len(sessions),
        "subagent_hook": hooks, "subagent_hook_path": "~/.gemini/config/hooks.json",
        "subagent_tool_calls_attempted": attempted,
        "budget_sec": budget, "budget_source": "task.toml steps.agent.timeout_sec",
        "print_timeout": f"{int(budget)}s",
        "cpus": cpus, "memory_mb": memory_mb, "resources_source": "task.toml [environment], applied by Harbor",
        "running_at_start": running_at_start,
        "argv": argv,
        "prompt_sha256": prompt_sha, "ran_inside_the_task_image": True,
        "egress": {"environment_phase": ENVIRONMENT_HOSTS, "agent_phase": AGENT_HOSTS,
                   "policy": "task.toml allow_internet=false, with Harbor phase overrides"},
        "trajectory": "antigravity.jsonl" if traj.is_file() else None,
        "harbor_job": job, "harbor_exit_code": proc.returncode,
        "wall_sec": round(wall, 1),
        "solution_written": wrote, "solution_entries": entries, "verifier_reward": reward,
        "run_dir": "/workspace", "materials": "/workspace/materials",
    }
    if wrote:
        manifest["solution_sha256"] = hashlib.sha256((run_dir / "solution.json").read_bytes()).hexdigest()
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"antigravity: harbor exit {proc.returncode}, {wall / 60:.1f} min, reward {reward}, "
          f"solution {'yes' if wrote else 'NO'}, trajectory {'yes' if traj.is_file() else 'NO'}, "
          f"{len(sessions)} session(s), {attempted} subagent call(s) attempted")
    return 0 if (wrote and traj.is_file() and len(sessions) == 1) else 1


if __name__ == "__main__":
    raise SystemExit(main())
