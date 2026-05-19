#!/usr/bin/env python3
"""Create the `ameddserM/agentic_vbench_assembly` HF dataset + emit local task dirs.

Curated 18-task subset of the existing `ameddserM/video_edit_bench_task_7_3`
benchmark. Source task_ids are picked to match the assembly task_ids in
`Anonymous47621123/AgenticVBench_100` (we only borrowed the index list, not
the prompts or details). Renumbered sequentially 1–18 in the output.

Source schema preserved verbatim — same columns, same prompts, same
`reference_file_urls` (pointing back at the existing `video_edit_bench_task_7`
materials zips; no re-upload).

Run:
    .venv/bin/python scripts/create_agentic_vbench_assembly.py [--overwrite]
                                                               [--no-upload]
                                                               [--no-tasks]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
from pathlib import Path

from datasets import Dataset, load_dataset

REPO_ROOT = Path(__file__).resolve().parent.parent

SRC_DATASET = "ameddserM/video_edit_bench_task_7_3"
DST_DATASET = "ameddserM/agentic_vbench_assembly"

# The 18 source task_7_3 task_ids that match the AgenticVBench_100 assembly
# subset (matched by `correct_assembly_in_slot_order` content). Output order
# becomes the new dataset's sequential 1..18 numbering.
SELECTED_SOURCE_IDS = [1, 2, 4, 5, 6, 7, 9, 10, 11, 12, 13, 14, 15, 18, 19, 20, 22, 24]
assert len(SELECTED_SOURCE_IDS) == 18

TASKS_DIR = REPO_ROOT / "tasks" / "agentic_vbench_assembly"
TASK_PREFIX = "agentic-vbench-assembly-task"

INSTRUCTION_FOOTER = """

---

## Workspace layout

- The candidate clips have been pre-downloaded to `/workspace/materials/`
  (named `1.mp4` through `N.mp4`). Read them from there.
- Use `/workspace/work/` for any intermediate scratch files.
- Use `/workspace/output/` only for the two final deliverables.
- `ffmpeg` and `ffprobe` are available on `PATH`.
"""

TASK_TOML = """\
version = "1.0"

[task]
name = "agentic-vbench/{task_name}"

[metadata]
difficulty = "medium"
category = "video-editing"
tags = ["video-assembly", "agentic-vbench-assembly"]
source = "{dataset} (row task_id={task_id})"

[environment]
build_timeout_sec = 600.0
cpus = 2
memory_mb = 4096
storage_mb = 10240
allow_internet = true

[environment.env]
HF_TOKEN = "${{HF_TOKEN:-}}"

[[steps]]
name = "solve"

[steps.agent]
timeout_sec = 1800.0

[steps.verifier]
timeout_sec = 600.0
"""

DOCKERFILE = """\
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \\
        ffmpeg \\
        unzip \\
        curl \\
        ca-certificates \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
"""

SETUP_SH = """\
#!/bin/bash
# Pre-agent fetch: pulls the per-task materials zip into /workspace/materials/.
set -euo pipefail

MATERIALS_URL="{materials_url}"

mkdir -p /workspace/materials /workspace/output /workspace/work

curl --fail --silent --show-error --location \\
     --retry 5 --retry-delay 3 --retry-connrefused \\
     ${{HF_TOKEN:+-H "Authorization: Bearer $HF_TOKEN"}} \\
     "$MATERIALS_URL" -o /tmp/materials.zip
unzip -q -o /tmp/materials.zip -d /workspace/materials/
rm -f /tmp/materials.zip

mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt

rm -- "$0"
"""

TEST_SH = """\
#!/bin/bash
# Verifier: scores /workspace/output/solution.json against the inline
# CORRECT_PICKS baked into judge.py. Writes 0–1 reward to
# /logs/verifier/reward.json (and reward.txt for legacy readers).
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts

if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

python3 /tests/judge.py \\
        --solution /workspace/output/solution.json \\
        --reward-json /logs/verifier/reward.json \\
        --reward-txt /logs/verifier/reward.txt
"""

JUDGE_PY = '''\
#!/usr/bin/env python3
"""Score one agentic_vbench_assembly solution. Ports the per-slot exact-pick
verifier from video-agent-runner/verifiers/video_assembly/runner.py
(no S3, stdlib only).

Reward = fraction of slots whose `source` matches the baked-in CORRECT_PICKS,
in slot order.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CORRECT_PICKS = {correct_picks!r}


def _normalize(src) -> str:
    """Agent may emit `"3"`, `"3.mp4"`, or `3`; normalize to `"<N>.mp4"`."""
    s = str(src).strip()
    if not s.endswith(".mp4"):
        s = f"{{s}}.mp4"
    return s


def _zero(reason):
    return {{
        "reward": 0.0,
        "details": {{
            "reason": reason,
            "n_slots": len(CORRECT_PICKS),
            "n_correct": 0,
            "pred": [],
            "correct": CORRECT_PICKS,
        }},
    }}


def score(solution_path):
    if not solution_path.exists():
        return _zero(f"solution.json not found at {{solution_path}}")
    try:
        sol = json.loads(solution_path.read_text())
    except json.JSONDecodeError as e:
        return _zero(f"solution.json invalid JSON: {{e}}")

    segments = sol.get("segments")
    if not isinstance(segments, list):
        return _zero("solution.json: segments not a list")

    pred = [_normalize(seg.get("source", "")) for seg in segments]
    n = len(CORRECT_PICKS)
    if len(pred) != n:
        return _zero(f"slot count mismatch: expected {{n}}, got {{len(pred)}}")

    correct_count = sum(1 for i in range(n) if pred[i] == CORRECT_PICKS[i])
    reward = correct_count / n

    return {{
        "reward": reward,
        "details": {{
            "reason": "ok",
            "n_slots": n,
            "n_correct": correct_count,
            "pred": pred,
            "correct": CORRECT_PICKS,
        }},
    }}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--reward-json", required=True, type=Path)
    parser.add_argument("--reward-txt", required=True, type=Path)
    args = parser.parse_args()

    result = score(args.solution)
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps(result, indent=2))
    args.reward_txt.write_text(f"{{result['reward']:.6f}}\\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

SOLVE_SH = '''\
#!/bin/bash
# Oracle: writes the ground-truth solution.json directly.
set -euo pipefail

mkdir -p /workspace/output

python3 - <<'PY'
import json, subprocess
from pathlib import Path

CORRECT = {correct_picks!r}
materials = Path("/workspace/materials")

def duration(p):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(p),
    ]).decode().strip()
    return float(out)

durs = {{c: duration(materials / c) for c in CORRECT}}

t = 0.0
segments = []
for c in CORRECT:
    d = durs[c]
    segments.append({{
        "output": [round(t, 3), round(t + d, 3)],
        "source": c.removesuffix(".mp4"),
        "source_range": [0.0, round(d, 3)],
    }})
    t += d

Path("/workspace/output/solution.json").write_text(
    json.dumps({{"segments": segments}}, indent=2)
)

list_file = Path("/workspace/work/concat.txt")
list_file.parent.mkdir(parents=True, exist_ok=True)
list_file.write_text(
    "\\n".join(f"file '{{materials / c}}'" for c in CORRECT) + "\\n"
)

subprocess.run([
    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file),
    "-c", "copy", "/workspace/output/solution.mp4",
], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
PY

echo "oracle: wrote /workspace/output/solution.json and (best-effort) solution.mp4"
'''


def _materials_url(refs) -> str | None:
    if isinstance(refs, list) and refs:
        v = refs[0]
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            return v.get("url")
    if isinstance(refs, dict):
        return refs.get("url")
    return None


def _write_exec(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def emit_task(task_id: int, prompt: str, materials_url: str,
              correct_picks: list[str], *, overwrite: bool) -> None:
    task_name = f"{TASK_PREFIX}{task_id}"
    task_dir = TASKS_DIR / task_name
    if task_dir.exists():
        if not overwrite:
            print(f"  skip {task_name} (exists)")
            return
        shutil.rmtree(task_dir)

    correct_picks = [str(x) for x in correct_picks]

    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "environment" / "Dockerfile").write_text(DOCKERFILE)
    (task_dir / "task.toml").write_text(
        TASK_TOML.format(task_name=task_name, dataset=DST_DATASET, task_id=task_id)
    )

    step_dir = task_dir / "steps" / "solve"
    step_dir.mkdir(parents=True)
    (step_dir / "instruction.md").write_text(prompt.rstrip() + INSTRUCTION_FOOTER)
    _write_exec(step_dir / "workdir" / "setup.sh",
                SETUP_SH.format(materials_url=materials_url))
    _write_exec(step_dir / "tests" / "test.sh", TEST_SH)
    _write_exec(step_dir / "tests" / "judge.py",
                JUDGE_PY.format(correct_picks=correct_picks))
    _write_exec(step_dir / "solution" / "solve.sh",
                SOLVE_SH.format(correct_picks=correct_picks))

    print(f"  wrote {task_name}")


def build_rows_from_source() -> list[dict]:
    """Bootstrap path: pull 18 selected rows from `video_edit_bench_task_7_3`
    and renumber 1..18. Used once on initial setup before the destination
    dataset exists."""
    print(f"loading {SRC_DATASET} ...")
    src = load_dataset(SRC_DATASET, split="train", token=os.environ.get("HF_TOKEN"))
    by_id = {r["task_id"]: r for r in src}
    rows = []
    for new_id, src_id in enumerate(SELECTED_SOURCE_IDS, start=1):
        if src_id not in by_id:
            print(f"  ! source task_id={src_id} missing in {SRC_DATASET}", file=sys.stderr)
            continue
        r = dict(by_id[src_id])
        r["task_id"] = new_id  # renumbered sequentially 1..18
        rows.append(r)
    print(f"  selected {len(rows)} rows from {len(src)} source rows")
    return rows


def load_rows_from_published() -> list[dict]:
    """Default path post-bootstrap: read the published HF dataset, which is
    now the source of truth (carries any prompt edits made directly on HF)."""
    print(f"loading {DST_DATASET} (source of truth) ...")
    ds = load_dataset(DST_DATASET, split="train",
                      token=os.environ.get("HF_TOKEN"),
                      download_mode="force_redownload")
    print(f"  {len(ds)} rows")
    return [dict(r) for r in ds]


def upload_dataset(rows: list[dict]) -> None:
    print(f"\npushing → {DST_DATASET} (train split, {len(rows)} rows)")
    ds = Dataset.from_list(rows)
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("HF_TOKEN unset; cannot push.", file=sys.stderr)
        sys.exit(1)
    ds.push_to_hub(DST_DATASET, split="train", token=token, private=False)
    print("  ✓ pushed")


def emit_local_tasks(rows: list[dict], *, overwrite: bool) -> None:
    print(f"\nemitting local Harbor task dirs under {TASKS_DIR}")
    n = 0
    for r in rows:
        task_id = int(r["task_id"])
        prompt = r.get("prompt") or ""
        url = _materials_url(r.get("reference_file_urls"))
        correct = r.get("correct_assembly_in_slot_order") or []
        if not (prompt and url and correct):
            print(f"  skip task_id={task_id}: missing prompt/url/correct_picks",
                  file=sys.stderr)
            continue
        emit_task(task_id, prompt, url, correct, overwrite=overwrite)
        n += 1
    print(f"  ✓ {n} task dirs")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--overwrite", action="store_true",
                    help="Replace existing local task dirs (HF upload is always overwrite).")
    ap.add_argument("--bootstrap", action="store_true",
                    help="One-time setup: read from the source `video_edit_bench_task_7_3`, "
                         "transform + renumber, and push to the destination HF dataset. "
                         "Without this flag, the script reads from the destination dataset "
                         "(the source of truth post-bootstrap) and only re-emits local task dirs.")
    ap.add_argument("--no-upload", action="store_true",
                    help="With --bootstrap, skip the HF dataset push.")
    ap.add_argument("--no-tasks", action="store_true",
                    help="Skip the local task-dir emit; only push the HF dataset.")
    args = ap.parse_args()

    if args.bootstrap:
        rows = build_rows_from_source()
        if not args.no_upload:
            upload_dataset(rows)
        else:
            print("(skipping HF upload)")
    else:
        rows = load_rows_from_published()

    if not args.no_tasks:
        emit_local_tasks(rows, overwrite=args.overwrite)
    else:
        print("(skipping local task emit)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
