#!/usr/bin/env python3
"""Run the Codex or Claude Code arm inside the task image.

    python3 calibration/run_in_image.py --arm codex  --image <image> --run-dir /abs/run
    python3 calibration/run_in_image.py --arm claude --image <image> --run-dir /abs/run

Ported from the CaptainCook4D task, where each property below was learned from a run that
failed without it. Antigravity is not here: it runs under Harbor, which owns its own
container; see calibration/antigravity_in_image.md.

1. Every arm gets exactly the cpus and memory task.toml declares, and never less. Arms may
   run side by side only when arm_protocol's capacity check finds room on the Docker engine
   for every running container's CPU limit plus this arm's, and the manifest records what
   was already running when this arm started.
2. The budget is task.toml's own steps.agent.timeout_sec, read at run time. An arm that
   reaches it is stopped with SIGKILL to every process the agent user owns, and the
   trajectory it streamed so far is kept rather than lost.
3. The prompt is the shipped prompt, byte for byte.
4. The agent runs as a non-root user, because Claude Code refuses to bypass permissions as
   root and a container is root by default.
5. Credentials are copied in with `docker cp`, which moves the file without printing it,
   and the container is removed afterwards.
6. The CLI answers a trivial question twice before the run: once with the network still
   open, so an expired token can refresh, and once after egress is cut down to the model
   API and the CLI's token endpoint. A refreshed credential is written back to the host file
   it came from, again with `docker cp` and never printed, because a refresh can rotate the
   token the next arm needs.
7. Egress is checked in BOTH directions before the agent starts: every allowed host must
   answer and a host with no business being reachable must not. A one-directional check
   passes just as happily on a container with no network at all.
8. manifest.json records the image id, the CLI version read inside the container, the
   argv, the prompt digest, wall clock, exit code, and both checks' own results.
9. The session record the CLI keeps itself is copied out before the container is removed.
   For Codex it is the complete trajectory, because in code mode most of what the agent
   does never reaches the --json stream.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import arm_protocol  # noqa: E402  the budget, the resources, the capacity check and the lock
import make_prompts  # noqa: E402

TASK = HERE.parent
MEDIA = "/workspace/materials/game.mp4"
MEDIA_BYTES = 1836710763  # the digest-checked file environment/Dockerfile bakes
# Linux's kill(-1, sig) reaches every process the caller may signal except init and itself,
# so run as the agent it ends the agent's side of the container and nothing of root's. The
# image has no procps, so the pkill this used to run was never found and stopped nothing.
KILL_AGENT = "import os, signal; os.kill(-1, signal.SIGKILL)"

ARMS = {
    "codex": {
        "bin": "codex",
        "api_host": "chatgpt.com",
        # Where the CLI refreshes its token. The first Codex run lost its answer without it:
        # the access token expired 53 minutes in, and with only chatgpt.com reachable the CLI
        # retried the refresh for four minutes and ended the run with no solution written.
        "auth_host": "auth.openai.com",
        "sessions": "/home/agent/.codex/sessions",
        "cred_src": Path.home() / ".codex" / "auth.json",
        "cred_dst": "/home/agent/.codex/auth.json",
        "install": "npm install -g @openai/codex@0.154.0 >/dev/null 2>&1",
        "trajectory": "codex.jsonl",
        "model": "gpt-5.6-sol",
        "effort": "xhigh",
        # The answer is read from --output-last-message, never from the log: codex echoes
        # the prompt into its log, so a log that merely contains the expected word proves
        # nothing. The file is removed first so a second preflight cannot pass on the first.
        "preflight": ('cd /tmp && rm -f /tmp/preflight.txt /tmp/preflight.log && '
                      'codex exec --skip-git-repo-check -m gpt-5.6-sol '
                      '-c model_reasoning_effort="xhigh" -o /tmp/preflight.txt '
                      '"What is 17 plus 25? Reply with the number only." >/tmp/preflight.log 2>&1; '
                      'if [ -s /tmp/preflight.txt ]; then echo "ANSWER: $(cat /tmp/preflight.txt)"; '
                      'else tail -5 /tmp/preflight.log; fi'),
        "cli": ('cd /workspace && codex exec --json -m gpt-5.6-sol '
                '-c model_reasoning_effort="xhigh" '
                '--dangerously-bypass-approvals-and-sandbox --skip-git-repo-check '
                '--cd /workspace < /workspace/instruction.md'),
    },
    "claude": {
        "bin": "claude",
        "api_host": "api.anthropic.com",
        # Where Claude Code 2.1.270 refreshes its token, read out of the installed binary.
        "auth_host": "platform.claude.com",
        "sessions": "/home/agent/.claude/projects",
        # The credential file, not ~/.claude, which holds every transcript on this machine.
        # Claude Code keeps its credential in the macOS Keychain, so this file is produced
        # once out of band by signing in inside a keyring-less container.
        "cred_src": Path(os.environ.get("CLAUDE_CRED_FILE",
                                        str(Path.home() / ".claude-cred" / ".credentials.json"))),
        "cred_dst": "/home/agent/.claude/.credentials.json",
        "install": "npm install -g @anthropic-ai/claude-code@2.1.270 >/dev/null 2>&1",
        "trajectory": "claude.jsonl",
        "model": "claude-opus-4-8",
        "effort": "xhigh",
        # stdout carries only the answer in print mode; errors go to their own file.
        "preflight": ('cd /tmp && out=$(claude -p "What is 17 plus 25? Reply with the number only." '
                      '--model claude-opus-4-8 --effort xhigh '
                      '--permission-mode bypassPermissions 2>/tmp/preflight.err); '
                      'echo "ANSWER: $out"; tail -3 /tmp/preflight.err'),
        # --disallowedTools is the one-agent protocol, not a difficulty knob: on the sibling
        # task an attempt without it spawned 29 subagents and produced no answer at all.
        "cli": ('cd /workspace && claude -p "$(cat /workspace/instruction.md)" '
                '--model claude-opus-4-8 --effort xhigh --output-format stream-json --verbose '
                '--permission-mode bypassPermissions '
                '--disallowedTools Agent Task Monitor SendMessage ToolSearch WebFetch WebSearch'),
    },
}
DENIED_HOST = "example.com"


def sh(*args: str, check: bool = True, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), capture_output=True, text=True, check=check, **kw)


def dexec(cid: str, command: str, user: str = "root", check: bool = True):
    return sh("docker", "exec", "-u", user, cid, "sh", "-lc", command, check=check)


def resolve(host: str) -> str:
    try:
        return socket.gethostbyname(host)
    except OSError as exc:
        raise SystemExit(f"cannot resolve {host} on this host: {exc}")


def preflight(cid: str, arm: dict, when: str) -> None:
    pre = dexec(cid, arm["preflight"], user="agent", check=False)
    # The expected answer appears nowhere in the prompt, and only after the ANSWER marker
    # the preflight itself prints, so an echoed prompt or an error page cannot pass.
    if not re.search(r"ANSWER:\s*42\b", pre.stdout or ""):
        raise SystemExit(
            f"the CLI could not answer a trivial prompt inside the container ({when}), so "
            f"the arm would spend its budget failing for a reason that is not the task:\n"
            f"  exit {pre.returncode}\n  {(pre.stdout or pre.stderr).strip()[:600]}")


def sync_credential_back(cid: str, arm: dict) -> bool:
    """Write a credential the CLI refreshed inside the container back to its host file."""
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "cred"
        if sh("docker", "cp", f"{cid}:{arm['cred_dst']}", str(dst), check=False).returncode != 0:
            return False
        new = dst.read_bytes()
        if new == arm["cred_src"].read_bytes():
            return False
        json.loads(new)  # still a credential file, not an error page
        staged = arm["cred_src"].with_name(arm["cred_src"].name + ".refreshed")
        staged.write_bytes(new)
        os.chmod(staged, 0o600)
        os.replace(staged, arm["cred_src"])
        return True


def egress_check(cid: str, allowed_hosts: list[str]) -> dict:
    """Every allowed host must answer and the denied one must not."""
    reachable = {}
    for host in allowed_hosts:
        r = dexec(cid, f"curl -s -o /dev/null -m 20 -w '%{{http_code}}' https://{host}/", check=False)
        reachable[host] = r.stdout.strip() not in ("", "000")
    denied = dexec(cid, f"curl -s -o /dev/null -m 12 -w '%{{http_code}}' https://{DENIED_HOST}/",
                   check=False)
    denied_reachable = denied.stdout.strip() not in ("", "000")
    result = {"allowed_reachable": reachable, "denied_host": DENIED_HOST,
              "denied_reachable": denied_reachable}
    dead = [h for h, ok in reachable.items() if not ok]
    if dead:
        raise SystemExit(f"{', '.join(dead)} not reachable from the container; the arm would "
                         f"fail for the wrong reason")
    if denied_reachable:
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
    run_dir = args.run_dir.resolve()

    src = arm["cred_src"]
    assert src.is_file(), f"no credential at {src}"
    # A credential is a file of a few kilobytes. Anything larger is a directory of
    # transcripts named by mistake, and copying it would hand the agent all of it.
    assert src.stat().st_size <= 1_000_000, f"{src} is not a credential file"
    image_id = sh("docker", "image", "inspect", args.image, "--format", "{{.Id}}").stdout.strip()
    budget = arm_protocol.budget_sec()
    cpus, memory_mb = arm_protocol.declared_resources()
    allowed = [arm["api_host"], arm["auth_host"]]

    run_dir.mkdir(parents=True, exist_ok=True)
    sessions = run_dir / f"{args.arm}-sessions"
    assert not sessions.exists(), f"{sessions} already exists; give each arm a fresh run directory"
    prompt = make_prompts.base_prompt("/workspace")
    shipped = (TASK / "steps" / "solve" / "instruction.md").read_text()
    assert prompt == shipped, "the calibration prompt is not the shipped prompt"
    (run_dir / "instruction.md").write_text(prompt)
    digest = hashlib.sha256(prompt.encode()).hexdigest()

    create = ["docker", "run", "-d", "--platform", "linux/arm64",
              "--label", f"avb.calibration.arm={args.arm}",
              "--cpus", str(cpus), "--memory", f"{memory_mb}m",
              args.image, "sleep", "infinity"]
    if args.dry_run:
        print("would create:", " ".join(create))
        print("would exec  :", arm["cli"])
        print(f"budget {budget:.0f}s, image {image_id}, prompt {digest[:16]}, egress to {allowed}")
        print("running now :", arm_protocol.running_containers())
        return 0

    refreshed = []
    with arm_protocol.Lock(args.arm):
        running_at_start = arm_protocol.running_containers()
        blockers = arm_protocol.capacity_blockers(cpus)
        assert not blockers, (f"no room on the Docker engine for this arm's declared {cpus} CPUs "
                              f"beside what is running: {blockers}")
        cid = sh(*create).stdout.strip()
        try:
            node = dexec(cid, "apt-get update -qq && DEBIAN_FRONTEND=noninteractive "
                              "apt-get install -y -qq nodejs npm", check=False)
            assert node.returncode == 0, (
                f"could not install node in the container (exit {node.returncode}):\n"
                f"{(node.stderr or node.stdout).strip()[-800:]}")
            cli = dexec(cid, arm["install"], check=False)
            where = dexec(cid, f"command -v {arm['bin']}", check=False)
            assert where.returncode == 0 and where.stdout.strip(), (
                f"{arm['bin']} is not on PATH after install (exit {cli.returncode}):\n"
                f"{(cli.stderr or cli.stdout).strip()[-800:]}")
            # Read from the container, not the host: the two CLIs differ.
            version = " ".join(dexec(cid, f"{arm['bin']} --version", check=False).stdout.split()) or "unknown"

            dexec(cid, "id -u agent >/dev/null 2>&1 || useradd -m -s /bin/bash agent")
            # The shipped setup script, run rather than reimplemented.
            sh("docker", "cp", str(TASK / "steps" / "solve" / "workdir" / "setup.sh"), f"{cid}:/tmp/setup.sh")
            dexec(cid, "mkdir -p /logs/artifacts && bash /tmp/setup.sh")
            staged = dexec(cid, f"stat -c %s {MEDIA}").stdout.strip()
            assert staged == str(MEDIA_BYTES), f"staged {MEDIA} is {staged} bytes, expected {MEDIA_BYTES}"
            sh("docker", "cp", str(run_dir / "instruction.md"), f"{cid}:/workspace/instruction.md")
            dexec(cid, "chown -R agent /workspace /logs")
            parent = str(PurePosixPath(arm["cred_dst"]).parent)
            dexec(cid, f"mkdir -p {parent}")
            sh("docker", "cp", str(src), f"{cid}:{arm['cred_dst']}")
            dexec(cid, "chown -R agent /home/agent")

            preflight(cid, arm, "network open")
            if sync_credential_back(cid, arm):
                refreshed.append("after the open preflight")
            pins = "".join(f" && printf '%s %s\\n' {resolve(h)} {h} >> /etc/hosts" for h in allowed)
            dexec(cid, f"printf 'nameserver 127.0.0.1\\n' > /etc/resolv.conf{pins}")
            egress = egress_check(cid, allowed)
            preflight(cid, arm, "egress restricted")

            traj = run_dir / arm["trajectory"]
            started = time.time()
            budget_bound = False
            with traj.open("w") as out, (run_dir / f"{args.arm}.stderr.txt").open("w") as err:
                proc = subprocess.Popen(["docker", "exec", "-u", "agent", cid, "sh", "-lc", arm["cli"]],
                                        stdout=out, stderr=err)
                try:
                    proc.wait(timeout=budget)
                except subprocess.TimeoutExpired:
                    budget_bound = True
                    print(f"budget of {budget:.0f} s reached; stopping the arm", flush=True)
                    sh("docker", "exec", "-u", "agent", cid, "python3", "-c", KILL_AGENT, check=False)
                    try:
                        proc.wait(timeout=60)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
            wall = time.time() - started
            got = dexec(cid, "cat /workspace/output/solution.json", check=False)
            wrote = got.returncode == 0 and got.stdout.strip().startswith(("{", "["))
            if wrote:
                (run_dir / "solution.json").write_text(got.stdout)
            if sync_credential_back(cid, arm):
                refreshed.append("after the run")
            copied = sh("docker", "cp", f"{cid}:{arm['sessions']}", str(sessions),
                        check=False).returncode == 0
        finally:
            sh("docker", "rm", "-f", cid, check=False)

    entries = None
    if wrote:
        doc = json.loads((run_dir / "solution.json").read_text())
        entries = len(doc.get("sequence", []) if isinstance(doc, dict) else doc)
    manifest = {
        "arm": args.arm, "model": arm["model"], "reasoning_effort": arm["effort"],
        "harness_version": f"{version}, run inside the task image",
        "harness_version_source": "the CLI inside the container, after install",
        "image": args.image, "image_id": image_id,
        "one_session": True,
        "budget_sec": budget, "budget_source": "task.toml steps.agent.timeout_sec",
        "cpus": cpus, "memory_mb": memory_mb, "resources_source": "task.toml [environment]",
        "running_at_start": running_at_start,
        "cli_install": arm["install"],
        "egress_restricted_after_install": True,
        "egress_allowed_hosts": allowed,
        "argv": ["docker", "exec", "-u", "agent", "<container>", "sh", "-lc", arm["cli"]],
        "create_argv": create[:-3] + ["<image>", "sleep", "infinity"],
        "prompt_sha256": digest, "ran_inside_the_task_image": True,
        "run_dir": "/workspace", "materials": "/workspace/materials",
        "trajectory": arm["trajectory"],
        "session_record": sessions.name if copied else None,
        "egress_check": egress,
        "preflight_answered": ["network open", "egress restricted"],
        "credential_refreshed": refreshed,
        "wall_sec": round(wall, 1), "exit_code": proc.returncode,
        "budget_bound": budget_bound,
        "solution_written": wrote, "solution_entries": entries,
    }
    if wrote:
        manifest["solution_sha256"] = hashlib.sha256((run_dir / "solution.json").read_bytes()).hexdigest()
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"{args.arm}: exit {proc.returncode}, {wall/60:.1f} min"
          f"{' (budget bound)' if budget_bound else ''}, solution {'yes' if wrote else 'NO'}"
          + (f", {entries} entries" if entries is not None else ""))
    return 0 if wrote else 1


if __name__ == "__main__":
    raise SystemExit(main())
