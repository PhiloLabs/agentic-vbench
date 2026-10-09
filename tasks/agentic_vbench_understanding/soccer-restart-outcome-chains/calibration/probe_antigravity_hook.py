#!/usr/bin/env python3
"""Positive control for calibration/antigravity_hooks.json, the hook that keeps the
Antigravity arm to one agent.

    AGY_AUTH_JSON_PATH=/abs/antigravity-oauth-token python3 calibration/probe_antigravity_hook.py \\
        --image <image> [--model gemini-3.6-flash --effort high]

Installs agy in a fresh container of the image, the way Harbor's adapter does, and gives it a
prompt that asks for one subagent. It does that twice, with the model the arm runs. Without
the hook agy must record a second session, which proves the prompt really starts a subagent.
With the hook agy must record exactly one session and the model must still have tried the
tool, which proves the hook refused it. A hook that refuses nothing would fail the second
run, and a prompt that never asks for a subagent would fail the first. The token is copied in
with docker cp and never printed. The result lands in
calibration/rollouts/antigravity-hook-probe.json.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import arm_protocol  # noqa: E402

PROMPT = ("Use your invoke_subagent tool to start exactly one subagent whose only job is to "
          "reply with the word PING. Wait for it to finish, then say in one sentence whether "
          "the subagent ran.")
REASON = "Subagents are not available in this environment."
BRAIN = "/root/.gemini/antigravity-cli/brain"


def sh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(list(args), capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"{' '.join(args[:4])} ... failed ({r.returncode}):\n{(r.stderr or r.stdout)[-600:]}")
    return r


def probe(image: str, token: Path, with_hook: bool, model: str, effort: str) -> dict:
    cid = sh("docker", "run", "-d", "--platform", "linux/arm64", "--cpus", "1", "--memory", "2048m",
             image, "sleep", "infinity").stdout.strip()
    try:
        sh("docker", "exec", cid, "sh", "-c", "mkdir -p /root/.gemini/antigravity-cli /root/.gemini/config")
        sh("docker", "exec", cid, "bash", "-lc", "curl -fsSL https://antigravity.google/cli/install.sh | bash")
        sh("docker", "cp", str(token), f"{cid}:/root/.gemini/antigravity-cli/antigravity-oauth-token")
        sh("docker", "exec", cid, "chmod", "600", "/root/.gemini/antigravity-cli/antigravity-oauth-token")
        if with_hook:
            sh("docker", "cp", str(HERE / "antigravity_hooks.json"), f"{cid}:/root/.gemini/config/hooks.json")
        run = sh("docker", "exec", cid, "bash", "-lc",
                 "cd /tmp && $HOME/.local/bin/agy --dangerously-skip-permissions "
                 f"--model {shlex.quote(model)} --effort {shlex.quote(effort)} --print-timeout 10m "
                 f"--prompt={shlex.quote(PROMPT)} </dev/null", check=False)
        version = sh("docker", "exec", cid, "bash", "-lc", "$HOME/.local/bin/agy --version",
                     check=False).stdout.strip()
        files = sh("docker", "exec", cid, "sh", "-c",
                   f'for f in {BRAIN}/*/.system_generated/logs/transcript_full.jsonl; do '
                   '[ -f "$f" ] && echo "$f"; done', check=False).stdout.split()
        calls, denial_seen, errors = 0, False, []
        for f in files:
            text = sh("docker", "exec", cid, "cat", f).stdout
            denial_seen = denial_seen or REASON in text
            for line in text.splitlines():
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                calls += sum(1 for c in row.get("tool_calls") or [] if "subagent" in str(c.get("name", "")))
                if row.get("type") == "ERROR_MESSAGE" and row.get("error"):
                    errors.append(str(row["error"])[:200])
        return {"hook": with_hook, "model": model, "effort": effort, "agy_version": version,
                "exit_code": run.returncode, "sessions": len(files), "subagent_tool_calls": calls,
                "denial_reason_in_transcript": denial_seen, "model_errors": errors[-3:],
                "final_output": run.stdout.strip()[-400:]}
    finally:
        sh("docker", "rm", "-f", cid, check=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--model", default="gemini-3.6-flash", help="the model the arm runs, without the provider prefix")
    ap.add_argument("--effort", default="high")
    args = ap.parse_args()
    token = Path(os.environ.get("AGY_AUTH_JSON_PATH", "")).expanduser()
    assert token.is_file(), "set AGY_AUTH_JSON_PATH to agy's token file"
    assert REASON in (HERE / "antigravity_hooks.json").read_text(), "the probe checks for a reason the hook no longer gives"
    blockers = arm_protocol.capacity_blockers(1)
    assert not blockers, f"no room for one CPU beside what is running: {blockers}"

    without = probe(args.image, token, False, args.model, args.effort)
    assert not without["model_errors"] or without["sessions"] >= 2, (
        f"the model could not answer, so the probe cannot run: {without['model_errors']}")
    with_hook = probe(args.image, token, True, args.model, args.effort)
    record = {"ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "image": args.image,
              "prompt": PROMPT, "without_hook": without, "with_hook": with_hook}
    (HERE / "rollouts").mkdir(exist_ok=True)
    (HERE / "rollouts" / "antigravity-hook-probe.json").write_text(json.dumps(record, indent=1) + "\n")
    print(json.dumps(record, indent=1))
    assert without["sessions"] >= 2, "without the hook no subagent started, so this probe proves nothing"
    assert with_hook["subagent_tool_calls"] >= 1, "with the hook the model never tried a subagent"
    assert with_hook["sessions"] == 1, "with the hook agy still recorded a second session"
    print("hook holds: the prompt starts a subagent without it and cannot with it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
