"""Fix the 12 oracle solve.sh files so each one copies the golden reference
into /workspace/output/ instead of doing a passthrough or best-effort algo.

For each task:
  1. Copy `tests/<golden_filename>` into `solution/<golden_filename>`
     (so it ships with the oracle's mount context).
  2. Rewrite `solution/solve.sh` to `cp $HERE/<golden> /workspace/output/<artifact>`.

Result: every oracle now hits 1.0 under v4 by construction.

After running this, the oracle smoke tests need to be re-rolled for the
dashboard to pick up the new oracle artifacts. The fix-script itself does
not invoke Harbor.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

TASKS_DIR = Path(__file__).resolve().parents[2] / "tasks" / "agentic_vbench_repair"

# Map: task_id -> (golden_in_tests, output_artifact_name)
FIXES = {
    # audio family
    "exp-codec-restore-task01":         ("clean.wav", "enhanced.wav"),
    "exp-dereverb-task01":              ("clean.wav", "enhanced.wav"),
    "exp-dns-denoise-task01":           ("clean.wav", "enhanced.wav"),
    "exp-declip-task01":                ("clean.wav", "enhanced.wav"),
    "exp-voicebank-denoise-task01":     ("clean.wav", "enhanced.wav"),
    # color family (golden is `original.mp4`)
    "exp-color-shot-visit-korea-task01":("original.mp4", "output.mp4"),
    "exp-color-shot-gobelins-task01":   ("original.mp4", "output.mp4"),
    "exp-color-shot-v3-s1-task01":      ("original.mp4", "output.mp4"),
    # deblur family (golden is `clean.mp4`)
    "exp-deblur-motion-f1-task01":      ("clean.mp4", "output.mp4"),
    "exp-deblur-gaussian-mkbhd-task01": ("clean.mp4", "output.mp4"),
    # sr family (golden is `original.mp4`)
    "exp-sr-2x-shot-task01":            ("original.mp4", "output.mp4"),
    "exp-sr-4x-shot-task01":            ("original.mp4", "output.mp4"),
    # swap family (golden is `original.mp4`) — v4 swap judge has ±5-frame
    # tolerance, so simple cp gives 1.0
    "exp-swap-car-task01":              ("original.mp4", "output.mp4"),
    "exp-swap-product-task01":          ("original.mp4", "output.mp4"),
}


SOLVE_SH_TEMPLATE = """\
#!/bin/bash
# Oracle: copy the bundled golden reference straight to the output.
# This is the ceiling-proof oracle — it shows the verifier returns 1.0
# when given the correct answer.
set -euo pipefail
mkdir -p /workspace/output
HERE="$(cd "$(dirname "$0")" && pwd)"
cp "$HERE/{golden}" /workspace/output/{artifact}
echo "oracle: copied bundled golden $HERE/{golden} -> /workspace/output/{artifact}"
"""


# A few oracles also need a small companion JSON to satisfy the verifier
# (e.g., sr expects output.json with the GT range; swap needs gt_swap.json).
# We additionally write output.json for the SR family using their gt_shot.json.
SR_EXTRA = """\
import json, sys
from pathlib import Path
HERE = Path(sys.argv[1])
gt = json.loads((HERE.parent / "tests" / "gt_shot.json").read_text())
out = HERE / "output.json"
out.write_text(json.dumps({"start_frame": gt["start_frame"], "end_frame": gt["end_frame"]}, indent=2))
"""


def fix(task_id: str, golden: str, artifact: str, dry_run: bool = False):
    base = TASKS_DIR / task_id / "steps" / "solve"
    tests = base / "tests"
    solution = base / "solution"
    if not solution.exists():
        print(f"  {task_id}: no solution/ dir, skipping")
        return False
    src = tests / golden
    if not src.exists():
        print(f"  {task_id}: golden {src.name} not present in tests/, skipping")
        return False
    dst = solution / golden
    solve_sh = solution / "solve.sh"

    if dry_run:
        print(f"  {task_id}: would cp {src} -> {dst}, rewrite {solve_sh}")
        return True

    # Copy (skip if already up-to-date)
    if not dst.exists() or dst.stat().st_size != src.stat().st_size:
        shutil.copy2(src, dst)
        print(f"  {task_id}: copied {src.name} -> solution/ ({dst.stat().st_size/1024/1024:.2f} MB)")
    else:
        print(f"  {task_id}: solution/{golden} already current")

    # Build solve.sh content
    if task_id.startswith("exp-sr-"):
        # SR oracle needs an output.json with start/end frames too
        gt_shot_path = (tests / "gt_shot.json").read_text()
        import json as _json
        gt = _json.loads(gt_shot_path)
        sh = f"""#!/bin/bash
# Oracle: copy the bundled golden + emit GT shot range JSON.
# Ceiling-proof oracle for SR family.
set -euo pipefail
mkdir -p /workspace/output
HERE="$(cd "$(dirname "$0")" && pwd)"
cp "$HERE/{golden}" /workspace/output/{artifact}
cat > /workspace/output/output.json <<'EOF'
{{"start_frame": {gt["start_frame"]}, "end_frame": {gt["end_frame"]}}}
EOF
echo "oracle: copied bundled golden $HERE/{golden} -> /workspace/output/{artifact}"
"""
    else:
        sh = SOLVE_SH_TEMPLATE.format(golden=golden, artifact=artifact)

    solve_sh.write_text(sh)
    solve_sh.chmod(0o755)
    print(f"  {task_id}: rewrote {solve_sh}")
    return True


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    targets = [a for a in argv[1:] if not a.startswith("--")]
    if not targets:
        targets = list(FIXES.keys())
    print(f"Fixing {len(targets)} oracle solve.sh files (dry_run={dry})")
    n_ok = 0
    for tid in targets:
        if tid not in FIXES:
            print(f"  {tid}: not in FIXES table, skipping")
            continue
        golden, artifact = FIXES[tid]
        if fix(tid, golden, artifact, dry_run=dry):
            n_ok += 1
    print(f"\nDone. {n_ok}/{len(targets)} fixed.")
    if not dry:
        print("\nNext steps:")
        print("  1. Re-roll oracle smoke runs to generate new oracle artifacts.")
        print("  2. Re-run scripts/v4/recompute_oracle.py to score them.")
        print("  3. Rebuild dashboard: scripts/build_site_v4.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
