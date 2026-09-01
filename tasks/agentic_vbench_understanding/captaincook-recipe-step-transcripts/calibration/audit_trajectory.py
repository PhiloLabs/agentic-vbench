#!/usr/bin/env python3
"""Read a calibration rollout and answer: did this agent cheat, and did it work hard.

The family README asks for the raw trajectory and for a turn count, and warns that a
score is only worth what an audit of the trajectory says it is. This reads the rollout
rather than the summary: it counts real tool calls, lists every filesystem path the agent
touched, and looks for the three ways this particular task could be shortcut, which are
reading the answer key, reaching the network, and recalling the source dataset.

    python3 calibration/audit_trajectory.py --run-dir /abs/run --rollout a.jsonl [b.jsonl ...]

Every check carries a positive control. A pattern search that returns zero on a file it
was never able to read returns the same zero as a clean run, so the script asserts that
it can find things that must be there before it reports the absence of things that must
not be. If a control fails the script exits non-zero and reports nothing else.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

# Ways this task could be shortcut rather than solved.
LEAKS = {
    "answer key or grader": r"judge\.py|GROUND_TRUTH|step-derived|build_gt|solve\.sh|VOCABULARY\s*=",
    # The source of THIS task, not of the sibling one. An audit that greps for the wrong
    # dataset name reports every run clean no matter what the agent said, so the names
    # here are checked against the shipped task.toml by the control below.
    "the source dataset by name": r"captain\s?cook|captaincook4d|utdallas|data\.bris",
    "the task package": r"avb_repo|agentic_vbench|provenance/|steps/solve",
}
# Searched only in shell commands the agent actually ran. The prompt itself says the
# words "curl" and "wget" while forbidding them, so a whole-transcript search for these
# hits the rule that bans them and reports every clean run as dirty.
NETWORK_CMD = r"\bcurl\b|\bwget\b|\bgit\s+clone\b|\bpip\s+install\b|\bnc\b|\bssh\b"
NETWORK_TOOLS = {"WebSearch", "WebFetch"}

# The one path outside the run directory that is not a finding. Running an agent harness
# on a laptop rather than inside the task image means the harness parks the stdout of the
# agent's own background commands in its own tasks/ directory, and the agent reads its own
# output back from there. Those files hold nothing but what that agent just printed. The
# container has no such directory. Anything else outside the run directory is reported.
# Paths that belong to the agent's own harness rather than to this task. Two shapes, and
# both are named rather than pattern-matched loosely, because widening this list is the one
# edit here that makes the audit report LESS. The first is the Claude Code harness's task
# output on the host. The second is where the Antigravity CLI keeps its session state
# inside the container: its brain directory, its scratch directory, its logs and its own
# binary. An agent writing there is doing its own bookkeeping, and the container has no
# equivalent of a task directory at those paths.
HARNESS_SCRATCH = re.compile(
    r"^/private/tmp/claude-[^/]+/[^/]+/[^/]+/tasks/[\w-]+\.output$"
    r"|^/root/\.gemini/antigravity-cli/"
    r"|^/root/\.agy/"
    r"|^/root/\.local/bin/agy$")
PATH_KEYS = ("file_path", "path", "notebook_path")
# Row types no reader claimed. Filled by blocks(), read by the controls in main().
UNROUTED: collections.Counter = collections.Counter()
# Antigravity row types that carry a turn, used to route a line to its reader.
# ERROR_MESSAGE is in here for a reason worth stating: it is how the Antigravity harness
# records that its own stream dropped and the agent was told to continue. A row type that
# no reader claims falls through to the Claude reader, finds no `message`, and yields
# nothing, so an interrupted run would read exactly like an uninterrupted one. The
# unrouted-rows control below fails on any type not listed here.
ANTIGRAVITY_ROWS = {"PLANNER_RESPONSE", "USER_INPUT", "CHECKPOINT", "GENERIC",
                    "SYSTEM_MESSAGE", "ERROR_MESSAGE"}
# Codex event types that carry no `item`, so the shape alone does not identify them.
CODEX_ROWS = {"thread.started", "turn.started", "turn.completed", "turn.failed", "error"}


def _claude_line(j: dict, stem: str):
    """Claude Code --output-format stream-json: tool calls live in message.content[]."""
    msg = j.get("message")
    if not isinstance(msg, dict):
        # Not a Claude line after all. Codex writes top-level {"type": "error",
        # "message": "<string>"} events, and routing one of those here used to raise
        # AttributeError and take the whole audit down with it.
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
                # `thinking` too, not only `text`. On the sibling Ego-Exo4D task the one
                # finding that mattered, an agent naming the source dataset from a frame
                # grid, appeared in private thinking and never in a tool call. The
                # Antigravity reader has always read its thinking field; leaving it out
                # here made this harness the only one whose reasoning went unsearched.
                yield "text", stem, b.get("text") or b.get("thinking") or ""
            elif b.get("type") == "tool_result":
                # What the tools handed back. Dropping these searched only what the agent
                # said and typed, never what it read, while the Codex reader passes
                # aggregated_output and the Antigravity reader passes content through. A
                # leak that arrives in a tool result would have been invisible on this
                # harness alone.
                c = b.get("content")
                if isinstance(c, str):
                    yield "text", stem, c
                elif isinstance(c, list):
                    for sub in c:
                        if isinstance(sub, dict) and isinstance(sub.get("text"), str):
                            yield "text", stem, sub["text"]


def _codex_line(j: dict, stem: str):  # noqa: C901
    """Codex exec --json: one event per lifecycle item.

    Only `item.completed` is read. Codex announces each item twice, once started and
    once completed, and counting both would double every tool call in the turn count
    the family gate reads. Shell commands arrive as `command_execution` and are mapped
    onto Bash so the same command and network checks apply to both harnesses; writes
    arrive as `file_change` and are mapped onto Write, one event per changed path.
    """
    if j.get("type") in CODEX_ROWS:
        # Transport and lifecycle events. They carry no tool call, but their text is
        # kept so that a run interrupted by reconnects or a failed turn shows up in the
        # audit rather than reading as a clean run that simply stopped early.
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


def _antigravity_line(j: dict, stem: str):
    """Antigravity transcript_full.jsonl: tool calls hang off PLANNER_RESPONSE rows.

    Its tool names are mapped onto the names the checks below already know, so the same
    command, path and network rules apply to all three harnesses: run_command is Bash,
    view_file is Read, write_to_file is Write. Search tools keep their own names and
    contribute the directory they searched, because searching outside the working
    directory is itself the thing the prompt's stay-inside rule forbids.
    """
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
    """Yield (kind, name, payload) for every tool call and every text block.

    Two harnesses write two different stream formats, and a reader that understands only
    one of them reports an empty, clean-looking run for the other. Each line is dispatched
    on its own shape rather than the file being sniffed once, so a truncated or mixed file
    still reads correctly instead of silently yielding nothing.
    """
    for p in paths:
        for line in p.open(errors="replace"):
            try:
                j = json.loads(line)
            except Exception:
                continue
            if not isinstance(j, dict):
                continue
            if isinstance(j.get("item"), dict) or j.get("type") in CODEX_ROWS:
                reader = _codex_line
            elif "tool_calls" in j or j.get("type") in ANTIGRAVITY_ROWS:
                reader = _antigravity_line
            else:
                reader = _claude_line
                # A row whose shape matches no reader is dropped silently, which makes an
                # unread run look like a clean one. Antigravity rows are identified by an
                # upper-case `type`, so one that reaches the Claude reader carrying no
                # `message` is a routing miss, not a Claude row. Report it, do not guess.
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
    paths_touched: set[str] = set()
    commands: list[str] = []
    hay: list[str] = []

    for kind, name, payload in blocks(args.rollout):
        if kind == "text":
            hay.append(payload)
            continue
        tools[name] += 1
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
    # The media control accepts the relative form too. A harness given the run directory
    # as its working directory (codex takes --cd) reaches the clips as `materials/A.mp4`,
    # so demanding the absolute path would fail the control on a run that plainly did
    # watch the videos, and a failed control blocks the whole audit.
    # The letter range comes from the shipped key, not from a literal. Copied from the
    # sibling task it was a stale `[A-Q]` against a corpus that runs to V, which still
    # passed on `materials/A.mp4` and so would never have announced itself.
    key = json.loads((Path(__file__).resolve().parent.parent
                      / "provenance" / "step-derived.json").read_text())
    last = sorted(v["letter"] for v in key["videos"])[-1]
    # --run-dir is the directory the run happened in, which for an in-image arm is the
    # container's /workspace and not wherever the rollout file was copied to afterwards.
    # Pointing this at the host copy makes both this control and the out-of-bounds path
    # check meaningless, and the control is what catches that: it fails rather than
    # reporting a clean audit of a run it could not see. Loosening the pattern instead
    # was tried and reverted, because a control that is easier to satisfy is a control
    # that catches less.
    saw_media = (f"{run_dir}/materials" in text
                 or bool(re.search(rf"(^|[^\w/])materials/[A-{last}]\.mp4", text, re.M)))
    # The dataset-name pattern is the one check that silently becomes a no-op when this
    # file is copied to a task with a different source, so it is tested against the task
    # it is actually auditing rather than trusted.
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
