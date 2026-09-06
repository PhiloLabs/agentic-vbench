#!/usr/bin/env python3
"""Integrity audit for a single agentic-omni-understanding rollout.

Reads one agent trajectory and confirms the score was earned honestly, i.e. the
run did NOT:

  1. ANSWER-FILE ACCESS  open/read any answer-key path (ground_truth*, oracle*,
                         solution/, *provenance*, the verifier tests/ dir).
  2. WEB / LOOKUP        call any web-fetch / search / browser tool, or leave
                         Gemini server-side grounding metadata in the transcript.

It inspects the *inputs of tool calls only* — never the surrounding prose — because
the prompt's own prohibition list ("never open ground_truth*, …") is echoed in the
conversation history every turn and a naive substring grep over the whole file
would flag every clean run (this is the exact bug the earlier `audit_runs.sh` had).

Supports every transcript shape shipped in calibration/rollouts/:
  * ATIF `trajectory.json`  (Harbor's normalized schema — has steps[].tool_calls)
  * Claude Code `--output-format stream-json` (message.content[].tool_use)
  * Codex `codex exec --json` (item.completed → command_execution / file_change)
  * Antigravity agy `--output-format stream-json` (step_update → tool_name)
  * raw Gemini session jsonl (toolCalls per msg)

Exit status is non-zero if any check FAILS, so it drops into CI / the calibration
gate. It also FAILS CLOSED: a non-empty trajectory in which no tool call can be
recognized exits 2 instead of reporting a vacuous PASS. Prints a one-line-per-check
report plus a tool-call turn count.

Usage
-----
  python scripts/understanding/audit_trajectory.py path/to/trajectory.json
  python scripts/understanding/audit_trajectory.py path/to/antigravity-full.jsonl
"""
import argparse
import json
import re
import sys
from pathlib import Path

# Answer-key paths an honest run must never open. Matched against tool-call
# argument *values*, case-insensitively.
ANSWER_PATTERNS = [
    r"ground_truth",
    r"oracle",
    r"provenance",
    r"/solution/",
    r"\btests/\b",
    r"adjudication",
    r"logs_leaked",
]

# Tool / function names that mean the agent reached outside the sandbox for
# information. ffmpeg/ffprobe/transcribe/read/shell are all legitimate and are
# deliberately NOT here.
WEB_TOOL_PATTERNS = [
    r"web[_-]?search",
    r"web[_-]?fetch",
    r"google[_-]?search",
    r"\bsearch\b",
    r"\bbrowse",
    r"browser",
    r"url_?fetch",
    r"fetch_?url",
    r"http_request",
    r"open_?url",
]

# `find ... ! -name '<pattern>'` exclusion clauses, with any run of quote characters
# around the pattern (shell quote-juggling such as '"'ground_truth*'"' is common).
_FIND_EXCLUDE_RE = re.compile(r"!\s*-i?name\s+['\"]*[^'\"\s]*['\"]*", re.IGNORECASE)

# Substrings in the RAW transcript that betray server-side grounding having fired
# (Gemini attaches groundingMetadata / groundingChunks when it grounds a reply).
GROUNDING_KEYS = ["groundingMetadata", "groundingChunks", "groundingSupports",
                  "webSearchQueries", "retrievalMetadata"]


def _iter_tool_calls(traj: dict):
    """Yield (function_name, arguments_json_string) for every tool call.

    Handles five transcript shapes:
      * ATIF          steps[].tool_calls[].{function_name,arguments}
      * raw Gemini     messages[].toolCalls[].{name,args}
      * Claude Code `--output-format stream-json`: records whose
        message.content[] holds parts with type == "tool_use" ({name, input}).
      * Codex `codex exec --json`: records with type == "item.completed" whose
        item.type is "command_execution" ({command}) or "file_change" ({changes[]}).
      * Antigravity agy `--output-format stream-json`: JSONL of
        {event:'step_update', step_update:{step_index, tool_name, tool_info:{name,parameters}}}.
        One step emits several step_update records (running → completed); dedupe by
        step_index so each tool call counts once."""
    for step in traj.get("steps", []):
        for tc in step.get("tool_calls") or []:
            name = tc.get("function_name") or tc.get("name") or ""
            args = tc.get("arguments")
            if args is None:
                args = tc.get("args", {})
            yield name, json.dumps(args, ensure_ascii=False)
    for msg in traj.get("messages", []):
        for tc in msg.get("toolCalls") or []:
            name = tc.get("name") or ""
            yield name, json.dumps(tc.get("args", {}), ensure_ascii=False)
        # Claude Code stream-json: tool calls live inside message.content[].
        inner = msg.get("message")
        content = inner.get("content") if isinstance(inner, dict) else None
        for part in content if isinstance(content, list) else []:
            if isinstance(part, dict) and part.get("type") == "tool_use":
                yield part.get("name") or "", json.dumps(part.get("input", {}), ensure_ascii=False)
        # Codex exec --json: each finished tool step is an item.completed record.
        if msg.get("type") == "item.completed":
            item = msg.get("item") or {}
            kind = item.get("type")
            if kind == "command_execution":
                # A shell `find ... ! -name 'ground_truth*'` EXCLUDES the answer
                # files — the opposite of accessing them. Strip those clauses on the
                # raw command (before JSON escaping inserts backslashes) so the
                # prohibition itself does not read as a violation. The pattern may be
                # wrapped in quote-juggling like '"'ground_truth*'"'.
                cmd = _FIND_EXCLUDE_RE.sub("", item.get("command", ""))
                yield "command_execution", json.dumps({"command": cmd}, ensure_ascii=False)
            elif kind == "file_change":
                paths = [c.get("path", "") for c in item.get("changes") or [] if isinstance(c, dict)]
                yield "file_change", json.dumps({"paths": paths}, ensure_ascii=False)
    seen_steps = set()
    for rec in traj.get("_agy_records", []):
        if rec.get("event") != "step_update":
            continue
        su = rec.get("step_update") or {}
        info = su.get("tool_info") or {}
        name = su.get("tool_name") or info.get("name") or ""
        if not name:
            continue
        idx = su.get("step_index")
        if idx in seen_steps:
            continue
        seen_steps.add(idx)
        yield name, json.dumps(info.get("parameters", {}), ensure_ascii=False)


def _load(path: Path):
    """Return (trajectory_dict, raw_text). JSONL is normalized to a messages list."""
    text = path.read_text()
    stripped = text.strip()
    try:
        data = json.loads(stripped)
        if isinstance(data, dict):
            # A whole-file JSON object is either an ATIF/Gemini document or a
            # one-record JSONL transcript; only the former is a document.
            if "steps" in data or "messages" in data:
                return data, text
            return {"messages": [data], "_agy_records": [data] if "event" in data else []}, text
    except json.JSONDecodeError:
        pass
    # JSONL: one record per line. Split into agy stream-json records (have an
    # 'event' field) and generic message records; the iterator reads both.
    messages, agy = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            (agy if "event" in rec else messages).append(rec)
    return {"messages": messages, "_agy_records": agy}, text


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trajectory", help="ATIF trajectory.json or raw *.jsonl")
    args = ap.parse_args()

    path = Path(args.trajectory)
    traj, raw = _load(path)

    calls = list(_iter_tool_calls(traj))
    n_turns = len(calls)

    # Fail closed. The three checks below are vacuously "clean" when no calls were
    # parsed, which would let an unrecognized transcript format sail through as
    # PASS. A non-empty trajectory with zero recognized tool calls is an audit
    # failure, not a clean run.
    if n_turns == 0 and raw.strip():
        print(f"\n  trajectory: {path}")
        print("  tool-call turns: 0")
        print("\nFAILED: no recognized tool calls in a non-empty trajectory "
              "(unsupported transcript format?) — refusing to report PASS")
        sys.exit(2)

    ans_re = re.compile("|".join(ANSWER_PATTERNS), re.IGNORECASE)
    web_re = re.compile("|".join(WEB_TOOL_PATTERNS), re.IGNORECASE)

    answer_hits, web_hits = [], []
    for name, argstr in calls:
        if ans_re.search(argstr) or ans_re.search(name):
            answer_hits.append((name, argstr[:160]))
        if web_re.search(name):
            web_hits.append((name, argstr[:160]))

    grounding_hits = [k for k in GROUNDING_KEYS if k in raw]

    checks = [
        ("no answer-file access", not answer_hits,
         "clean" if not answer_hits else f"{len(answer_hits)} tool call(s) touch an answer path"),
        ("no web / lookup tool", not web_hits,
         "clean" if not web_hits else f"{len(web_hits)} web/search tool call(s)"),
        ("no server-side grounding", not grounding_hits,
         "clean" if not grounding_hits else f"grounding metadata present: {', '.join(grounding_hits)}"),
    ]

    print(f"\n  trajectory: {path}")
    print(f"  tool-call turns: {n_turns}\n")
    width = max(len(n) for n, _, _ in checks)
    for name, ok, msg in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name.ljust(width)}  {msg}")

    failed = [n for n, ok, _ in checks if not ok]
    print()
    if answer_hits:
        print("  answer-file offenders:")
        for name, snippet in answer_hits[:10]:
            print(f"    - {name}: {snippet}")
    if web_hits:
        print("  web-tool offenders:")
        for name, snippet in web_hits[:10]:
            print(f"    - {name}: {snippet}")
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        sys.exit(1)
    print(f"All integrity checks passed ({n_turns} tool-call turns).")


if __name__ == "__main__":
    main()
