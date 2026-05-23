#!/usr/bin/env python3
"""avb — agentic-vbench CLI.

Thin discoverability + ergonomics layer over the Harbor harness.
Sandbox execution and scoring still happen through `harbor run` /
`harbor check`; this CLI just lists tasks, knows the env-var
requirements per family, and aggregates per-trial rewards.

Usage:
    avb tasks list [--family FAMILY]
    avb tasks check <task>
    avb tasks env   <task>
    avb run     <task> --agent AGENT [-m MODEL] [-e EXECUTOR]
    avb rollout --family FAMILY [--agent AGENT] [--env ENV]
    avb results show [--job JOB | --task TASK]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from _task_paths import FAMILIES, all_tasks, family_dir, task_dir  # noqa: E402


# ---- env-var matrices ------------------------------------------------------
# Per-agent: which env var Harbor needs `--ae` to inject for the agent step.
AGENT_ENV = {
    "claude-code": "ANTHROPIC_API_KEY",
    "codex":       "OPENAI_API_KEY",
    "gemini-cli":  "GEMINI_API_KEY",
    "opencode":    None,   # provider depends on -m flag; user passes manually
    "oracle":      None,
}

# Per-family: which env var Harbor needs `--ve` to inject for the verifier.
# repurpose runs a Gemini-based rubric judge; others use deterministic CPU code.
FAMILY_VERIFIER_ENV = {
    "agentic_vbench_repurpose": ["GEMINI_API_KEY"],
}


def _family_of(task_name: str) -> str:
    return family_dir(task_name).name


# ---- tasks list ------------------------------------------------------------
def cmd_tasks_list(args: argparse.Namespace) -> int:
    fam_arg = args.family
    if fam_arg and not fam_arg.startswith("agentic_vbench_"):
        fam_arg = f"agentic_vbench_{fam_arg}"
    if fam_arg and fam_arg not in FAMILIES:
        print(f"unknown family: {args.family}", file=sys.stderr)
        return 2
    grouped: dict[str, list[str]] = {}
    for p in all_tasks(family=fam_arg):
        grouped.setdefault(p.parent.name, []).append(p.name)
    for fam in FAMILIES:
        if fam not in grouped:
            continue
        names = sorted(grouped[fam])
        print(f"{fam}  ({len(names)} tasks)")
        for n in names:
            print(f"  {n}")
    return 0


# ---- tasks check -----------------------------------------------------------
def cmd_tasks_check(args: argparse.Namespace) -> int:
    p = task_dir(args.task)
    return subprocess.call(["harbor", "check", str(p)])


# ---- tasks env -------------------------------------------------------------
def cmd_tasks_env(args: argparse.Namespace) -> int:
    p = task_dir(args.task)
    fam = p.parent.name
    cfg = tomllib.loads((p / "task.toml").read_text())
    agent_env = list(cfg.get("environment", {}).get("env", {}).keys())
    verifier_env = FAMILY_VERIFIER_ENV.get(fam, [])
    print(f"task:      {args.task}")
    print(f"family:    {fam}")
    print(f"agent --ae:    {', '.join(agent_env) if agent_env else '(none)'}")
    print(f"verifier --ve: {', '.join(verifier_env) if verifier_env else '(none)'}")
    return 0


# ---- run -------------------------------------------------------------------
def cmd_run(args: argparse.Namespace) -> int:
    p = task_dir(args.task)
    fam = p.parent.name
    cmd = ["harbor", "run", "-p", str(p), "-e", args.env, "-a", args.agent]
    if args.model:
        cmd += ["-m", args.model]
    # Inject agent env if we know what the agent expects and the user has it.
    agent_key = AGENT_ENV.get(args.agent)
    if agent_key and os.environ.get(agent_key):
        cmd += ["--ae", f"{agent_key}={os.environ[agent_key]}"]
    elif agent_key:
        print(f"warning: {args.agent} typically needs {agent_key} — not set in env",
              file=sys.stderr)
    # Inject verifier env for families that need it.
    for key in FAMILY_VERIFIER_ENV.get(fam, []):
        if os.environ.get(key):
            cmd += ["--ve", f"{key}={os.environ[key]}"]
        else:
            print(f"warning: family {fam} verifier needs {key} — not set in env",
                  file=sys.stderr)
    if args.yes:
        cmd += ["--yes"]
    print("+", " ".join(cmd), file=sys.stderr)
    return subprocess.call(cmd)


# ---- rollout ---------------------------------------------------------------
def cmd_rollout(args: argparse.Namespace) -> int:
    fam = args.family
    if fam and not fam.startswith("agentic_vbench_"):
        fam = f"agentic_vbench_{fam}"
    if fam and fam not in FAMILIES:
        print(f"unknown family: {args.family}", file=sys.stderr)
        return 2
    tasks = [p.name for p in all_tasks(family=fam)]
    if not tasks:
        print(f"no tasks found for family {fam}", file=sys.stderr)
        return 2
    cmd = [
        sys.executable, str(REPO / "scripts" / "parallel_rollout.py"),
        "--mode", "claude" if args.agent == "claude-code" else args.agent,
        "--env", args.env,
        "--max-parallel", str(args.max_parallel),
        "--tasks", *tasks,
    ]
    print("+", " ".join(cmd), file=sys.stderr)
    return subprocess.call(cmd)


# ---- results show ----------------------------------------------------------
def _reward_files(job_dir: Path) -> list[Path]:
    return sorted(job_dir.glob("*/steps/solve/verifier/reward.json"))


def cmd_results_show(args: argparse.Namespace) -> int:
    jobs_dir = REPO / "jobs"
    if not jobs_dir.is_dir():
        print("no jobs/ dir yet", file=sys.stderr)
        return 1

    # Build (job_path, reward_file) pairs to show.
    pairs: list[tuple[Path, Path]] = []
    if args.job:
        job = jobs_dir / args.job
        if not job.is_dir():
            print(f"no such job: {args.job}", file=sys.stderr)
            return 1
        pairs = [(job, rf) for rf in _reward_files(job)]
    elif args.task:
        # Match trial dirs whose name starts with "<task>__".
        for rf in jobs_dir.glob(f"*/{args.task}__*/steps/solve/verifier/reward.json"):
            pairs.append((rf.parents[4], rf))
        pairs.sort(key=lambda x: x[1].stat().st_mtime, reverse=True)
        if not pairs:
            print(f"no rewards found for task {args.task}", file=sys.stderr)
            return 1
    else:
        # Latest job by mtime.
        candidates = [d for d in jobs_dir.iterdir() if d.is_dir()]
        if not candidates:
            print("no jobs yet", file=sys.stderr)
            return 1
        latest = max(candidates, key=lambda d: d.stat().st_mtime)
        pairs = [(latest, rf) for rf in _reward_files(latest)]
        if not pairs:
            print(f"latest job {latest.name} has no reward.json yet", file=sys.stderr)
            return 1

    print(f"{'job':<55s}  {'trial':<45s}  {'reward':>8s}")
    print("-" * 115)
    for job, rf in pairs:
        trial = rf.parents[3].name
        try:
            data = json.loads(rf.read_text())
            r = data.get("reward", "?")
            r_str = f"{r:.4f}" if isinstance(r, (int, float)) else str(r)
        except Exception as e:
            r_str = f"<err:{type(e).__name__}>"
        print(f"{job.name:<55s}  {trial:<45s}  {r_str:>8s}")
    return 0


# ---- arg parsing -----------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="avb",
        description="agentic-vbench CLI — list / check / run tasks via Harbor.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # tasks subtree
    p_tasks = sub.add_parser("tasks", help="Inspect the task tree.")
    sub_tasks = p_tasks.add_subparsers(dest="sub", required=True)
    s = sub_tasks.add_parser("list", help="List task names (optionally by family).")
    s.add_argument("--family", "-f", help="repair|assembly|sequencing|repurpose")
    s.set_defaults(func=cmd_tasks_list)
    s = sub_tasks.add_parser("check", help="Validate a task dir via `harbor check`.")
    s.add_argument("task")
    s.set_defaults(func=cmd_tasks_check)
    s = sub_tasks.add_parser("env", help="Show env-var requirements for a task.")
    s.add_argument("task")
    s.set_defaults(func=cmd_tasks_env)

    # run
    s = sub.add_parser("run", help="Run a single task via Harbor.")
    s.add_argument("task")
    s.add_argument("--agent", "-a", required=True,
                   help=f"one of: {', '.join(AGENT_ENV)}")
    s.add_argument("--model", "-m", help="model id (e.g. anthropic/claude-sonnet-4-6)")
    s.add_argument("--env", "-e", default="modal", choices=["docker", "modal"])
    s.add_argument("--yes", "-y", action="store_true", default=True,
                   help="pass --yes to harbor (default)")
    s.set_defaults(func=cmd_run)

    # rollout
    s = sub.add_parser("rollout", help="Run an entire family in parallel.")
    s.add_argument("--family", "-f", required=True)
    s.add_argument("--agent", "-a", default="claude-code")
    s.add_argument("--env", "-e", default="modal", choices=["docker", "modal"])
    s.add_argument("--max-parallel", type=int, default=20)
    s.set_defaults(func=cmd_rollout)

    # results
    p_res = sub.add_parser("results", help="Inspect reward.json files.")
    sub_res = p_res.add_subparsers(dest="sub", required=True)
    s = sub_res.add_parser("show", help="Print per-trial rewards.")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--job", help="job dir name under jobs/")
    g.add_argument("--task", help="show rewards for a specific task across jobs")
    s.set_defaults(func=cmd_results_show)

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
