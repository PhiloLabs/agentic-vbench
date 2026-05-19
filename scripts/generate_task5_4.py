#!/usr/bin/env python3
"""Generate one Harbor task dir per row in the task5_4 HF dataset.

Reads `ameddserM/video_edit_bench_task_5_4`, emits
`tasks/video-edit-bench-task-5-4-task<N>/` for each row using the Phase 1
layout as the template. Three per-task substitutions:

  - `MATERIALS_URL`  → setup.sh
  - `CORRECT_ORDER`  → judge.py (as a Python list literal)
  - `prompt` text    → instruction.md (with a fixed workspace-layout footer)

Everything else (Dockerfile, task.toml shape, test.sh, solve.sh shape) is
constant across instances and the same as the Phase 1 hand-authored task.

Run:
    source .venv/bin/activate
    python scripts/generate_task5_4.py
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
from pathlib import Path

from datasets import load_dataset

DATASET = "ameddserM/video_edit_bench_task_5_4"
SPLIT = "train"
REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks" / "task5_4"
TASK_PREFIX = "video-edit-bench-task-5-4-task"

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
tags = ["video-ordering", "video-edit-bench", "task-5-4"]
source = "{dataset} (row task_id={task_id})"

[environment]
build_timeout_sec = 600.0
cpus = 2
memory_mb = 4096
storage_mb = 10240
allow_internet = true

# HF_TOKEN is plumbed in for materials hosted in gated HF datasets (e.g.
# the _5_3 variant referenced by task_id=22 and task_id=30). Harbor resolves
# ${{HF_TOKEN}} from the host's environment at trial start; the suite remains
# runnable for public-only materials when HF_TOKEN is unset.
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
# Runs in the container before the agent starts (Harbor multi-step setup hook).
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

# Leave no trace of setup.sh in WORKDIR.
rm -- "$0"
"""

TEST_SH = """\
#!/bin/bash
# Verifier: scores /workspace/output/solution.json against the inline
# CORRECT_ORDER baked into judge.py. Writes 0–1 reward to
# /logs/verifier/reward.json (and reward.txt for legacy readers).
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts

# Republish rollout outputs (solution.json + solution.mp4) into the
# bind-mounted /logs/artifacts so the host keeps them after sandbox teardown.
# Best-effort: an absent /workspace/output/ should not fail verification.
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
"""Score one task5_4 solution. Ports the three metrics from
video-agent-runner/verifiers/video_order/runner.py (no S3, stdlib only).

Composite reward = 0.4*(1-nd) + 0.3*lis + 0.3*adj in [0,1].
"""
from __future__ import annotations

import argparse
import json
import sys
from bisect import bisect_left
from pathlib import Path

CORRECT_ORDER = {correct_order!r}


def metric_nd(pred, correct):
    pred_pos = {{c: i for i, c in enumerate(pred)}}
    correct_pos = {{c: i for i, c in enumerate(correct)}}
    n = len(correct)
    total = sum(abs(pred_pos[c] - correct_pos[c]) for c in correct_pos)
    max_total = (n * n) // 2
    return total / max_total if max_total else 0.0


def metric_lis(pred, correct):
    rank = {{c: i for i, c in enumerate(correct)}}
    seq = [rank[c] for c in pred if c in rank]
    if not seq:
        return 0.0
    tails = []
    for x in seq:
        i = bisect_left(tails, x)
        if i == len(tails):
            tails.append(x)
        else:
            tails[i] = x
    return len(tails) / len(pred)


def metric_adj(pred, correct):
    if len(correct) <= 1:
        return 1.0
    pred_pos = {{c: i for i, c in enumerate(pred)}}
    caught = 0
    for i in range(len(correct) - 1):
        a, b = correct[i], correct[i + 1]
        if pred_pos.get(b, -2) - pred_pos.get(a, -1) == 1:
            caught += 1
    return caught / (len(correct) - 1)


def _zero(reason):
    return {{
        "reward": 0.0,
        "details": {{
            "reason": reason,
            "nd_score": 0.0,
            "lis_score": 0.0,
            "adj_score": 0.0,
            "strict_match": 0.0,
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

    pred = [str(seg.get("source", "")) for seg in segments]
    if sorted(pred) != sorted(CORRECT_ORDER):
        return _zero(
            f"slot set mismatch: expected {{sorted(CORRECT_ORDER)}}, got {{sorted(pred)}}"
        )

    nd = metric_nd(pred, CORRECT_ORDER)
    lis = metric_lis(pred, CORRECT_ORDER)
    adj = metric_adj(pred, CORRECT_ORDER)
    strict = 1.0 if pred == CORRECT_ORDER else 0.0
    nd_score = 1.0 - nd
    final = 0.4 * nd_score + 0.3 * lis + 0.3 * adj

    return {{
        "reward": final,
        "details": {{
            "reason": "ok",
            "nd_score": nd_score,
            "lis_score": lis,
            "adj_score": adj,
            "strict_match": strict,
            "pred": pred,
            "correct": CORRECT_ORDER,
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
# Oracle: writes the ground-truth solution.json (and a concat solution.mp4)
# directly. Used with `-a oracle` to confirm the verifier returns ≈1.0.
set -euo pipefail

mkdir -p /workspace/output

python3 - <<'PY'
import json, subprocess
from pathlib import Path

CORRECT = {correct_order!r}
materials = Path("/workspace/materials")

def duration(p):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(p),
    ]).decode().strip()
    return float(out)

durs = {{c: duration(materials / f"{{c}}.mp4") for c in CORRECT}}

t = 0.0
segments = []
for c in CORRECT:
    d = durs[c]
    segments.append({{
        "output": [round(t, 3), round(t + d, 3)],
        "source": c,
        "source_range": [0.0, round(d, 3)],
    }})
    t += d

Path("/workspace/output/solution.json").write_text(
    json.dumps({{"segments": segments}}, indent=2)
)

list_file = Path("/workspace/work/concat.txt")
list_file.parent.mkdir(parents=True, exist_ok=True)
list_file.write_text("\\n".join(f"file '{{materials / f'{{c}}.mp4'}}'" for c in CORRECT) + "\\n")

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


def emit_task(task_id, prompt, materials_url, correct_order, *, overwrite):
    task_name = f"{TASK_PREFIX}{task_id}"
    task_dir = TASKS_DIR / task_name
    if task_dir.exists():
        if not overwrite:
            print(f"  skip {task_name} (exists)")
            return
        shutil.rmtree(task_dir)

    correct_order = [str(x) for x in correct_order]

    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "environment" / "Dockerfile").write_text(DOCKERFILE)
    (task_dir / "task.toml").write_text(
        TASK_TOML.format(task_name=task_name, dataset=DATASET, task_id=task_id)
    )

    step_dir = task_dir / "steps" / "solve"
    step_dir.mkdir(parents=True)
    (step_dir / "instruction.md").write_text(prompt.rstrip() + INSTRUCTION_FOOTER)
    _write_exec(step_dir / "workdir" / "setup.sh",
                SETUP_SH.format(materials_url=materials_url))
    _write_exec(step_dir / "tests" / "test.sh", TEST_SH)
    _write_exec(step_dir / "tests" / "judge.py",
                JUDGE_PY.format(correct_order=correct_order))
    _write_exec(step_dir / "solution" / "solve.sh",
                SOLVE_SH.format(correct_order=correct_order))

    print(f"  wrote {task_name}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--overwrite", action="store_true",
                   help="Replace existing task dirs (default: skip).")
    p.add_argument("--task-id", action="append", type=int, default=None,
                   help="Generate only specific task_id(s).")
    args = p.parse_args()

    print(f"loading {DATASET} [{SPLIT}]...")
    ds = load_dataset(DATASET, split=SPLIT, token=os.environ.get("HF_TOKEN"))
    print(f"  {len(ds)} rows; columns: {ds.column_names}")

    n_written = 0
    for row in ds:
        task_id = row["task_id"]
        if args.task_id and int(task_id) not in args.task_id:
            continue
        prompt = row.get("prompt") or ""
        url = _materials_url(row.get("reference_file_urls"))
        correct = row.get("correct_order") or []
        if not (prompt and url and correct):
            print(f"  skip task_id={task_id}: missing prompt/url/correct_order",
                  file=sys.stderr)
            continue
        emit_task(task_id, prompt, url, correct, overwrite=args.overwrite)
        n_written += 1

    print(f"\ndone: {n_written} task dirs under {TASKS_DIR}")


if __name__ == "__main__":
    main()
