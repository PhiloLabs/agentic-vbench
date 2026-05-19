#!/usr/bin/env python3
"""Refresh the embedded `_cut_verifier_core.py` in every cut/glitch/disfluency
task's `steps/solve/tests/judge.py`, in place.

Why: `judge.py` is generated at task build time by each `build_*` script,
which inlines a snapshot of `_cut_verifier_core.py` between the markers
`# ---- BEGIN EMBEDDED VERIFIER CORE ----` and `# ---- END EMBEDDED VERIFIER
CORE ----`. When the source verifier picks up a bug fix (e.g., the half-open
interval nudge), the baked copies do not. Rebuilding the whole task would
also regenerate `corrupted.mp4` and may invalidate existing Modal artifacts
under rejudge. This script refreshes only the embedded core — fast, safe,
and leaves the task inputs byte-stable.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CORE = ROOT / "scripts" / "_cut_verifier_core.py"
# v4 tasks live under tasks/repair_v4/<task>; only repair_v4 has baked judges.
TASKS = ROOT / "tasks" / "repair_v4"

BEGIN = "# ---- BEGIN EMBEDDED VERIFIER CORE ----"
END = "# ---- END EMBEDDED VERIFIER CORE ----"


def main() -> int:
    if not CORE.exists():
        print(f"missing source verifier: {CORE}", file=sys.stderr)
        return 1
    src = CORE.read_text()
    src = re.sub(r"^from __future__ import .*\n", "", src, count=1, flags=re.M)

    updated, skipped = 0, 0
    for judge_py in sorted(TASKS.glob("exp-*/steps/solve/tests/judge.py")):
        old = judge_py.read_text()
        if BEGIN not in old or END not in old:
            skipped += 1
            continue
        new = re.sub(
            rf"({re.escape(BEGIN)}\n).*?(\n{re.escape(END)})",
            lambda m: m.group(1) + src + m.group(2),
            old, count=1, flags=re.S,
        )
        if new == old:
            skipped += 1
            continue
        judge_py.write_text(new)
        updated += 1
        print(f"  refreshed: {judge_py.relative_to(ROOT)}")

    print(f"\n{updated} judge.py refreshed, {skipped} skipped (no embedded core or unchanged)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
