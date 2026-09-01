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
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_arm  # noqa: E402  the lock, the scan, the budget and the prompt come from here

TASK = HERE.parent

# The one host each CLI must reach, and one it must not. The negative is a host with no
# business being reachable from a calibration run; if it answers, the restriction is not
# in force and the run is not comparable to the others.
ARMS = {
    "codex": {
        "bin": "codex",
        "api_host": "chatgpt.com",
        "cred_src": Path.home() / ".codex" / "auth.json",
        "cred_dst": "/home/agent/.codex/auth.json",
        "install": "npm install -g @openai/codex@0.144.1 >/dev/null 2>&1",
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
        "bin": "claude",
        "api_host": "api.anthropic.com",
        # The credential file, not ~/.claude. That directory is every project transcript,
        # every cache and every history file this machine has, 4.5 GiB of them, and
        # copying it would put all of it inside a container an agent then runs in and into
        # the raw archive afterwards. Claude Code keeps its credential in the macOS
        # Keychain, so on this machine the file has to be produced once out of band, the
        # same way the Antigravity token was: sign in inside a keyring-less container,
        # which writes .credentials.json in plaintext, and point CLAUDE_CRED_FILE at it.
        "cred_src": Path(os.environ.get("CLAUDE_CRED_FILE",
                                        str(Path.home() / ".claude-cred" / ".credentials.json"))),
        "cred_dst": "/home/agent/.claude/.credentials.json",
        "install": "npm install -g @anthropic-ai/claude-code@2.1.251 >/dev/null 2>&1",
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


def declared_resources() -> tuple[int, int]:
    """cpus and memory_mb, out of task.toml. Not defaults: the file is the contract."""
    text = (TASK / "task.toml").read_text()
    cpus = re.search(r"^cpus\s*=\s*(\d+)", text, re.M)
    mem = re.search(r"^memory_mb\s*=\s*(\d+)", text, re.M)
    assert cpus and mem, "task.toml declares no cpus or memory_mb to run the arm under"
    return int(cpus.group(1)), int(mem.group(1))


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

    assert arm["cred_src"].exists(), (
        f"no credential at {arm['cred_src']}. For the claude arm, produce one with a "
        f"one-time sign-in in a container and point CLAUDE_CRED_FILE at the resulting "
        f".credentials.json; see calibration/scores.md.")
    # A credential is a file of a few kilobytes. Anything larger is a home directory that
    # was named by mistake, and copying one into the container would hand the agent every
    # transcript on this machine and put them in the archive. This guard exists because
    # that mistake was made here once.
    size = sum(f.stat().st_size for f in
               ([arm["cred_src"]] if arm["cred_src"].is_file()
                else arm["cred_src"].rglob("*")) if f.is_file())
    assert size <= 1_000_000, (
        f"{arm['cred_src']} is {size/1e6:.1f} MB, which is not a credential. Point this "
        f"at the credential file itself.")
    image_id = sh("docker", "image", "inspect", args.image, "--format", "{{.Id}}").stdout.strip()
    budget = run_arm.budget_sec()
    api_ip = resolve(arm["api_host"])

    args.run_dir.mkdir(parents=True, exist_ok=True)
    prompt = run_arm.make_prompts.base_prompt("/workspace")
    shipped = (TASK / "steps" / "solve" / "instruction.md").read_text()
    assert prompt == shipped, "the calibration prompt is not the shipped prompt"
    (args.run_dir / "instruction.md").write_text(prompt)
    import hashlib
    digest = hashlib.sha256(prompt.encode()).hexdigest()

    # The container gets exactly what task.toml declares, read from the file rather than
    # chosen here. Harbor applies those limits to its own arm; without them these two would
    # run against the whole daemon and the three arms would not be comparable. Memory in
    # particular is load-bearing: the Antigravity arm was OOM-killed twice under the old
    # declaration, so an arm running unconstrained beside it would be a different task.
    cpus, memory_mb = declared_resources()
    # The container starts with working DNS because the CLI has to be installed into it,
    # exactly as Harbor installs agy into its own. Egress is taken away afterwards and
    # before the agent runs: resolution is pointed at nothing and the one host the CLI
    # needs is pinned by address, so it can reach the model API and nothing else it might
    # look something up on. Doing it in that order rather than recreating the container
    # keeps the agent in the same filesystem the install produced.
    create = ["docker", "run", "-d", "--platform", "linux/arm64",
              "--cpus", str(cpus), "--memory", f"{memory_mb}m",
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
            # The CLI goes in first, before 13.9 GiB of media is copied into the
            # container's writable layer. Installing after that once failed with a bare
            # apt exit 100 that said nothing about why, and a setup step that fails
            # opaquely is worse than one that fails early.
            node = dexec(cid, "apt-get update -qq && DEBIAN_FRONTEND=noninteractive "
                              "apt-get install -y -qq nodejs npm", check=False)
            assert node.returncode == 0, (
                f"could not install node in the container (exit {node.returncode}):\n"
                f"{(node.stderr or node.stdout).strip()[-800:]}")
            cli = dexec(cid, arm["install"], check=False)
            where = dexec(cid, f"command -v {arm['bin']}", check=False)
            # The version is read from the container, not from this machine. Reading it
            # from the host recorded the host's CLI in the manifest of a run that used the
            # pinned one, and the two differed: 2.1.129 against the 2.1.251 the trajectory
            # itself carries. A manifest that names a version the run did not use is worse
            # than one that names none.
            version = " ".join(dexec(cid, f"{arm['bin']} --version",
                                     check=False).stdout.split()) or "unknown"
            assert where.returncode == 0 and where.stdout.strip(), (
                f"{arm['bin']} is not on PATH after install (exit {cli.returncode}):\n"
                f"{(cli.stderr or cli.stdout).strip()[-800:]}")

            dexec(cid, "id -u agent >/dev/null 2>&1 || useradd -m -s /bin/bash agent")
            # The shipped setup script, run rather than reimplemented. Harbor runs it for
            # its own arm, and a hand-written copy of it here would be a second thing to
            # keep in step: it also writes the materials listing the verifier collects and
            # asserts the count itself. The same reasoning the oracle check rests on.
            setup = TASK / "steps" / "solve" / "workdir" / "setup.sh"
            assert setup.is_file(), f"no setup script at {setup}"
            sh("docker", "cp", str(setup), f"{cid}:/tmp/setup.sh")
            dexec(cid, "mkdir -p /logs/artifacts && bash /tmp/setup.sh")
            dexec(cid, "chown -R agent /workspace /logs")
            n = int(dexec(cid, "ls /workspace/materials/*.mp4 | wc -l").stdout.strip())
            assert n == run_arm.n_videos(), f"staged {n} recordings, expected {run_arm.n_videos()}"
            sh("docker", "cp", str(args.run_dir / "instruction.md"), f"{cid}:/workspace/instruction.md")
            # docker cp will not create the parent, and a credential that lands nowhere
            # fails the arm much later, inside the CLI, as an auth error.
            parent = str(PurePosixPath(arm["cred_dst"]).parent)
            dexec(cid, f"mkdir -p {parent} && chown -R agent {parent}")
            sh("docker", "cp", str(arm["cred_src"]), f"{cid}:{arm['cred_dst']}")
            dexec(cid, f"chown -R agent {arm['cred_dst']}")
            # Now take the network away, keeping only the model API.
            dexec(cid, f"printf 'nameserver 127.0.0.1\\n' > /etc/resolv.conf && "
                       f"printf '%s %s\\n' {api_ip} {arm['api_host']} >> /etc/hosts")
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
        "harness_version_source": "the CLI inside the container, after install",
        "image": args.image, "image_id": image_id,
        "one_session_whole_corpus": True, "videos": run_arm.n_videos(),
        "budget_sec": budget, "budget_source": "task.toml steps.agent.timeout_sec",
        "cpus": cpus, "memory_mb": memory_mb, "resources_source": "task.toml [environment]",
        "cli_install": arm["install"],
        "egress_restricted_after_install": True,
        "argv": ["docker", "exec", "-u", "agent", "<container>", "sh", "-lc", arm["cli"]],
        "create_argv": create[:-3] + ["<image>", "sleep", "infinity"],
        "prompt_sha256": digest, "ran_inside_the_task_image": True,
        "run_dir": "/workspace", "materials": "/workspace/materials",
        "trajectory": arm["trajectory"],
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
