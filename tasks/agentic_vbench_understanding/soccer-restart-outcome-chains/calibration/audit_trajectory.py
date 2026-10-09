#!/usr/bin/env python3
"""Read a calibration rollout and answer: did this agent cheat, and did it work hard.

The family README asks for the raw trajectory and for a turn count, and a score is only
worth what an audit of the trajectory says it is. This reads the rollout rather than a
summary: it counts real tool calls, lists every filesystem path the agent touched, and
looks for the ways this particular task could be shortcut, which are reading the answer
key, reaching the network, and naming the dataset the key comes from.

    python3 calibration/audit_trajectory.py --run-dir /workspace --rollout a.jsonl [b.jsonl ...]

Every check carries a positive control. A pattern search that returns zero on a file it
was never able to read returns the same zero as a clean run, so the script asserts that
it can find things that must be there before it reports the absence of things that must
not be. If a control fails the script exits 2 and reports nothing else.

Ported from the CaptainCook4D task's auditor. The readers for the three harnesses are
unchanged; the shortcut patterns and the media control are this task's own, and so is the
fourth reader, for the session record Codex keeps itself, which this task's Codex arm needed.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

# Ways this task could be shortcut rather than solved.
LEAKS = {
    "answer key or grader": r"judge\.py|GROUND_TRUTH|labels-derived|build_gt|align_halves|solve\.sh"
                            r"|Labels-v2|Labels-cameras",
    # The source of THIS task's key. An audit that greps for the wrong dataset name reports
    # every run clean no matter what the agent said, so the pattern is checked against the
    # shipped task.toml by the control below.
    "the source dataset by name": r"soccer\s?net",
    "the task package": r"agentic[_-]vbench|provenance/|steps/solve",
}
# Searched only in shell commands the agent actually ran. The prompt forbids looking
# anything up online, and a whole-transcript search for these words would find its own
# rule and report every clean run as dirty.
NETWORK_CMD = r"\bcurl\b|\bwget\b|\bgit\s+clone\b|\bpip\s+install\b|\bnc\b|\bssh\b|\byt-dlp\b"
NETWORK_TOOLS = {"WebSearch", "WebFetch"}

# Paths that belong to the agent's own harness rather than to this task, named rather than
# matched loosely, because widening this list is the one edit here that makes the audit
# report LESS: the Claude Code harness's task output on a host, and the Antigravity CLI's
# session state inside the container (its brain directory, scratch, logs and binary).
HARNESS_SCRATCH = re.compile(
    r"^/private/tmp/claude-[^/]+/[^/]+/[^/]+/tasks/[\w-]+\.output$"
    r"|^/root/\.gemini/antigravity-cli/"
    r"|^/root/\.agy/"
    r"|^/root/\.local/bin/agy$")
PATH_KEYS = ("file_path", "path", "notebook_path")
# Row types no reader claimed. Filled by blocks(), read by the controls in main().
UNROUTED: collections.Counter = collections.Counter()
# Antigravity row types that carry a turn. ERROR_MESSAGE is how that harness records that
# its own stream dropped; a row type no reader claims would otherwise read as nothing.
ANTIGRAVITY_ROWS = {"PLANNER_RESPONSE", "USER_INPUT", "CHECKPOINT", "GENERIC",
                    "SYSTEM_MESSAGE", "ERROR_MESSAGE"}
# Codex event types that carry no `item`, so the shape alone does not identify them.
CODEX_ROWS = {"thread.started", "turn.started", "turn.completed", "turn.failed", "error"}
# Row types of the session record Codex writes under ~/.codex/sessions. The settings rows
# (session_meta, turn_context, world_state, token_usage_record) are routed and not searched:
# they hold Codex's own system prompt and configuration, which neither the task nor the
# agent wrote.
CODEX_SESSION_ROWS = {"session_meta", "response_item", "event_msg", "turn_context",
                      "world_state", "compacted", "token_usage_record"}
CODEX_TOOL_ITEMS = {"custom_tool_call", "function_call", "local_shell_call"}


def _strings(x):
    """Every string inside a nested value, less image payloads and encrypted reasoning."""
    if isinstance(x, str):
        if not x.startswith("data:image"):
            yield x
    elif isinstance(x, list):
        for v in x:
            yield from _strings(v)
    elif isinstance(x, dict):
        for k, v in x.items():
            if k not in ("encrypted_content", "image_url"):
                yield from _strings(v)


def _claude_line(j: dict, stem: str):
    """Claude Code --output-format stream-json: tool calls live in message.content[]."""
    msg = j.get("message")
    if not isinstance(msg, dict):
        if isinstance(msg, str) and msg:
            yield "text", stem, msg
        return
    content = msg.get("content")
    if isinstance(content, str):
        yield "text", stem, content
    elif isinstance(content, list):
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                yield "tool", b.get("name", "?"), b.get("input") or {}
            elif b.get("type") in ("text", "thinking"):
                # Thinking too: a model naming its source from a frame grid does it there.
                yield "text", stem, b.get("text") or b.get("thinking") or ""
            elif b.get("type") == "tool_result":
                # What the tools handed back, so a leak that arrives in a result is seen.
                c = b.get("content")
                if isinstance(c, str):
                    yield "text", stem, c
                elif isinstance(c, list):
                    for sub in c:
                        if isinstance(sub, dict) and isinstance(sub.get("text"), str):
                            yield "text", stem, sub["text"]


def _codex_line(j: dict, stem: str):
    """Codex exec --json: one event per lifecycle item.

    Only `item.completed` is read, because Codex announces each item started and again
    completed and counting both would double the turn count. Shell commands arrive as
    `command_execution` and are mapped onto Bash; writes arrive as `file_change` and are
    mapped onto Write, one event per changed path.
    """
    if j.get("type") in CODEX_ROWS:
        msg = j.get("message")
        if isinstance(msg, str) and msg:
            yield "text", stem, msg
        return
    if j.get("type") != "item.completed":
        return
    item = j.get("item") or {}
    kind = item.get("type")
    if kind == "command_execution":
        yield "tool", "Bash", {"command": item.get("command") or ""}
        out = item.get("aggregated_output")
        if isinstance(out, str) and out:
            yield "text", stem, out
    elif kind == "file_change":
        for change in item.get("changes") or []:
            if isinstance(change, dict) and isinstance(change.get("path"), str):
                yield "tool", "Write", {"path": change["path"]}
    elif kind in ("agent_message", "error"):
        yield "text", stem, item.get("text") or item.get("message") or ""


def _codex_session_line(j: dict, stem: str):
    """The session record Codex keeps itself, which run_in_image.py copies out of the container.

    Codex's --json stream is not the whole run. In code mode each tool call the model makes
    is an `exec` script, and the shell commands and image views inside it mostly never reach
    the stream: this task's first Codex run streamed 37 commands out of 156 tool calls and
    none of its 460 image views. This record has all of them. A turn is a tool call the model
    issued. What a script did inside it is yielded as nested work, which the path and command
    scans read and the turn count does not add, so a script that views ten frames is one turn.
    """
    pl = j.get("payload") if isinstance(j.get("payload"), dict) else {}
    kind = j.get("type")
    if kind == "response_item":
        t = pl.get("type")
        if t in CODEX_TOOL_ITEMS:
            yield "tool", pl.get("name") or t, {
                "input": pl.get("input") or pl.get("arguments") or pl.get("action") or ""}
        elif t in ("message", "reasoning", "custom_tool_call_output", "function_call_output"):
            # The prompt, the model's own words, and what each tool handed back.
            for s in _strings({k: v for k, v in pl.items() if k in ("content", "summary", "output")}):
                yield "text", stem, s
    elif kind == "event_msg" and pl.get("type") == "item_completed":
        item = pl.get("item") if isinstance(pl.get("item"), dict) else {}
        if item.get("type") == "CommandExecution":
            cmd = item.get("command")
            if isinstance(cmd, list):
                cmd = cmd[-1] if cmd else ""
            yield "nested", "Bash", {"command": cmd if isinstance(cmd, str) else ""}
        elif item.get("type") == "ImageView":
            path = item.get("path") if isinstance(item.get("path"), str) else ""
            yield "nested", "ImageView", {"path": path.removeprefix("file://")}
    elif kind == "compacted":
        # What a context compaction kept, which the model reads again afterwards.
        for s in _strings(pl):
            yield "text", stem, s


def _antigravity_line(j: dict, stem: str):
    """Antigravity transcript_full.jsonl: tool calls hang off PLANNER_RESPONSE rows."""
    for key in ("content", "thinking"):
        v = j.get(key)
        if isinstance(v, str) and v:
            yield "text", stem, v
    for call in j.get("tool_calls") or []:
        if not isinstance(call, dict):
            continue
        args = call.get("args") if isinstance(call.get("args"), dict) else {}
        name = call.get("name")
        if name == "run_command":
            yield "tool", "Bash", {"command": args.get("CommandLine") or ""}
        elif name == "view_file":
            yield "tool", "Read", {"path": args.get("AbsolutePath") or ""}
        elif name == "write_to_file":
            yield "tool", "Write", {"path": args.get("TargetFile") or ""}
        elif name == "find_by_name":
            yield "tool", "Glob", {"path": args.get("SearchDirectory") or "",
                                   "pattern": args.get("Pattern") or ""}
        elif name == "grep_search":
            yield "tool", "Grep", {"path": args.get("SearchPath") or "",
                                   "pattern": args.get("Query") or ""}
        else:
            yield "tool", name or "?", dict(args)


def blocks(paths: list[Path]):
    """Yield (kind, name, payload) for every tool call, nested action and text block.

    Each line is dispatched on its own shape rather than the file being sniffed once, so
    a truncated or mixed file still reads correctly instead of silently yielding nothing.
    """
    for p in paths:
        for line in p.open(errors="replace"):
            try:
                j = json.loads(line)
            except Exception:
                continue
            if not isinstance(j, dict):
                continue
            if "payload" in j and "timestamp" in j:
                if j.get("type") not in CODEX_SESSION_ROWS:
                    UNROUTED[f"codex session row {j.get('type')}"] += 1
                reader = _codex_session_line
            elif isinstance(j.get("item"), dict) or j.get("type") in CODEX_ROWS:
                reader = _codex_line
            elif "tool_calls" in j or j.get("type") in ANTIGRAVITY_ROWS:
                reader = _antigravity_line
            else:
                reader = _claude_line
                if (isinstance(j.get("type"), str) and j["type"].isupper()
                        and not isinstance(j.get("message"), dict)):
                    UNROUTED[j["type"]] += 1
            yield from reader(j, p.stem)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--rollout", required=True, nargs="+", type=Path)
    args = ap.parse_args()
    run_dir = args.run_dir.rstrip("/")

    tools = collections.Counter()
    nested = collections.Counter()
    paths_touched: set[str] = set()
    commands: list[str] = []
    hay: list[str] = []

    for kind, name, payload in blocks(args.rollout):
        if kind == "text":
            hay.append(payload)
            continue
        (tools if kind == "tool" else nested)[name] += 1
        for k in PATH_KEYS:
            v = payload.get(k)
            if isinstance(v, str):
                paths_touched.add(v)
        if name == "Bash" and isinstance(payload.get("command"), str):
            commands.append(payload["command"])
        hay.append(json.dumps(payload))

    text = "\n".join(hay)
    total = sum(tools.values())

    # ---- positive controls: this reader must be able to see the run at all ----
    # --run-dir is where the run happened, which for an in-image arm is the container's
    # /workspace, not wherever the rollout was copied afterwards. Pointing it elsewhere
    # makes this control fail rather than report a clean audit of a run it could not see.
    saw_media = (f"{run_dir}/materials" in text
                 or bool(re.search(r"(^|[^\w/])materials/game\.mp4", text, re.M)))
    spec = Path(__file__).resolve().parent.parent / "task.toml"
    src = spec.read_text() if spec.exists() else ""
    controls = {
        "saw any tool call": total > 0,
        "the dataset-name pattern matches this task's own source":
            (not src) or bool(re.search(LEAKS["the source dataset by name"], src, re.I)),
        "saw a Bash command": bool(commands),
        "saw the run's own media path": saw_media,
        "saw ffmpeg or ffprobe": bool(re.search(r"ffmpeg|ffprobe", text)),
        "every transcript row was routed to a reader that understood it": not UNROUTED,
    }
    failed = [k for k, ok in controls.items() if not ok]
    if failed:
        for k in failed:
            print(f"  CONTROL FAILED  {k}")
        if UNROUTED:
            print(f"  unrouted row types: {dict(UNROUTED)}")
        print("this audit cannot see the run, so its clean result would mean nothing")
        return 2

    # ---- the findings ----
    outside, harness = [], []
    for q in sorted(paths_touched):
        if not q.startswith("/") or q.startswith(run_dir):
            continue
        (harness if HARNESS_SCRATCH.match(q) else outside).append(q)
    net = sum(tools[t] for t in NETWORK_TOOLS)
    hits = {}
    for label, pat in LEAKS.items():
        found = sorted(set(m.group(0) for m in re.finditer(pat, text, re.I)))
        if found:
            hits[label] = found
    cmd_text = "\n".join(commands)
    netcmd = sorted(set(m.group(0) for m in re.finditer(NETWORK_CMD, cmd_text, re.I)))
    if netcmd:
        hits["a network command it actually ran"] = netcmd

    print(f"tool calls: {total} across {len(args.rollout)} rollout file(s)")
    for k, v in tools.most_common():
        print(f"  {k:16s} {v}")
    if nested:
        print("  done inside those calls, scanned below and not counted as turns:")
        for k, v in nested.most_common():
            print(f"    {k:14s} {v}")
    print(f"\ncontrols: {len(controls)} passed, so a zero below is a real zero")
    print(f"network tool calls (WebSearch, WebFetch): {net}")
    print(f"absolute paths touched outside {run_dir}: {len(outside)}")
    for q in outside[:20]:
        print(f"    {q}")
    if harness:
        print(f"  ({len(harness)} more are the agent harness's own runtime state, listed "
              f"below rather than counted against the run)")
        for q in harness[:8]:
            print(f"      {q}")
        if len(harness) > 8:
            print(f"      ... and {len(harness) - 8} more under the same prefixes")
    if hits:
        print("\nSHORTCUT PATTERNS FOUND:")
        for label, found in hits.items():
            print(f"  {label}: {', '.join(found[:8])}")
    else:
        print("shortcut patterns found: none of " + ", ".join(LEAKS)
              + ", and no network command among the "
              + f"{len(commands)} shell commands it ran\n")

    clean = not outside and net == 0 and not hits
    print("VERDICT:", "clean" if clean else "REVIEW REQUIRED")
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
