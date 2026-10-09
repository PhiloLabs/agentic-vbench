#!/usr/bin/env python3
"""The run protocol every calibration arm shares: its budget, its resources, its lock.

1. The budget is task.toml's own steps.agent.timeout_sec, read at run time, so an arm gets
   what the shipped task grants and no number is chosen in a calibration script.
2. The resources are task.toml's own cpus and memory_mb, and an arm never gets less. The
   sibling CaptainCook4D task ran its arms strictly one at a time, because a starved agent
   scores lower and lower is the direction that would make a task look like it passes.
   What that rule protects is each arm's declared share, not the calendar, so arms here
   may overlap on one condition: the CPU limits of every container already running on the
   Docker engine, plus this arm's, must fit within the engine's CPUs. A container with no
   CPU limit counts as taking all of them. Each arm's manifest records what was running
   when it started.
3. One process per arm: a lock file per arm name, so the same arm cannot be started twice.

calibration/run_in_image.py uses this for the Codex and Claude Code arms, and
calibration/run_antigravity.py for the Antigravity arm under Harbor.
"""
from __future__ import annotations

import json
import os
import subprocess
import tomllib
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
# The name Harbor gives the egress-control sidecar of a trial, after its compose project.
HARBOR_EGRESS_SIDECAR = "egress-control-sidecar-1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def budget_sec() -> float:
    """The wall clock an arm gets, taken from the task's own agent step."""
    spec = tomllib.loads((TASK / "task.toml").read_text())
    solve = next((s for s in spec.get("steps") or [] if s.get("name") == "solve"), None)
    assert solve, "task.toml has no step named solve"
    value = (solve.get("agent") or {}).get("timeout_sec")
    assert isinstance(value, (int, float)) and value > 0, (
        f"steps.agent.timeout_sec is {value!r}; the budget must come from task.toml")
    return float(value)


def declared_resources() -> tuple[int, int]:
    """cpus and memory_mb, out of task.toml. Not defaults: the file is the contract."""
    env = tomllib.loads((TASK / "task.toml").read_text()).get("environment") or {}
    cpus, memory_mb = env.get("cpus"), env.get("memory_mb")
    assert isinstance(cpus, int) and isinstance(memory_mb, int), (
        "task.toml declares no cpus or memory_mb to run the arm under")
    return cpus, memory_mb


def _docker(*args: str) -> str:
    out = subprocess.run(["docker", *args], capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"docker {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout


def engine_cpus() -> float:
    n = float(_docker("info", "--format", "{{.NCPU}}").strip() or 0)
    assert n > 0, "cannot read the Docker engine's CPU count, so capacity cannot be checked"
    return n


def running_containers() -> dict[str, float]:
    """Every running container and the CPUs it may take. No limit means all of them.

    One exception. Harbor starts an egress-control sidecar with no CPU limit beside its task
    container, whose limit is counted. The sidecar only proxies the agent's API traffic, and
    counting its missing limit as the whole engine would hold every other arm back for the
    length of a Harbor run. It counts as zero and stays listed, so the manifest shows it.
    """
    total = engine_cpus()
    out: dict[str, float] = {}
    for cid in _docker("ps", "-q").split():
        name, nano, image = _docker("inspect", "-f", "{{.Name}} {{.HostConfig.NanoCpus}} {{.Config.Image}}",
                                    cid).split(maxsplit=2)
        name = name.lstrip("/")
        if int(nano) > 0:
            cpus = int(nano) / 1e9
        elif name.endswith(HARBOR_EGRESS_SIDECAR):
            cpus = 0.0
        else:
            cpus = total
        out[f"{name} ({image.strip()})"] = cpus
    return out


def capacity_blockers(requested_cpus: float) -> dict[str, float]:
    """Empty when this arm fits beside everything already running, else what is in the way."""
    running = running_containers()
    if sum(running.values()) + requested_cpus <= engine_cpus() + 1e-9:
        return {}
    return running


class Lock:
    """One process per arm name, across every shell on this machine."""

    def __init__(self, arm: str):
        self.arm = arm
        self.path = Path(f"/tmp/avb_calibration_arm.{arm}.lock")
        self.held = False

    def _stale(self) -> bool:
        try:
            held = json.loads(self.path.read_text())
        except Exception:
            return True  # an unreadable lock is stale by definition
        pid = held.get("pid")
        if not isinstance(pid, int):
            return True
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            print(f"clearing a stale lock left by pid {pid}, started {held.get('started_at')}")
            return True
        except PermissionError:
            return False  # alive and owned by someone else
        return False

    def __enter__(self):
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            except FileExistsError:
                if self._stale():
                    self.path.unlink(missing_ok=True)
                    continue
                held = json.loads(self.path.read_text())
                raise SystemExit(f"the {self.arm} arm is already running as pid {held.get('pid')} "
                                 f"since {held.get('started_at')}; if it is gone remove {self.path}")
            with os.fdopen(fd, "w") as fh:
                json.dump({"arm": self.arm, "pid": os.getpid(), "started_at": now()}, fh)
            self.held = True
            return self
        raise SystemExit(f"could not take {self.path}")

    def __exit__(self, *exc):
        if self.held:
            self.path.unlink(missing_ok=True)
