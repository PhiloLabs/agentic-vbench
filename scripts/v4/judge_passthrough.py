"""v4 cut/glitch passthrough judges (no math change vs v3).

The v3 cut & glitch verifiers already pin broken=0 and golden=1 by construction:

  - 'Range gate' — number of agent-submitted cut/glitch ranges that match a GT
    range (within tolerance) over the count of GT ranges. Passthrough = no
    submitted ranges = 0/N = 0.0.
  - 'Honesty gate' — reconstructs the expected video (source minus submitted
    ranges) and compares to the agent output with SSIM ≥ 0.95. Passthrough
    survives honesty because expected = source.
  - 'Audio xcorr gate' — same idea, on audio. Passthrough survives.

So the broken-input passthrough always lands at reward = 0 (range gate
denominator). The golden (correct cut-list submission) lands at 1.0
(range gate numerator = denominator).

For v4 we therefore reuse the v3 reward unchanged for these 7 tasks. This
script reads the v3 reward.json from each task's latest claude job and
re-emits it into the v4 per-task store and TSV with `metric=binary_range_f1`.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _framework import (  # noqa: E402
    append_tsv,
    get_task_paths,
    write_v4_result,
    JOBS_DIR,
)


PASSTHROUGH_TASKS = [
    ("exp-glitch-dup-short-task01", "glitch"),
    ("exp-glitch-dup-long-task01", "glitch"),
    ("exp-content-cut-mkbhd-task01", "cut"),
    ("exp-content-cut-wsj-task01", "cut"),
    ("exp-disfluency-interview-3-task01", "cut"),
    ("exp-disfluency-interview-4-task01", "cut"),
    ("exp-disfluency-pitch-meeting-task01", "cut"),
]


def latest_v3_reward(task_id: str) -> float | None:
    """Read the v3 reward.json from the latest job under jobs/cc-<task_id>-*."""
    pattern = f"cc-{task_id}-"
    candidates = []
    for d in JOBS_DIR.iterdir():
        if d.name.startswith(pattern):
            files = list(d.glob("*/steps/solve/verifier/reward.json"))
            for f in files:
                candidates.append((f.stat().st_mtime, f))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    _, latest = candidates[0]
    try:
        d = json.load(open(latest))
        return float(d.get("reward", 0.0))
    except Exception:
        return None


def main(argv: list[str]) -> int:
    print(f"v4 passthrough (binary range-F1): {len(PASSTHROUGH_TASKS)} tasks")
    for tid, family in PASSTHROUGH_TASKS:
        r = latest_v3_reward(tid)
        if r is None:
            print(f"  {tid:42s} no v3 reward found — defaulting to 0.0")
            r = 0.0
        # By construction: broken=0, golden=1. We pass the v3 reward through
        # unchanged because the v3 math is already correctly calibrated.
        details = {
            "metric_primary": "binary_range_f1",
            "rationale": "v3 range-F1 already pins broken=0, golden=1; no v4 change",
            "binary_range_f1": {"broken": 0.0, "golden": 1.0, "claude": r,
                                  "unit": "fraction of GT ranges matched within tolerance"},
        }
        write_v4_result(tid, family, "binary_range_f1", 0.0, 1.0, r, r, r, details)
        append_tsv(tid, family, "binary_range_f1", 0.0, 1.0, r, r, r)
        print(f"  {tid:42s} score={r:.3f}  metric=binary_range_f1  (v3 passthrough)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
