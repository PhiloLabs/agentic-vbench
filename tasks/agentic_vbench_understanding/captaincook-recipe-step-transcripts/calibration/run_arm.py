#!/usr/bin/env python3
"""Run one calibration arm under a pinned harness, alone, and record what ran.

Why this file exists. Version 4 reported a Claude Code score whose shipped trajectory
turned out to be a three-line authentication failure, so the model, the turn count and
even the shape of that run could not be read back from the record. Version 5 then scored
higher than version 4, and with version 4's shape unreadable there was no way to tell
whether the task had become easier or the run had become more generous. The fix is to
stop keeping the harness in memory and keep it in a file: one agent, one session, all
twenty-two recordings in that session, the budget the task itself grants, no second arm
running alongside, and a manifest written next to the trajectory stating exactly what ran.

For this task only the codex arm actually ran through this script. Claude Code and
Antigravity were driven by hand, because the Antigravity app has no headless entry point
and the claude CLI on this machine was not authenticated. Every property below was then
held by artifact instead, and calibration/scores.md names the artifact for each. The two
hand-driven ARMS entries below are therefore the intent; the manifests beside the
rollouts are the record of what ran.

    python3 calibration/run_arm.py --arm claude      --run-dir /abs/run
    python3 calibration/run_arm.py --arm codex       --run-dir /abs/run
    python3 calibration/run_arm.py --arm antigravity --run-dir /abs/run

Add --dry-run to build the run directory, resolve the harness version and print the exact
command without spending anything.

Five properties this script holds, and how each one is held:

1. One agent, one session. Each arm is a single non-interactive CLI invocation given the
   whole corpus, which is the command shape the family README prescribes. Splitting the
   corpus across one agent per recording hands every recording a full budget instead
   of a twenty-second of one, and that inflates the score without the task changing.
   On the sibling Ego-Exo4D task that difference was 0.1791 against 0.0029.
2. All twenty-two recordings. The prompt is derived from the shipped
   steps/solve/instruction.md by calibration/make_prompts.py, which already asserts
   the derivation is a pure path substitution. This script re-checks that assertion and records the prompt's digest.
3. A fixed budget, read from the task rather than chosen here. Neither CLI exposes a
   turn cap, so the budget is wall clock, and its value is task.toml's own
   steps.agent.timeout_sec so that a calibration run gets what the shipped task grants.
   Turn count is not a cap but a floor the family checks afterwards (> 50), and
   calibration/audit_trajectory.py counts it from the trajectory this script writes.
4. Alone. An exclusive lock plus a scan of the process table, because a starved agent
   scores lower and lower is the direction that would make this task look like it passes.
   The scan carries a positive control: it must find this session's own agent process
   before it is allowed to report that no arm is running.
5. Readable afterwards. The trajectory goes to a file, and manifest.json alongside it
   records harness version, model, reasoning effort, budget, argv, prompt digest, wall
   clock, exit code and whether the budget bound. A run whose manifest is missing or
   whose exit code is non-zero is not a result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
LOCK = Path("/tmp/avb_calibration_arm.lock")

sys.path.insert(0, str(HERE))
import make_prompts  # noqa: E402  - sibling module, imported for its checked derivation


# --------------------------------------------------------------------- the arms
#
# Model and reasoning effort are named here rather than left to each CLI's default, so
# that changing them is a visible edit to this file. The family README names the harnesses
# to calibrate against and, for Claude Code, names Fable 5 and Opus 4.8 as its models.

ARMS = {
    "claude": {
        "bin": "claude",
        "model": "claude-opus-4-8",
        "effort": "xhigh",
        "trajectory": "claude.jsonl",
        "version_cmd": ["claude", "--version"],
        "prompt_via": "stdin",
        "argv": lambda a, run: [
            "claude", "--print",
            "--verbose", "--output-format", "stream-json",
            "--model", a["model"],
            "--effort", a["effort"],
            "--permission-mode", "bypassPermissions",
            "--add-dir", str(run),
            # task.toml sets allow_internet = false, so the arm runs without the two
            # tools that would reach the network. This is parity with the shipped image,
            # not a difficulty knob; the prompt's no-lookup rule stays either way, and
            # audit_trajectory.py still checks the trajectory for shell-level network use.
            "--disallowedTools", "WebSearch,WebFetch",
        ],
    },
    "codex": {
        "bin": "codex",
        "model": "gpt-5.6-sol",
        "effort": "xhigh",
        "trajectory": "codex.jsonl",
        "version_cmd": ["codex", "--version"],
        "prompt_via": "stdin",
        "argv": lambda a, run: [
            "codex", "exec", "--json",
            "-m", a["model"],
            "-c", f'model_reasoning_effort="{a["effort"]}"',
            "-c", 'sandbox_mode="workspace-write"',
            "-c", "sandbox_workspace_write.network_access=false",
            "--skip-git-repo-check",
            "--cd", str(run),
        ],
    },
    "antigravity": {
        "bin": "gemini",
        # What the app arm was actually calibrated with, so this file and
        # rollouts/antigravity-manifest.json name the same model. The family README names
        # Gemini 3.5 Flash and 3.1 Pro; 3.6 Flash is newer, and using a stronger model is
        # the conservative direction for a ceiling gate.
        "model": "gemini-3.6-flash",
        "effort": "high",
        "trajectory": "antigravity.jsonl",
        "version_cmd": ["gemini", "--version"],
        "prompt_via": "argv",
        "argv": lambda a, run: [
            "gemini",
            "-m", a["model"],
            "--yolo", "--skip-trust",
            "--output-format", "stream-json",
        ],
    },
}

# Patterns that identify another arm already running. codex exec and gemini are
# unambiguous. A bare "claude" is not: this machine also runs the Claude Code app and
# whatever session is driving this script, and both of those are fine. A -p arm is
# distinguished by what it lacks, since the interactive harness always drives its child
# over a stream-json *input* channel with a permission-prompt tool, and an arm never does.
OTHER_ARM = [
    ("codex", re.compile(r"(^|/)codex\s+exec\b(?=.*--json)")),
    ("antigravity", re.compile(r"(^|/)gemini\b.*--output-format\s+stream-json")),
]
CLAUDE_ANY = re.compile(r"(^|/)claude\b")
CLAUDE_ARM = re.compile(r"(^|/)claude\b(?=.*--output-format\s+stream-json)"
                        r"(?!.*--input-format)(?!.*--permission-prompt-tool)")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------- the budget

def budget_sec() -> float:
    """The wall clock this arm gets, taken from the task's own agent step."""
    spec = tomllib.loads((TASK / "task.toml").read_text())
    steps = spec.get("steps") or []
    solve = next((s for s in steps if s.get("name") == "solve"), None)
    assert solve, "task.toml has no step named solve"
    value = ((solve.get("agent") or {}).get("timeout_sec"))
    assert isinstance(value, (int, float)) and value > 0, (
        f"steps.agent.timeout_sec is {value!r}; the budget must come from task.toml")
    return float(value)


# --------------------------------------------------------------------- the lock

class Lock:
    """One arm at a time, across every shell on this machine."""

    def __init__(self, arm: str):
        self.arm = arm
        self.held = False

    def _stale(self) -> bool:
        try:
            held = json.loads(LOCK.read_text())
        except Exception:
            return True  # unreadable lock is stale by definition
        pid = held.get("pid")
        if not isinstance(pid, int):
            return True
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            print(f"clearing a stale lock left by pid {pid} ({held.get('arm')}, "
                  f"started {held.get('started_at')})")
            return True
        except PermissionError:
            return False  # alive and owned by someone else
        return False

    def __enter__(self):
        for _ in range(2):
            try:
                fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                if self._stale():
                    LOCK.unlink(missing_ok=True)
                    continue
                held = json.loads(LOCK.read_text())
                raise SystemExit(
                    f"another arm holds the lock: {held.get('arm')} as pid {held.get('pid')} "
                    f"since {held.get('started_at')}.\nArms must not overlap; wait for it, "
                    f"or if it is gone remove {LOCK}.")
            with os.fdopen(fd, "w") as fh:
                json.dump({"arm": self.arm, "pid": os.getpid(), "started_at": now()}, fh)
            self.held = True
            return self
        raise SystemExit(f"could not take {LOCK}")

    def __exit__(self, *exc):
        if self.held:
            LOCK.unlink(missing_ok=True)


def _scan() -> dict[str, str]:
    """One pass over the process table. Maps "arm pid" to the command line that matched.

    A scan that cannot see the process table returns the same empty result as a machine
    with nothing running on it, and the two mean opposite things. So the pass first has to
    find this session's own agent process, which is known to exist because it is what
    launched this script's shell. Only after that control passes is an empty result
    believed.
    """
    out = subprocess.run(["ps", "-Ao", "pid=,command="], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"cannot read the process table: {out.stderr.strip()}")
    lines = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    assert len(lines) > 20, f"the process table came back with {len(lines)} rows; that is not a machine"
    if not any(CLAUDE_ANY.search(ln) for ln in lines):
        raise SystemExit(
            "positive control failed: the scan cannot see any claude process, not even the "
            "session that launched this script, so it cannot be trusted to report that no "
            "other arm is running. Fix the scan before running an arm.")

    mine = str(os.getpid())
    found = {}
    for ln in lines:
        pid, _, cmd = ln.partition(" ")
        if pid == mine or "run_arm.py" in cmd:
            continue
        name = next((n for n, pat in OTHER_ARM if pat.search(cmd)), None)
        if name is None and CLAUDE_ARM.search(cmd):
            name = "claude"
        if name:
            found[f"{name} pid {pid}"] = cmd[:200]
    return found


def other_arm_running(settle_sec: float = 5.0) -> dict[str, str]:
    """Report arms already running, confirmed by a second look.

    A single sample is a coin flip. Editor tooling and MCP servers spawn short-lived
    `codex exec` children that look exactly like a calibration arm for a second or two,
    and failing on one of those would block a legitimate run for no reason. A real arm
    runs for hours, so anything still present on a second pass is real. Nothing here
    weakens the guarantee: the lock, not this scan, is what makes overlap impossible.
    """
    first = _scan()
    if not first:
        return {}
    print(f"saw {len(first)} possible arm(s); looking again in {settle_sec:.0f} s to let "
          f"short-lived tooling clear")
    time.sleep(settle_sec)
    second = _scan()
    return {k: v for k, v in second.items() if k in first}


# ------------------------------------------------------------------ the run dir

def n_videos() -> int:
    """How many recordings this task ships, read from the key rather than hardcoded."""
    key = json.loads((TASK / "provenance" / "step-derived.json").read_text())
    return len(key["videos"])


def prepare(run_dir: Path, materials: Path) -> tuple[Path, str]:
    """Lay out the run directory and write the prompt this arm will be handed."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "output").mkdir(exist_ok=True)
    (run_dir / "work").mkdir(exist_ok=True)

    link = run_dir / "materials"
    if link.is_symlink() or link.exists():
        assert link.is_symlink(), f"{link} exists and is not a symlink; refusing to replace it"
        link.unlink()
    link.symlink_to(materials)
    baked = sorted(p.name for p in materials.glob("*.mp4"))
    expected = [f"{chr(65 + i)}.mp4" for i in range(n_videos())]
    assert baked == expected, (
        f"expected {len(expected)} baked recordings in {materials}, found {len(baked)}: {baked}")

    prompt = make_prompts.base_prompt(str(run_dir))
    shipped = (TASK / "steps" / "solve" / "instruction.md").read_text()
    assert prompt.replace(str(run_dir), "/workspace") == shipped, (
        "the calibration prompt is not a pure path substitution of the shipped prompt")
    assert len(make_prompts.video_table(prompt)) == n_videos(), \
        f"the prompt does not list {n_videos()} videos"
    (run_dir / "instruction.md").write_text(prompt)
    return run_dir / "instruction.md", hashlib.sha256(prompt.encode()).hexdigest()


def harness_version(cmd: list[str]) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception as exc:  # noqa: BLE001 - a missing CLI is reported, not raised
        return f"unavailable: {exc}"
    return (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr) else "unknown"


# ----------------------------------------------------------------------- the run

def run(arm_name: str, run_dir: Path, materials: Path, dry: bool) -> int:
    arm = ARMS[arm_name]
    if shutil.which(arm["bin"]) is None:
        raise SystemExit(f"{arm['bin']} is not on PATH")

    prompt_path, digest = prepare(run_dir, materials)
    prompt = prompt_path.read_text()
    argv = arm["argv"](arm, run_dir)
    if arm["prompt_via"] == "argv":
        argv += ["-p", prompt]
    budget = budget_sec()
    version = harness_version(arm["version_cmd"])

    traj = run_dir / arm["trajectory"]
    manifest_path = run_dir / "manifest.json"
    shown = argv[:-1] + ["<prompt>"] if arm["prompt_via"] == "argv" else argv
    manifest = {
        "arm": arm_name,
        "model": arm["model"],
        "reasoning_effort": arm["effort"],
        "harness_version": version,
        "one_session_whole_corpus": True,
        "videos": n_videos(),
        "budget_sec": budget,
        "budget_source": "task.toml steps.agent.timeout_sec",
        "argv": shown,
        "prompt_via": arm["prompt_via"],
        "prompt_sha256": digest,
        "prompt_is_pure_path_substitution": True,
        "run_dir": str(run_dir),
        "materials": str(materials.resolve()),
        "trajectory": traj.name,
        "host": {"cpu_count": os.cpu_count(),
                 "memory_gb": round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1)},
    }

    print(f"arm            {arm_name}")
    print(f"model          {arm['model']}  effort {arm['effort']}")
    print(f"harness        {version}")
    print(f"budget         {budget:.0f} s ({budget / 3600:.1f} h), from task.toml")
    print(f"run dir        {run_dir}")
    print(f"prompt sha256  {digest[:16]}…  ({len(prompt)} bytes, {n_videos()} videos)")
    print(f"command        {' '.join(shown)}")
    if dry:
        manifest["dry_run"] = True
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"\ndry run; wrote {manifest_path} and nothing was spent")
        return 0

    busy = other_arm_running()
    if busy:
        detail = "\n".join(f"  {k}: {cmd}" for k, cmd in busy.items())
        raise SystemExit(f"another arm is already running:\n{detail}\n"
                         "Arms must not overlap. A starved agent scores lower, and lower "
                         "is the direction that would make this task look like it passes.")

    with Lock(arm_name):
        started = time.time()
        manifest["started_at"] = now()
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        with traj.open("w") as out, (run_dir / f"{arm_name}.err").open("w") as err:
            proc = subprocess.Popen(
                argv, cwd=run_dir, stdout=out, stderr=err,
                stdin=subprocess.PIPE if arm["prompt_via"] == "stdin" else subprocess.DEVNULL,
                start_new_session=True)
            if arm["prompt_via"] == "stdin":
                proc.stdin.write(prompt.encode())
                proc.stdin.close()
            timed_out = False
            try:
                proc.wait(timeout=budget)
            except subprocess.TimeoutExpired:
                timed_out = True
                # Signal the whole process group, never `pkill -f`, which matches the
                # pattern against its own command line and can take out the caller.
                print(f"\nbudget of {budget:.0f} s reached; stopping the arm")
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGTERM)
                try:
                    proc.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    os.killpg(pgid, signal.SIGKILL)
                    proc.wait()

    wall = time.time() - started
    manifest.update({"ended_at": now(), "wall_sec": round(wall, 1),
                     "exit_code": proc.returncode, "budget_bound": timed_out})
    sol = run_dir / "output" / "solution.json"
    manifest["solution_written"] = sol.exists()
    if sol.exists():
        entries = json.loads(sol.read_text()).get("sequence", [])
        manifest["solution_entries"] = len(entries)
        manifest["solution_sha256"] = hashlib.sha256(sol.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"\nexit {proc.returncode} after {wall / 60:.1f} min"
          f"{' (budget bound)' if timed_out else ''}")
    print(f"trajectory     {traj}  ({traj.stat().st_size} bytes)")
    print(f"manifest       {manifest_path}")
    if not sol.exists():
        print(f"\nNO ANSWER: {sol} was never written. This is not a result.")
        return 1
    print(f"solution       {manifest['solution_entries']} entries")
    print(f"\nNext, and both are needed before this counts as a calibration row:\n"
          f"  python3 {TASK}/steps/solve/tests/judge.py --solution {sol} \\\n"
          f"      --reward-json {run_dir}/reward.json --reward-txt {run_dir}/reward.txt\n"
          f"  python3 {TASK}/calibration/audit_trajectory.py --run-dir {run_dir} "
          f"--rollout {traj}")
    return 0 if proc.returncode == 0 else proc.returncode


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--arm", required=True, choices=sorted(ARMS))
    ap.add_argument("--run-dir", required=True, type=Path,
                    help="absolute path for this run; it is created if missing")
    ap.add_argument("--materials", type=Path, default=None,
                    help="directory holding the baked recordings, A.mp4 onward")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    run_dir = args.run_dir.resolve()
    materials = (args.materials or run_dir.parent / "v5_materials").resolve()
    if not materials.is_dir():
        raise SystemExit(f"no materials directory at {materials}; pass --materials")
    raise SystemExit(run(args.arm, run_dir, materials, args.dry_run))


if __name__ == "__main__":
    main()
