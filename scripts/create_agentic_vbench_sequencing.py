#!/usr/bin/env python3
"""Create the `ameddserM/agentic_vbench_sequencing` HF dataset + emit local task dirs.

A 31-task video-ordering benchmark mixing two upstream sources:

  - All 22 of our curated `task5_5` set (from the local `tasks/task5_5/` dirs,
    originally generated from a local `~/Downloads/sequencing_batch2` bundle).
  - 9 picks from the upstream `ameddserM/video_edit_bench_task_5_4`, chosen
    by the AgenticVBench_100 sequencing-subset index list
    `[24, 1, 28, 10, 6, 2, 9, 19, 3]`. (We only borrowed the index list, not
    the prompts — those come verbatim from `video_edit_bench_task_5_4`.)

Sequential task_id renumbering: 1..22 = task5_5 entries (preserved order),
23..31 = task5_4 picks (in the user-given index order).

Schema mirrors `video_edit_bench_task_5_4`:
  task_id, prompt, reference_file_urls, correct_order, n_slots, provenance

Run:
    .venv/bin/python scripts/create_agentic_vbench_sequencing.py --bootstrap
    .venv/bin/python scripts/create_agentic_vbench_sequencing.py --overwrite
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import sys
from pathlib import Path

from datasets import Dataset, load_dataset

REPO_ROOT = Path(__file__).resolve().parent.parent

SRC_T5_4_DATASET = "ameddserM/video_edit_bench_task_5_4"
LOCAL_T5_5_TASKS = REPO_ROOT / "tasks" / "task5_5"
DST_DATASET = "ameddserM/agentic_vbench_sequencing"

# AgenticVBench_100 sequencing-subset indices (1-based within the sequencing
# subset). Empirically these map 1:1 to `video_edit_bench_task_5_4` task_ids
# via a +1 offset (verified by matching `correct_order` content).
USER_INDICES = [24, 1, 28, 10, 6, 2, 9, 19, 3]
T5_4_PICK_IDS = [idx + 1 for idx in USER_INDICES]   # → [25, 2, 29, 11, 7, 3, 10, 20, 4]

TASKS_DIR = REPO_ROOT / "tasks" / "agentic_vbench_sequencing"
TASK_PREFIX = "agentic-vbench-sequencing-task"

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
tags = ["video-ordering", "agentic-vbench-sequencing"]
source = "{dataset} (row task_id={task_id}, upstream={provenance})"

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
"""Score one agentic_vbench_sequencing solution. Same composite as
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
# Oracle: writes the ground-truth solution.json directly.
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
list_file.write_text(
    "\\n".join(f"file '{{materials / f'{{c}}.mp4'}}'" for c in CORRECT) + "\\n"
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


def parse_t5_5_task_dir(dir_path: Path) -> dict:
    """Extract a HF-row-shaped dict from a local task5_5 task dir."""
    instr_text = (dir_path / "steps" / "solve" / "instruction.md").read_text()
    # Strip the workspace-layout footer that emit_task appends.
    marker = "\n\n---\n\n## Workspace layout"
    if marker in instr_text:
        prompt = instr_text[: instr_text.index(marker)].rstrip()
    else:
        prompt = instr_text.rstrip()

    judge_text = (dir_path / "steps" / "solve" / "tests" / "judge.py").read_text()
    m = re.search(r"CORRECT_ORDER\s*=\s*(\[[^\]]+\])", judge_text)
    correct_order = eval(m.group(1))      # safe — we wrote this list ourselves

    setup_text = (dir_path / "steps" / "solve" / "workdir" / "setup.sh").read_text()
    m = re.search(r'MATERIALS_URL="([^"]+)"', setup_text)
    materials_url = m.group(1)

    return {
        "prompt": prompt,
        "correct_order": correct_order,
        "reference_file_urls": [materials_url],
        "n_slots": len(correct_order),
        "provenance": f"task5_5: {dir_path.name}",
    }


def emit_task(task_id: int, prompt: str, materials_url: str,
              correct_order: list[str], provenance: str, *, overwrite: bool) -> None:
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
    # TOML basic-string can't carry literal `"` or `\` — escape defensively.
    provenance_toml = provenance.replace("\\", "\\\\").replace('"', "'")
    (task_dir / "task.toml").write_text(
        TASK_TOML.format(task_name=task_name, dataset=DST_DATASET,
                         task_id=task_id, provenance=provenance_toml)
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

    print(f"  wrote {task_name}  (n_slots={len(correct_order)}, src={provenance})")


def build_rows_from_sources() -> list[dict]:
    """Bootstrap: load task5_5 (local) + 9 task5_4 picks (HF), renumber 1..31."""
    rows: list[dict] = []

    # task5_5 → new task_id 1..22 (preserve existing order)
    t5_5_dirs = sorted(LOCAL_T5_5_TASKS.glob("video-edit-bench-task-5-5-task*"),
                       key=lambda d: int(d.name.rsplit("task", 1)[-1]))
    print(f"loading {len(t5_5_dirs)} task5_5 tasks from {LOCAL_T5_5_TASKS} ...")
    for new_id, d in enumerate(t5_5_dirs, start=1):
        r = parse_t5_5_task_dir(d)
        r["task_id"] = new_id
        rows.append(r)

    # task5_4 picks → new task_id 23..31 (in user-given AgenticVBench index order)
    print(f"loading {len(T5_4_PICK_IDS)} task5_4 picks from {SRC_T5_4_DATASET} ...")
    t5_4 = load_dataset(SRC_T5_4_DATASET, split="train",
                        token=os.environ.get("HF_TOKEN"))
    by_id = {r["task_id"]: r for r in t5_4}
    next_id = len(rows) + 1
    for offset, src_id in enumerate(T5_4_PICK_IDS):
        if src_id not in by_id:
            print(f"  ! task5_4 task_id={src_id} missing", file=sys.stderr)
            continue
        r = dict(by_id[src_id])
        r["task_id"] = next_id + offset
        # The upstream `provenance` is a JSON-encoded dict; keep it human-readable
        # (TOML string-safe — no embedded quotes) instead of re-serialising it.
        r["provenance"] = (f"task5_4 task_id={src_id} "
                           f"(AgenticVBench_100 sequencing idx {USER_INDICES[offset]})")
        rows.append(r)

    # Normalize column set (everything has the same keys)
    keys = ["task_id", "prompt", "reference_file_urls",
            "correct_order", "n_slots", "provenance"]
    rows = [{k: r.get(k) for k in keys} for r in rows]
    print(f"  total: {len(rows)} rows (task_id 1..{len(rows)})")
    return rows


def load_rows_from_published() -> list[dict]:
    """Post-bootstrap: read the published HF dataset (source of truth for
    any prompt edits made directly on HF)."""
    print(f"loading {DST_DATASET} ...")
    ds = load_dataset(DST_DATASET, split="train",
                      token=os.environ.get("HF_TOKEN"),
                      download_mode="force_redownload")
    print(f"  {len(ds)} rows")
    return [dict(r) for r in ds]


def upload_dataset(rows: list[dict]) -> None:
    print(f"\npushing → {DST_DATASET} (train split, {len(rows)} rows)")
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("HF_TOKEN unset; cannot push.", file=sys.stderr)
        sys.exit(1)
    Dataset.from_list(rows).push_to_hub(DST_DATASET, split="train",
                                        token=token, private=False)
    print("  ✓ pushed")


def emit_local_tasks(rows: list[dict], *, overwrite: bool) -> None:
    print(f"\nemitting local Harbor task dirs under {TASKS_DIR}")
    n = 0
    for r in rows:
        task_id = int(r["task_id"])
        prompt = r.get("prompt") or ""
        url = _materials_url(r.get("reference_file_urls"))
        correct = r.get("correct_order") or []
        provenance = r.get("provenance") or "unknown"
        if not (prompt and url and correct):
            print(f"  skip task_id={task_id}: missing prompt/url/correct_order",
                  file=sys.stderr)
            continue
        emit_task(task_id, prompt, url, correct, provenance, overwrite=overwrite)
        n += 1
    print(f"  ✓ {n} task dirs")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--overwrite", action="store_true",
                    help="Replace existing local task dirs.")
    ap.add_argument("--bootstrap", action="store_true",
                    help="One-time setup: load task5_5 (local) + task5_4 picks (HF), "
                         "merge, renumber 1..31, push to the destination HF dataset. "
                         "Without this flag, reads from the destination dataset "
                         "(the source of truth post-bootstrap) and only re-emits local task dirs.")
    ap.add_argument("--no-upload", action="store_true",
                    help="With --bootstrap, skip the HF push.")
    ap.add_argument("--no-tasks", action="store_true",
                    help="Skip the local task-dir emit; only push the HF dataset.")
    args = ap.parse_args()

    if args.bootstrap:
        rows = build_rows_from_sources()
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
