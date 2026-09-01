#!/usr/bin/env python3
"""Run the oracle that ships in the image and grade what it actually writes.

    python3 provenance/test_oracle_integration.py

Review round 2 found the oracle scoring 0.0: `make_task_files.py` built each row from
video, id, t_start and t_end, and the error field the contract now requires was never
emitted. Nothing caught it, because every check that claimed to grade "the oracle" built
its own error-aware oracle out of the key in memory. Those two objects came apart and the
checks kept passing on the one that was never shipped.

So this file grades the shipped artifact and nothing else. It executes
`steps/solve/solution/solve.sh` unmodified, reads back the `solution.json` that run
wrote, and requires reward 1.0. Parsing the SEQUENCE literal out of the script would
repeat the original mistake one level down: it would prove the table is right while
saying nothing about whether the script writes it to the right place in the right shape.

A test that cannot fail is not evidence, so the same execution path is run a second time
against a copy of the script with the error field stripped, and that run must NOT reach
1.0. If the environment cannot execute the script at all the test fails; it never reports
success on a run that did not happen.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TASK = Path(__file__).resolve().parent.parent
SOLVE = TASK / "steps" / "solve" / "solution" / "solve.sh"
OUTPUT = "/workspace/output/solution.json"
IMAGE = "python:3.12-slim"

sys.path.insert(0, str(TASK / "steps" / "solve" / "tests"))
import judge  # noqa: E402


def _native_possible() -> bool:
    """True when /workspace/output can be created here, as it can inside the image."""
    try:
        Path("/workspace/output").mkdir(parents=True, exist_ok=True)
        return os.access("/workspace/output", os.W_OK)
    except (OSError, PermissionError):
        return False


def _have_docker() -> bool:
    try:
        return subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"],
                              capture_output=True, timeout=30).returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def run_script(script: Path, how: str) -> list:
    """Execute `script` and return the entries of the solution.json it wrote."""
    if how == "native":
        subprocess.run(["bash", str(script)], check=True, capture_output=True)
        raw = Path(OUTPUT).read_text()
    else:
        # The script is mounted read-only and run by its own path, so what executes is
        # the file on disk rather than a transcription of it.
        r = subprocess.run(
            ["docker", "run", "--rm", "-v", f"{script.parent}:/oracle:ro", IMAGE,
             "bash", "-c", f"bash /oracle/{script.name} >/dev/null && cat {OUTPUT}"],
            check=True, capture_output=True, text=True, timeout=600)
        raw = r.stdout
    doc = json.loads(raw)
    entries = doc["sequence"] if isinstance(doc, dict) else doc
    assert entries, "the run produced a solution.json with no entries"
    return entries


def main() -> int:
    assert SOLVE.is_file(), f"no oracle at {SOLVE}"
    if _native_possible():
        how = "native"
    elif _have_docker():
        how = "docker"
    else:
        print("FAIL: cannot execute the oracle here. /workspace is not writable and no "
              "Docker daemon is reachable, so this check cannot run. It is not passing.",
              file=sys.stderr)
        return 2
    print(f"executing the shipped oracle ({how})")

    entries = run_script(SOLVE, how)
    n_key = sum(len(v) for v in judge.GROUND_TRUTH.values())
    assert len(entries) == n_key, \
        f"the oracle wrote {len(entries)} entries, the key holds {n_key}"
    missing = [i for i, e in enumerate(entries) if "error" not in e]
    assert not missing, (
        f"{len(missing)} of the oracle's rows carry no error field; this is the exact "
        f"drift review round 2 found")
    r = judge.grade(entries)
    assert r["f1"] == 1.0, (
        f"the oracle that ships in the image scores {r['f1']}, not 1.0 "
        f"({r['true_positives']} true positives out of {n_key}; "
        f"{r['label_and_order_only_matches']} rows are right on label, order and timing)")
    print(f"  ok  {len(entries)} entries written, graded by the shipped judge, "
          f"reward {r['f1']}")

    # Control. The same path, on a copy whose error field has been removed, must fall
    # short of 1.0. Without this the assertion above would pass just as happily on a
    # judge that had stopped scoring the field.
    with tempfile.TemporaryDirectory() as td:
        broken = Path(td) / "solve.sh"
        text = SOLVE.read_text()
        stripped = re.sub(r',\s*"error":\s*"[^"]*"', "", text)
        assert stripped != text, "the control could not strip the error field"
        broken.write_text(stripped)
        broken.chmod(0o755)
        ctl = run_script(broken, how)
        assert len(ctl) == n_key, f"the control wrote {len(ctl)} entries"
        assert all("error" not in e for e in ctl), "the control still carries the field"
        c = judge.grade(ctl)
        assert c["f1"] < 1.0, \
            "the control scored 1.0 without the error field, so this test cannot fail"
        print(f"  ok  control: the same script without the error field scores {c['f1']}, "
              f"with {c['label_and_order_only_matches']} rows still right on label, "
              f"order and timing")

    print("the oracle in the image writes a submission that scores 1.0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
