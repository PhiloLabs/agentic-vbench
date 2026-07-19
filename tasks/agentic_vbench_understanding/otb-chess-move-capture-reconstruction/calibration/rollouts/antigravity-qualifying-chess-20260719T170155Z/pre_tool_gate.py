#!/usr/bin/env python3
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


BLOCKED_COMMAND = re.compile(
    r"(^|[;&|()\s])(?:/[^\s;&|()]*/)?"
    r"(?:pip3?|curl|wget|yt-dlp|brew|npm|npx|uv|conda|mamba|aria2c|"
    r"ssh|scp|telnet|nc)(?=$|[;&|()\s])|"
    r"\bpython(?:3(?:\.\d+)?)?\s+-m\s+pip\b|"
    r"\bgit\s+(?:clone|fetch|pull|ls-remote)\b|https?://",
    re.IGNORECASE,
)
ABSOLUTE_COMMAND_PATH = re.compile(r"(?<![A-Za-z0-9_.-])(/[^\s'\"`;|&()]+)")


def path_value(value):
    if not isinstance(value, str):
        return None
    if value.startswith("file://"):
        return unquote(urlparse(value).path)
    return value if value.startswith("/") else None


def iter_path_fields(value, key=""):
    if isinstance(value, dict):
        for child_key, child in value.items():
            yield from iter_path_fields(child, child_key)
    elif isinstance(value, list):
        for child in value:
            yield from iter_path_fields(child, key)
    elif any(token in key.lower() for token in ("path", "directory", "cwd", "targetfile")):
        candidate = path_value(value)
        if candidate:
            yield candidate


def main():
    payload = json.load(sys.stdin)
    tool_call = payload.get("toolCall") or {}
    name = str(tool_call.get("name") or "").lower()
    args = tool_call.get("args") or {}
    workspace_paths = [os.path.realpath(path) for path in payload.get("workspacePaths") or []]
    decision = "allow"
    reason = "Allowed by offline rollout gate."

    if any(token in name for token in ("url", "browser", "web", "mcp")):
        decision = "deny"
        reason = "Online and browser tools are disabled for this benchmark rollout."
    elif name == "run_command":
        command = str(args.get("CommandLine") or "")
        if args.get("BypassSandbox") is True:
            decision = "deny"
            reason = "Sandbox bypass is disabled for this benchmark rollout."
        elif BLOCKED_COMMAND.search(command):
            decision = "deny"
            reason = "Package installation and network commands are disabled."
        else:
            for match in ABSOLUTE_COMMAND_PATH.finditer(command):
                candidate = match.group(1)
                resolved = os.path.realpath(candidate)
                if candidate == "/dev/null":
                    continue
                if not any(resolved == root or resolved.startswith(root + os.sep) for root in workspace_paths):
                    decision = "deny"
                    reason = f"Outside-workspace command path is disabled: {candidate}"
                    break

    if decision == "allow" and workspace_paths:
        for candidate in iter_path_fields(args):
            resolved = os.path.realpath(candidate)
            if not any(resolved == root or resolved.startswith(root + os.sep) for root in workspace_paths):
                decision = "deny"
                reason = f"Outside-workspace path is disabled: {candidate}"
                break

    record = {
        "stepIdx": payload.get("stepIdx"),
        "tool": name,
        "decision": decision,
        "reason": reason,
    }
    audit_path = Path(__file__).with_name("hook-audit.jsonl")
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    json.dump({"decision": decision, "reason": reason}, sys.stdout)


if __name__ == "__main__":
    main()
