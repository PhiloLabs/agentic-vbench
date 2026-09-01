#!/usr/bin/env python3
"""Run the Codex or Claude Code arm inside the frozen task image.

    python3 calibration/run_in_image.py --arm codex  --image cc4d:pinned --run-dir /abs/run
    python3 calibration/run_in_image.py --arm claude --image cc4d:pinned --run-dir /abs/run

Why this file exists. The two in-image arms that produced the shipped numbers were driven
by hand, and `run_arm.py` said so: only its codex entry had ever run through it. The hand
commands then lived in a scratch directory, which was wiped, and all that survived were
the `argv` fields in the rollout manifests. That is the failure `run_arm.py` was written
to prevent, one level down, so the container half is written here rather than retyped.

Antigravity is not here. It runs under Harbor, which owns its container; see
`calibration/antigravity_in_image.md`.

What this holds, and how:

1. One arm at a time. `run_arm.py`'s lock and process scan, imported rather than copied.
2. The budget is `task.toml`'s own `steps.agent.timeout_sec`, read at run time.
3. The prompt is the shipped prompt, asserted to be a pure path substitution.
4. Egress is reduced to the model API and checked in BOTH directions before the agent
   starts: the allowed host must resolve and connect, and a disallowed one must not. A
   one-directional check passes just as happily on a container with no network at all.
5. The agent runs as a non-root user, because Claude Code refuses to bypass permissions
   as root and a container is root by default.
6. Credentials are copied in with `docker cp`, which moves the file without printing it,
   and the container is removed afterwards.
7. Before the real run, the CLI is asked to answer one trivial prompt in the same
   container. A model API the arm cannot actually reach is otherwise discovered six
   hours later, and the run that discovers it looks like a bad score rather than a
   broken setup.
8. manifest.json records the image id, the resolved argv, the prompt digest, wall
   clock, exit code, and both checks' own results.
"""
from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_arm  # noqa: E402  the lock, the scan, the budget and the prompt come from here

TASK = HERE.parent

# The one host each CLI must reach, and one it must not. The negative is a host with no
# business being reachable from a calibration run; if it answers, the restriction is not
# in force and the run is not comparable to the others.
ARMS = {
    "codex": {
        "api_host": "chatgpt.com",
        "cred_src": Path.home() / ".codex" / "auth.json",
        "cred_dst": "/home/agent/.codex/auth.json",
        "trajectory": "codex.jsonl",
        "model": "gpt-5.6-sol",
        "effort": "xhigh",
        "version_cmd": ["codex", "--version"],
        "preflight": 'cd /tmp && codex exec --skip-git-repo-check -m gpt-5.6-sol '
                     '"reply with the single word OK" 2>&1 | tail -5',
        "cli": (
            'cd /workspace && codex exec --json -m gpt-5.6-sol '
            '-c model_reasoning_effort="xhigh" '
            '--dangerously-bypass-approvals-and-sandbox --skip-git-repo-check '
            '--cd /workspace < /workspace/instruction.md'
        ),
    },
    "claude": {
        "api_host": "api.anthropic.com",
        "cred_src": Path.home() / ".claude",
        "cred_dst": "/home/agent/.claude",
        "trajectory": "claude.jsonl",
        "model": "claude-opus-4-8",
        "effort": "default",
        "version_cmd": ["claude", "--version"],
        # --disallowedTools is the one-agent protocol, not a difficulty knob: an earlier
        # attempt without it spawned 29 subagents and produced no answer at all.
        "preflight": 'cd /tmp && claude -p "reply with the single word OK" '
                     '--model claude-opus-4-8 --permission-mode bypassPermissions '
                     '2>&1 | tail -5',
        "cli": (
            'cd /workspace && claude -p "$(cat /workspace/instruction.md)" '
            '--model claude-opus-4-8 --output-format stream-json --verbose '
            '--permission-mode bypassPermissions '
            '--disallowedTools Agent Task Monitor SendMessage ToolSearch WebFetch WebSearch'
        ),
    },
}
DENIED_HOST = "example.com"


def sh(*args: str, check: bool = True, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), capture_output=True, text=True, check=check, **kw)


def resolve(host: str) -> str:
    try:
        return socket.gethostbyname(host)
    except OSError as exc:
        raise SystemExit(f"cannot resolve {host} on this host: {exc}")


def dexec(cid: str, command: str, user: str = "root", check: bool = True):
    return sh("docker", "exec", "-u", user, cid, "sh", "-lc", command, check=check)


def egress_check(cid: str, api_host: str) -> dict:
    """The allowed host must answer and the denied one must not. Both, or neither means
    anything: a container with no network at all passes a one-directional check."""
    allowed = dexec(cid, f"curl -s -o /dev/null -m 20 -w '%{{http_code}}' https://{api_host}/",
                    check=False)
    denied = dexec(cid, f"curl -s -o /dev/null -m 12 -w '%{{http_code}}' https://{DENIED_HOST}/",
                   check=False)
    ok_allowed = allowed.stdout.strip() not in ("", "000")
    ok_denied = denied.stdout.strip() in ("", "000")
    result = {"allowed_host": api_host, "allowed_reachable": ok_allowed,
              "denied_host": DENIED_HOST, "denied_reachable": not ok_denied}
    if not ok_allowed:
        raise SystemExit(f"{api_host} is not reachable from the container; the arm would "
                         f"fail for the wrong reason")
    if not ok_denied:
        raise SystemExit(f"{DENIED_HOST} IS reachable from the container; egress is not "
                         f"restricted and this run is not comparable to the others")
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True, choices=sorted(ARMS))
    ap.add_argument("--image", required=True)
    ap.add_argument("--run-dir", required=True, type=Path)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    arm = ARMS[args.arm]

    assert arm["cred_src"].exists(), f"no credential at {arm['cred_src']}"
    image_id = sh("docker", "image", "inspect", args.image, "--format", "{{.Id}}").stdout.strip()
    budget = run_arm.budget_sec()
    api_ip = resolve(arm["api_host"])
    version = run_arm.harness_version(arm["version_cmd"])

    args.run_dir.mkdir(parents=True, exist_ok=True)
    prompt = run_arm.make_prompts.base_prompt("/workspace")
    shipped = (TASK / "steps" / "solve" / "instruction.md").read_text()
    assert prompt == shipped, "the calibration prompt is not the shipped prompt"
    (args.run_dir / "instruction.md").write_text(prompt)
    import hashlib
    digest = hashlib.sha256(prompt.encode()).hexdigest()

    # DNS is pointed at nothing and the one host the CLI needs is pinned by address, so
    # the container can reach the model API and nothing else it might look something up on.
    create = ["docker", "run", "-d", "--platform", "linux/arm64",
              "--dns", "127.0.0.1", "--add-host", f"{arm['api_host']}:{api_ip}",
              args.image, "sleep", "infinity"]
    if args.dry_run:
        print("would create:", " ".join(create))
        print("would exec  :", arm["cli"])
        print(f"budget {budget:.0f}s, image {image_id}, prompt {digest[:16]}")
        return 0

    with run_arm.Lock(args.arm):
        busy = run_arm.other_arm_running()
        assert not busy, f"another arm is running: {busy}"
        cid = sh(*create).stdout.strip()
        try:
            dexec(cid, "id -u agent >/dev/null 2>&1 || useradd -m -s /bin/bash agent")
            dexec(cid, "mkdir -p /workspace/materials /workspace/output /workspace/work && "
                       "cp /baked/*.mp4 /workspace/materials/ && "
                       "chown -R agent /workspace")
            n = int(dexec(cid, "ls /workspace/materials/*.mp4 | wc -l").stdout.strip())
            assert n == run_arm.n_videos(), f"staged {n} recordings, expected {run_arm.n_videos()}"
            sh("docker", "cp", str(args.run_dir / "instruction.md"), f"{cid}:/workspace/instruction.md")
            sh("docker", "cp", str(arm["cred_src"]), f"{cid}:{arm['cred_dst']}")
            dexec(cid, f"chown -R agent {arm['cred_dst']}")
            egress = egress_check(cid, arm["api_host"])
            pre = dexec(cid, arm["preflight"], user="agent", check=False)
            if pre.returncode != 0 or "OK" not in (pre.stdout or ""):
                raise SystemExit(
                    "the CLI could not answer a one-word prompt inside the container, "
                    "so the arm would have spent its whole budget failing for a reason "
                    "that is not the task:\n"
                    f"  exit {pre.returncode}\n"
                    f"  {(pre.stdout or pre.stderr).strip()[:600]}")

            started = time.time()
            run = subprocess.run(
                ["docker", "exec", "-u", "agent", cid, "sh", "-lc", arm["cli"]],
                capture_output=True, text=True, timeout=budget)
            wall = time.time() - started
            (args.run_dir / arm["trajectory"]).write_text(run.stdout)
            (args.run_dir / f"{args.arm}.stderr.txt").write_text(run.stderr)
            got = dexec(cid, "cat /workspace/output/solution.json", check=False)
            wrote = got.returncode == 0 and got.stdout.strip().startswith(("{", "["))
            if wrote:
                (args.run_dir / "solution.json").write_text(got.stdout)
        finally:
            sh("docker", "rm", "-f", cid, check=False)

    entries = None
    if wrote:
        doc = json.loads((args.run_dir / "solution.json").read_text())
        entries = len(doc["sequence"] if isinstance(doc, dict) else doc)
    manifest = {
        "arm": args.arm, "model": arm["model"], "reasoning_effort": arm["effort"],
        "harness_version": f"{version}, run inside the task image",
        "image": args.image, "image_id": image_id,
        "one_session_whole_corpus": True, "videos": run_arm.n_videos(),
        "budget_sec": budget, "budget_source": "task.toml steps.agent.timeout_sec",
        "argv": ["docker", "exec", "-u", "agent", "<container>", "sh", "-lc", arm["cli"]],
        "create_argv": create[:-3] + ["<image>", "sleep", "infinity"],
        "prompt_sha256": digest, "ran_inside_the_task_image": True,
        "egress_check": egress,
        "preflight_answered": True,
        "wall_sec": round(wall, 1), "exit_code": run.returncode,
        "budget_bound": wall >= budget - 1,
        "solution_written": wrote, "solution_entries": entries,
    }
    (args.run_dir / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"{args.arm}: exit {run.returncode}, {wall/60:.1f} min, "
          f"solution {'yes' if wrote else 'NO'}"
          + (f", {entries} entries" if entries else ""))
    return 0 if (run.returncode == 0 and wrote) else 1


if __name__ == "__main__":
    raise SystemExit(main())
