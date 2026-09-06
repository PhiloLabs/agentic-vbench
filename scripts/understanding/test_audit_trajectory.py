#!/usr/bin/env python3
"""Regression tests for audit_trajectory.py — the calibration integrity auditor.

Pins the two properties a reviewer relies on:
  1. Every transcript format shipped in calibration/rollouts/ is COUNTED correctly.
     The retained Codex / Claude Code / Antigravity rollouts must yield exactly the
     turn counts recorded in scores.md (112 / 51 / 115 / 98). An earlier version of the
     auditor returned 0 calls for the Codex and Claude formats and still printed PASS.
  2. The auditor FAILS CLOSED: a non-empty trajectory whose format is not recognized
     exits non-zero instead of reporting a vacuous PASS.

Plus two false-positive/negative edges found while fixing (1):
  - a one-record JSONL file must not be mis-read as a document with zero calls;
  - a shell `find ... ! -name 'ground_truth*'` EXCLUDES the answer files and must not
    be flagged as answer-file access, while a real `cat ground_truth.json` must be.

Run:  python3 scripts/understanding/test_audit_trajectory.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDITOR = HERE / "audit_trajectory.py"
ROLLOUTS = (
    HERE.parents[1]
    / "tasks/agentic_vbench_understanding/baddies-smp-pigs-can-fly-command-ledger/calibration/rollouts"
)

# Retained calibration rollouts and the turn counts recorded in calibration/scores.md.
EXPECTED_TURNS = {
    "codex-full.jsonl": 112,
    "opus48-full.jsonl": 51,
    "opus5-full.jsonl": 115,
    "antigravity-full.jsonl": 98,
}


def run(path: Path) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(AUDITOR), str(path)], capture_output=True, text=True
    )
    return proc.returncode, proc.stdout + proc.stderr


def turns(output: str) -> int:
    for line in output.splitlines():
        if "tool-call turns:" in line:
            return int(line.split(":")[1])
    raise AssertionError(f"no turn count in output:\n{output}")


def write(tmp: Path, name: str, *records: dict) -> Path:
    p = tmp / name
    p.write_text("".join(json.dumps(r) + "\n" for r in records))
    return p


def claude(tool: str, **inp) -> dict:
    return {
        "type": "assistant",
        "message": {"role": "assistant",
                    "content": [{"type": "tool_use", "id": "t1", "name": tool, "input": inp}]},
        "session_id": "s",
    }


def codex(command: str) -> dict:
    return {"type": "item.completed",
            "item": {"id": "i1", "type": "command_execution", "command": command,
                     "status": "completed"}}


def main() -> None:
    # 1. Shipped rollouts: exact counts, all clean.
    for name, want in EXPECTED_TURNS.items():
        rc, out = run(ROLLOUTS / name)
        got = turns(out)
        assert got == want, f"{name}: counted {got} tool calls, scores.md records {want}"
        assert rc == 0, f"{name}: expected clean audit (exit 0), got exit {rc}:\n{out}"
        print(f"[ok] {name:24s} {got:>3} tool-call turns, audit clean")

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)

        # 2. Fail closed on a non-empty, unrecognized transcript.
        rc, out = run(write(tmp, "unsupported.jsonl", {"foo": "bar"}, {"hello": "world"}))
        assert rc != 0 and "no recognized tool calls" in out, f"fail-open! exit {rc}:\n{out}"
        print("[ok] unrecognized non-empty transcript -> non-zero exit, no PASS")

        # 3. One-record JSONL (valid JSON as a whole) still parses its tool call.
        rc, out = run(write(tmp, "one.jsonl", claude("Bash", command="ls")))
        assert rc == 0 and turns(out) == 1, f"one-record JSONL mis-parsed:\n{out}"
        print("[ok] one-record JSONL is not mistaken for an empty document")

        # 4. Genuine answer-file access is caught, in both formats.
        rc, out = run(write(tmp, "claude_bad.jsonl",
                            claude("Read", file_path="/tests/ground_truth.json")))
        assert rc == 1 and "answer-file" in out, f"Claude ground_truth read not caught:\n{out}"
        rc, out = run(write(tmp, "codex_bad.jsonl",
                            codex("/bin/bash -lc 'cat /tests/ground_truth.json'")))
        assert rc == 1 and "answer-file" in out, f"Codex ground_truth read not caught:\n{out}"
        print("[ok] Read/cat of ground_truth.json -> FAIL (Claude and Codex)")

        # 5. Excluding the answer files in a find is not accessing them — even when
        #    the pattern is wrapped in shell quote-juggling, as in the real Codex run.
        rc, out = run(write(tmp, "codex_excl.jsonl",
                            codex("find . -type f ! -name '\"'ground_truth*' \"'! -name '\"'oracle*' \"' -print")))
        assert rc == 0, f"find exclusion flagged as answer access:\n{out}"
        print("[ok] `find ... ! -name 'ground_truth*'` is not flagged as access")

    print("\nALL CHECKS PASSED — auditor counts every shipped format and fails closed.")


if __name__ == "__main__":
    main()
