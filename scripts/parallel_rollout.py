#!/usr/bin/env python3
"""Parallel rollout orchestrator. Schedules harbor runs across tasks subject
to a memory budget. Tracks results into TSVs.

Usage:
  ANTHROPIC_API_KEY=sk-... python3 scripts/parallel_rollout.py --mode oracle
  ANTHROPIC_API_KEY=sk-... python3 scripts/parallel_rollout.py --mode claude
  python3 scripts/parallel_rollout.py --mode both
"""
import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from queue import Queue, Empty
from datetime import datetime

EXP = Path(__file__).resolve().parent.parent
TASKS_DIR = EXP / "tasks"
JOBS_DIR = EXP / "jobs"
LOGS_DIR = EXP / "logs"

# Per-task memory (MiB) — tuned to Docker host 7.65 GiB.
# Sums of any concurrent set must fit under ~7000 MiB.
WEIGHT = {
    "exp-codec-restore-task01":               1500,
    "exp-declip-task01":                       1500,
    "exp-dereverb-task01":                     1500,
    "exp-dns-denoise-task01":                  1500,
    "exp-voicebank-denoise-task01":            1500,
    "exp-content-cut-mkbhd-task01":            2000,
    "exp-content-cut-wsj-task01":              2000,
    "exp-disfluency-interview-3-task01":       2000,
    "exp-disfluency-interview-4-task01":       2000,
    "exp-disfluency-pitch-meeting-task01":     2000,
    "exp-glitch-dup-long-task01":              2000,
    "exp-glitch-dup-short-task01":             2000,
    "exp-swap-car-task01":                     2500,
    "exp-swap-product-task01":                 2500,
    "exp-sr-2x-shot-task01":                   2500,
    "exp-sr-4x-shot-task01":                   2500,
    "exp-deblur-gaussian-mkbhd-task01":        3000,
    "exp-deblur-motion-f1-task01":             3000,
    # Color-shot judges now use only numpy+opencv (deterministic LAB ΔE),
    # so the 6 GiB Q-Align reserve is no longer needed — shrink to fit
    # alongside other CPU-only tasks.
    "exp-color-shot-visit-korea-task01":       2500,
    "exp-color-shot-gobelins-task01":          2500,
    "exp-color-shot-v3-s1-task01":             2500,
}

# Budget: keep below host total minus OS reserve.
MEM_BUDGET_MIB = 6500


class Scheduler:
    def __init__(self, mode: str, env: str = "docker", max_parallel: int | None = None):
        self.mode = mode  # 'oracle' or 'claude'
        self.env = env    # 'docker' (local memory-budget) or 'modal' (remote, parallel)
        # On Modal each trial runs in a remote container, so the local
        # memory budget is irrelevant — just cap parallelism by count.
        self.max_parallel = max_parallel
        self.results_tsv = LOGS_DIR / ("smoke-results.tsv" if mode == "oracle" else "rollout-results.tsv")
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if mode == "claude" and not self.api_key:
            sys.exit("ANTHROPIC_API_KEY not set; required for claude mode")
        self.lock = threading.Lock()
        self.used_mem = 0
        self.queue = Queue()
        self.running = {}  # task_id -> thread
        self.completed = []
        self.failed = []

    def append_result(self, fields):
        with self.lock:
            with self.results_tsv.open("a") as f:
                f.write("\t".join(str(x) for x in fields) + "\n")

    def run_task(self, task_id):
        weight = WEIGHT.get(task_id, 2000)
        ts_short = datetime.now().strftime("%H%M%S")
        job_name = ("smoke-" if self.mode == "oracle" else "cc-") + f"{task_id}-{ts_short}"
        log_file = LOGS_DIR / f"{'smoke' if self.mode == 'oracle' else 'rollout'}-{task_id}.log"
        start = time.time()

        cmd = [
            "harbor", "run",
            "-p", str(TASKS_DIR),
            "-i", task_id,
            "-e", self.env,
            "-y",
            "--job-name", job_name,
            "--jobs-dir", str(JOBS_DIR),
        ]
        if self.mode == "oracle":
            cmd += ["-a", "oracle"]
            if self.api_key:
                cmd += ["--ve", f"ANTHROPIC_API_KEY={self.api_key}"]
        else:
            cmd += ["-a", "claude-code", "-m", "anthropic/claude-sonnet-4-6"]
            cmd += ["--ae", f"ANTHROPIC_API_KEY={self.api_key}"]
            cmd += ["--ve", f"ANTHROPIC_API_KEY={self.api_key}"]

        print(f"[{ts_short}] start  {task_id} (mem={weight} MiB, in_use={self.used_mem})", flush=True)

        with log_file.open("w") as lf:
            proc = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT)
        elapsed = int(time.time() - start)
        exit_code = proc.returncode

        # Find reward.json.
        job_dir = JOBS_DIR / job_name
        reward_files = list(job_dir.glob("**/verifier/reward.json"))
        reward = None
        if reward_files:
            try:
                reward = json.load(reward_files[0].open()).get("reward")
            except Exception:
                reward = None

        ts_done = datetime.now().strftime("%H%M%S")
        if reward is not None:
            status = "OK"
            print(f"[{ts_done}] DONE   {task_id} reward={reward:.4f} elapsed={elapsed}s", flush=True)
            if self.mode == "oracle":
                self.append_result([ts_done, task_id, reward, elapsed, status, str(job_dir)])
            else:
                cost_files = list(job_dir.glob("**/result.json"))
                cost = "?"
                if cost_files:
                    try:
                        d = json.load(cost_files[0].open())
                        cost = d.get("cost_usd", d.get("cost", "?"))
                    except Exception:
                        pass
                self.append_result([ts_done, task_id, reward, cost, elapsed, status, str(job_dir)])
            self.completed.append(task_id)
        else:
            status = f"FAIL(exit={exit_code})"
            print(f"[{ts_done}] FAIL   {task_id} exit={exit_code} elapsed={elapsed}s", flush=True)
            if self.mode == "oracle":
                self.append_result([ts_done, task_id, "-", elapsed, status, str(job_dir)])
            else:
                self.append_result([ts_done, task_id, "-", "-", elapsed, status, str(job_dir)])
            self.failed.append(task_id)

        with self.lock:
            self.used_mem -= weight
            del self.running[task_id]

    def can_start(self, task_id):
        # Modal: each trial runs remotely, so local memory budget doesn't
        # constrain parallelism. Cap by count instead (max_parallel).
        if self.env == "modal":
            return len(self.running) < (self.max_parallel or 8)
        weight = WEIGHT.get(task_id, 2000)
        return (self.used_mem + weight) <= MEM_BUDGET_MIB

    def schedule(self, tasks):
        # Sort heavy first so we never get stuck at the end with only the
        # 6 GiB color-shot tasks waiting for an empty slot.
        tasks = sorted(tasks, key=lambda t: -WEIGHT.get(t, 2000))
        for t in tasks:
            self.queue.put(t)

        pending = []
        while True:
            # Drain queue into pending list.
            try:
                while True:
                    pending.append(self.queue.get_nowait())
            except Empty:
                pass

            if not pending and not self.running:
                break

            # Try to schedule something.
            launched = []
            for t in pending:
                with self.lock:
                    if self.can_start(t) and t not in self.running:
                        weight = WEIGHT.get(t, 2000)
                        self.used_mem += weight
                        th = threading.Thread(target=self.run_task, args=(t,), daemon=True)
                        self.running[t] = th
                        th.start()
                        launched.append(t)
            for t in launched:
                pending.remove(t)

            time.sleep(5)

        return self.completed, self.failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["oracle", "claude", "both"], required=True)
    ap.add_argument("--tasks", nargs="*", help="Specific task ids; default = all in WEIGHT")
    ap.add_argument("--skip", nargs="*", default=[], help="Tasks to skip")
    ap.add_argument("--env", default="docker",
                    choices=["docker", "modal"],
                    help="Harbor environment (docker = local memory-budget; "
                         "modal = remote, count-budget)")
    ap.add_argument("--max-parallel", type=int, default=None,
                    help="Max concurrent jobs (modal only; default 8)")
    args = ap.parse_args()

    tasks = args.tasks or list(WEIGHT.keys())
    tasks = [t for t in tasks if t not in args.skip]
    if args.env == "modal":
        cap = args.max_parallel or 8
        print(f"Scheduling {len(tasks)} tasks, mode={args.mode}, env=modal, "
              f"max_parallel={cap}")
    else:
        print(f"Scheduling {len(tasks)} tasks, mode={args.mode}, env=docker, "
              f"budget={MEM_BUDGET_MIB} MiB")

    modes = ["oracle", "claude"] if args.mode == "both" else [args.mode]
    for m in modes:
        print(f"\n=== {m.upper()} ===")
        sched = Scheduler(m, env=args.env, max_parallel=args.max_parallel)
        done, fail = sched.schedule(list(tasks))
        print(f"\n{m.upper()} summary: {len(done)} ok, {len(fail)} fail")
        if fail:
            print(f"FAILED: {fail}")


if __name__ == "__main__":
    main()
