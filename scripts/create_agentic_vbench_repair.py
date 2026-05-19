#!/usr/bin/env python3
"""Migrate the agentic_vbench_repair family from "materials in git" to
Method 1 (runtime fetch from HF).

For each repair task:
  1. Bundle the agent-facing input files (workdir/ minus setup.sh) and the
     verifier-only golden + GT files (tests/ minus test.sh, judge.py) into
     a single zip with two top-level dirs: `input/` and `golden/`.
  2. Upload the zip to HF: `ameddserM/agentic_vbench_repair/materials/<task_id>.zip`.
  3. Rewrite setup.sh, test.sh, solve.sh to curl the zip at runtime instead
     of relying on files committed to git.
  4. Delete the binary inputs/goldens from the local task dir (scripts kept).

Also pushes a metadata HF dataset `ameddserM/agentic_vbench_repair` mirroring
the agentic_vbench_{assembly,sequencing} pattern: one row per task with
prompt + reference_file_urls + a few useful metadata fields.

Run:
    .venv/bin/python scripts/create_agentic_vbench_repair.py --bootstrap \
        [--task-id exp-codec-restore-task01] [--no-upload] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import sys
import zipfile
from pathlib import Path

from datasets import Dataset

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks" / "agentic_vbench_repair"
DIST_DIR = REPO_ROOT / "dist" / "agentic_vbench_repair_materials"

DST_DATASET = "ameddserM/agentic_vbench_repair"
HF_URL_TEMPLATE = (
    "https://huggingface.co/datasets/{dataset}/resolve/main/materials/{task_id}.zip"
)

SCRIPTS_KEEP = {"setup.sh", "test.sh", "judge.py", "solve.sh"}

# Per-task: (family, oracle_pattern, oracle_args)
# oracle_pattern controls how solve.sh stages its output:
#   - "cp_golden":   cp golden/<src> → /workspace/output/<dst>
#   - "cp_golden_sr": same, plus write /workspace/output/output.json with start/end frames from gt_shot.json
#   - "ffmpeg":      keep existing ffmpeg-based solve.sh (it uses baked-in GT and re-encodes from input)
TASK_META = {
    # audio
    "exp-codec-restore-task01":           ("audio", "cp_golden", {"src": "clean.wav", "dst": "enhanced.wav"}),
    "exp-dereverb-task01":                ("audio", "cp_golden", {"src": "clean.wav", "dst": "enhanced.wav"}),
    "exp-dns-denoise-task01":             ("audio", "cp_golden", {"src": "clean.wav", "dst": "enhanced.wav"}),
    "exp-declip-task01":                  ("audio", "cp_golden", {"src": "clean.wav", "dst": "enhanced.wav"}),
    "exp-voicebank-denoise-task01":       ("audio", "cp_golden", {"src": "clean.wav", "dst": "enhanced.wav"}),
    # color
    "exp-color-shot-visit-korea-task01":  ("color_shot", "cp_golden", {"src": "original.mp4", "dst": "output.mp4"}),
    "exp-color-shot-gobelins-task01":     ("color_shot", "cp_golden", {"src": "original.mp4", "dst": "output.mp4"}),
    "exp-color-shot-v3-s1-task01":        ("color_shot", "cp_golden", {"src": "original.mp4", "dst": "output.mp4"}),
    # deblur
    "exp-deblur-motion-f1-task01":        ("deblur", "cp_golden", {"src": "clean.mp4", "dst": "output.mp4"}),
    "exp-deblur-gaussian-mkbhd-task01":   ("deblur", "cp_golden", {"src": "clean.mp4", "dst": "output.mp4"}),
    # sr
    "exp-sr-2x-shot-task01":              ("sr", "cp_golden_sr", {"src": "original.mp4", "dst": "output.mp4"}),
    "exp-sr-4x-shot-task01":              ("sr", "cp_golden_sr", {"src": "original.mp4", "dst": "output.mp4"}),
    # swap
    "exp-swap-car-task01":                ("swap", "cp_golden", {"src": "original.mp4", "dst": "output.mp4"}),
    "exp-swap-product-task01":            ("swap", "cp_golden", {"src": "original.mp4", "dst": "output.mp4"}),
    # glitch — oracle uses ffmpeg-select with baked GT; just keep solve.sh's ffmpeg pattern (unchanged).
    "exp-glitch-dup-short-task01":        ("glitch", "ffmpeg", {}),
    "exp-glitch-dup-long-task01":         ("glitch", "ffmpeg", {}),
    # content-cut — same ffmpeg pattern
    "exp-content-cut-mkbhd-task01":       ("cut", "ffmpeg", {}),
    "exp-content-cut-wsj-task01":         ("cut", "ffmpeg", {}),
    # disfluency
    "exp-disfluency-interview-3-task01":  ("disfluency", "ffmpeg", {}),
    "exp-disfluency-interview-4-task01":  ("disfluency", "ffmpeg", {}),
}


# ── Template strings ────────────────────────────────────────────────────────

SETUP_SH_TEMPLATE = """\
#!/bin/bash
# Pre-agent fetch: download the per-task materials zip and stage only the
# agent-facing inputs into /workspace/materials/. The verifier-only golden
# stays in the zip and is re-fetched by test.sh.
set -euo pipefail

MATERIALS_URL="{materials_url}"

mkdir -p /workspace/materials /workspace/output /workspace/work

curl --fail --silent --show-error --location \\
     --retry 5 --retry-delay 3 --retry-connrefused \\
     ${{HF_TOKEN:+-H "Authorization: Bearer $HF_TOKEN"}} \\
     "$MATERIALS_URL" -o /tmp/materials.zip

unzip -q -j -o /tmp/materials.zip 'input/*' -d /workspace/materials/
rm -f /tmp/materials.zip

mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt

# Leave no trace of setup.sh in WORKDIR.
rm -- "$0"
"""

TEST_SH_TEMPLATE = """\
#!/bin/bash
# Verifier: download the per-task materials zip again to extract golden
# references into /tests/, then run judge.py. The golden never lived in
# the agent's container.
set -euo pipefail

MATERIALS_URL="{materials_url}"

mkdir -p /logs/verifier /logs/artifacts /tests

# Republish whatever the agent left under /workspace/output/.
if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

curl --fail --silent --show-error --location \\
     --retry 5 --retry-delay 3 --retry-connrefused \\
     ${{HF_TOKEN:+-H "Authorization: Bearer $HF_TOKEN"}} \\
     "$MATERIALS_URL" -o /tmp/materials.zip
unzip -q -j -o /tmp/materials.zip 'golden/*' -d /tests/
rm -f /tmp/materials.zip

{verifier_invocation}
"""

SOLVE_SH_CP_TEMPLATE = """\
#!/bin/bash
# Oracle: download the per-task materials zip and cp the bundled golden
# straight to the agent-output path. Ceiling-proof.
set -euo pipefail

MATERIALS_URL="{materials_url}"

mkdir -p /workspace/output

curl --fail --silent --show-error --location \\
     --retry 5 --retry-delay 3 --retry-connrefused \\
     ${{HF_TOKEN:+-H "Authorization: Bearer $HF_TOKEN"}} \\
     "$MATERIALS_URL" -o /tmp/materials.zip
unzip -q -j -o /tmp/materials.zip 'golden/{src}' -d /tmp/golden/
cp /tmp/golden/{src} /workspace/output/{dst}
rm -rf /tmp/golden /tmp/materials.zip

echo "oracle: copied golden/{src} → /workspace/output/{dst}"
"""

SOLVE_SH_SR_TEMPLATE = """\
#!/bin/bash
# Oracle (SR): cp golden mp4 + emit output.json with GT start/end frames.
set -euo pipefail

MATERIALS_URL="{materials_url}"

mkdir -p /workspace/output

curl --fail --silent --show-error --location \\
     --retry 5 --retry-delay 3 --retry-connrefused \\
     ${{HF_TOKEN:+-H "Authorization: Bearer $HF_TOKEN"}} \\
     "$MATERIALS_URL" -o /tmp/materials.zip
unzip -q -j -o /tmp/materials.zip 'golden/*' -d /tmp/golden/

cp /tmp/golden/{src} /workspace/output/{dst}
cat > /workspace/output/output.json <<'EOF'
{{"start_frame": {start_frame}, "end_frame": {end_frame}}}
EOF

rm -rf /tmp/golden /tmp/materials.zip
echo "oracle: copied golden/{src} → /workspace/output/{dst} + output.json"
"""


# ── Helpers ────────────────────────────────────────────────────────────────

def _write_exec(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _collect_input_files(task_dir: Path) -> list[Path]:
    """workdir/* minus setup.sh."""
    workdir = task_dir / "steps" / "solve" / "workdir"
    return sorted(p for p in workdir.iterdir()
                  if p.is_file() and p.name not in SCRIPTS_KEEP)


def _collect_golden_files(task_dir: Path) -> list[Path]:
    """tests/* minus test.sh, judge.py."""
    tests = task_dir / "steps" / "solve" / "tests"
    return sorted(p for p in tests.iterdir()
                  if p.is_file() and p.name not in SCRIPTS_KEEP)


def _build_zip(task_id: str, task_dir: Path, *, dry_run: bool) -> Path:
    out_zip = DIST_DIR / f"{task_id}.zip"
    if dry_run:
        return out_zip
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    input_files = _collect_input_files(task_dir)
    golden_files = _collect_golden_files(task_dir)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_STORED) as zf:
        for p in input_files:
            zf.write(p, arcname=f"input/{p.name}")
        for p in golden_files:
            zf.write(p, arcname=f"golden/{p.name}")
    return out_zip


def _extract_existing_setup_invocation(task_dir: Path) -> str | None:
    """Pull the original test.sh's `python3 /tests/judge.py ...` block,
    plus any preceding `pip install` lines (the judge dependencies)."""
    test_sh = (task_dir / "steps" / "solve" / "tests" / "test.sh").read_text()
    # Capture from the first `python3 /tests/judge.py` or `pip install` line
    # to the end (skip the head boilerplate we rewrite).
    lines = test_sh.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip().startswith("pip install") or "judge.py" in line:
            start = i
            break
    if start is None:
        return None
    return "\n".join(lines[start:]).strip() + "\n"


def _read_gt_shot_frames(task_dir: Path) -> tuple[int, int]:
    """For SR tasks, read start_frame and end_frame from gt_shot.json."""
    gt = json.loads((task_dir / "steps" / "solve" / "tests" / "gt_shot.json").read_text())
    return int(gt["start_frame"]), int(gt["end_frame"])


def _read_task_prompt(task_dir: Path) -> str:
    """Pull the instruction.md (the agent's prompt) from the task dir."""
    return (task_dir / "steps" / "solve" / "instruction.md").read_text()


def _read_corruption(task_dir: Path) -> str:
    """Pull `corruption = ...` from task.toml if present (audio tasks have it)."""
    toml_text = (task_dir / "task.toml").read_text()
    m = re.search(r'^corruption\s*=\s*"([^"]+)"', toml_text, re.M)
    return m.group(1) if m else ""


def patch_dockerfile(task_dir: Path, *, dry_run: bool) -> bool:
    """Method 1 needs `unzip` + `curl` in the container. The original v4
    Dockerfiles ship with neither (materials were git-tracked). Inject a
    small idempotent RUN line if either tool is missing."""
    docker_p = task_dir / "environment" / "Dockerfile"
    text = docker_p.read_text()
    needs_unzip = "unzip" not in text
    needs_curl = "curl" not in text
    if not (needs_unzip or needs_curl):
        return False
    pkgs = " ".join([p for p, need in [("unzip", needs_unzip), ("curl", needs_curl),
                                       ("ca-certificates", needs_curl)] if need])
    add_line = ("RUN apt-get update && apt-get install -y --no-install-recommends "
                f"{pkgs} && rm -rf /var/lib/apt/lists/*\n")
    # Insert after the first existing RUN apt-get block, otherwise after FROM.
    if "RUN apt-get" in text:
        lines = text.splitlines(keepends=True)
        # Find the END of the first apt-get RUN block (the line containing
        # `rm -rf /var/lib/apt/lists/*` or the next non-continuation line).
        i = next(j for j, l in enumerate(lines) if "RUN apt-get" in l)
        # Walk forward to the end of the block (last continuation line).
        while i + 1 < len(lines) and (
              lines[i].rstrip().endswith("\\") or "rm -rf /var/lib/apt/lists" in lines[i]):
            if "rm -rf /var/lib/apt/lists" in lines[i]:
                i += 1
                break
            i += 1
        lines.insert(i, add_line)
        new_text = "".join(lines)
    else:
        # Insert right after FROM
        lines = text.splitlines(keepends=True)
        from_idx = next(j for j, l in enumerate(lines) if l.startswith("FROM"))
        lines.insert(from_idx + 1, add_line)
        new_text = "".join(lines)
    if dry_run:
        print(f"    would patch Dockerfile: +{pkgs}")
        return True
    docker_p.write_text(new_text)
    return True


def rewrite_scripts(task_id: str, task_dir: Path, materials_url: str, *,
                    dry_run: bool) -> None:
    family, oracle_pattern, oracle_args = TASK_META[task_id]
    solve_dir = task_dir / "steps" / "solve"

    # setup.sh — always replace with the curl-stage-input flow.
    new_setup = SETUP_SH_TEMPLATE.format(materials_url=materials_url)

    # test.sh — preserve the verifier invocation (pip install + python3 judge.py)
    # from the current test.sh; only rewrite the header that fetches goldens.
    verifier_invocation = _extract_existing_setup_invocation(task_dir) or ""
    new_test = TEST_SH_TEMPLATE.format(materials_url=materials_url,
                                       verifier_invocation=verifier_invocation)

    # solve.sh — depends on oracle pattern.
    if oracle_pattern == "cp_golden":
        new_solve = SOLVE_SH_CP_TEMPLATE.format(
            materials_url=materials_url, **oracle_args)
    elif oracle_pattern == "cp_golden_sr":
        sf, ef = _read_gt_shot_frames(task_dir)
        new_solve = SOLVE_SH_SR_TEMPLATE.format(
            materials_url=materials_url, start_frame=sf, end_frame=ef,
            **oracle_args)
    elif oracle_pattern == "ffmpeg":
        # Keep the existing solve.sh — it bakes in the GT and re-encodes from
        # /workspace/materials/<input>. setup.sh now stages input from the zip,
        # so the existing solve.sh works unmodified.
        new_solve = None
    else:
        raise ValueError(f"unknown oracle_pattern: {oracle_pattern}")

    if dry_run:
        print(f"  {task_id}: would rewrite setup.sh + test.sh"
              + (f" + solve.sh" if new_solve else " (solve.sh unchanged)"))
        return

    _write_exec(solve_dir / "workdir" / "setup.sh", new_setup)
    _write_exec(solve_dir / "tests" / "test.sh", new_test)
    if new_solve is not None:
        _write_exec(solve_dir / "solution" / "solve.sh", new_solve)


def strip_binaries(task_id: str, task_dir: Path, *, dry_run: bool) -> int:
    """Delete every non-script file from workdir/, tests/, solution/ — they're
    now on HF. Scripts (setup.sh, test.sh, judge.py, solve.sh) stay."""
    n = 0
    for sub in ("workdir", "tests", "solution"):
        d = task_dir / "steps" / "solve" / sub
        if not d.is_dir():
            continue
        for p in list(d.iterdir()):
            if p.is_file() and p.name not in SCRIPTS_KEEP:
                if dry_run:
                    print(f"    would rm {p.relative_to(task_dir)}")
                else:
                    p.unlink()
                n += 1
            elif p.is_dir():
                # Walk one level for mask.png nested in subdir, etc. — repair tasks don't have these today
                for q in list(p.rglob("*")):
                    if q.is_file() and q.name not in SCRIPTS_KEEP:
                        if dry_run:
                            print(f"    would rm {q.relative_to(task_dir)}")
                        else:
                            q.unlink()
                        n += 1
    return n


def migrate_task(task_id: str, *, dry_run: bool, skip_zip: bool) -> dict:
    task_dir = TASKS_DIR / task_id
    family, _, _ = TASK_META[task_id]
    materials_url = HF_URL_TEMPLATE.format(dataset=DST_DATASET, task_id=task_id)

    print(f"\n=== {task_id} ({family}) ===")
    input_files = _collect_input_files(task_dir)
    golden_files = _collect_golden_files(task_dir)
    print(f"  input  ({len(input_files)}):  {[p.name for p in input_files]}")
    print(f"  golden ({len(golden_files)}): {[p.name for p in golden_files]}")

    if not skip_zip:
        zip_path = _build_zip(task_id, task_dir, dry_run=dry_run)
        size_mb = (zip_path.stat().st_size / 1024 / 1024) if zip_path.exists() else 0
        print(f"  zip:    {zip_path}  ({size_mb:.1f} MB)" if size_mb else f"  zip: (dry run)")

    patched = patch_dockerfile(task_dir, dry_run=dry_run)
    if patched and not dry_run:
        print(f"  patched Dockerfile (added unzip/curl)")
    rewrite_scripts(task_id, task_dir, materials_url, dry_run=dry_run)
    removed = strip_binaries(task_id, task_dir, dry_run=dry_run)
    print(f"  {'would remove' if dry_run else 'removed'} {removed} binary file(s)")

    return {
        "task_id": task_id,
        "family": family,
        "prompt": _read_task_prompt(task_dir),
        "reference_file_urls": [materials_url],
        "corruption": _read_corruption(task_dir),
    }


def upload_zips() -> None:
    """Upload dist/agentic_vbench_repair_materials/*.zip to HF as materials/<id>.zip."""
    from huggingface_hub import upload_folder
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("HF_TOKEN unset; cannot push.", file=sys.stderr)
        sys.exit(1)
    print(f"\nuploading {len(list(DIST_DIR.glob('*.zip')))} zips → {DST_DATASET}/materials/")
    upload_folder(
        folder_path=str(DIST_DIR),
        path_in_repo="materials",
        repo_id=DST_DATASET,
        repo_type="dataset",
        token=token,
        commit_message="add agentic_vbench_repair materials zips",
    )
    print("  ✓ pushed")


def upload_dataset(rows: list[dict]) -> None:
    print(f"\npushing metadata → {DST_DATASET} (train split, {len(rows)} rows)")
    token = os.environ.get("HF_TOKEN")
    Dataset.from_list(rows).push_to_hub(DST_DATASET, split="train",
                                        token=token, private=False)
    print("  ✓ pushed")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-id", action="append", default=None,
                    help="Limit to specific task_id(s) (default = all 20).")
    ap.add_argument("--bootstrap", action="store_true",
                    help="Build zips, upload to HF, push metadata dataset, "
                         "and migrate local task dirs to Method 1.")
    ap.add_argument("--no-upload", action="store_true",
                    help="Skip the HF uploads (zips + dataset).")
    ap.add_argument("--no-tasks", action="store_true",
                    help="Skip rewriting local task dirs.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Plan only — no file writes, no HF uploads.")
    ap.add_argument("--skip-zip", action="store_true",
                    help="Skip rebuilding the per-task zips (assume already built).")
    args = ap.parse_args()

    targets = args.task_id or list(TASK_META.keys())
    print(f"migrating {len(targets)} repair task(s) to Method 1 (dry_run={args.dry_run})")

    rows = []
    for task_id in targets:
        if task_id not in TASK_META:
            print(f"  ! unknown task_id: {task_id}", file=sys.stderr)
            continue
        row = migrate_task(task_id, dry_run=args.dry_run, skip_zip=args.skip_zip)
        rows.append(row)

    if args.dry_run:
        print("\n(dry run — no uploads, no file writes)")
        return 0

    if args.bootstrap and not args.no_upload:
        upload_zips()
        upload_dataset(rows)
    elif not args.bootstrap:
        print("\n(no --bootstrap → skipping HF uploads)")

    print(f"\ndone: {len(rows)} task(s) processed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
