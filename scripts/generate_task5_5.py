#!/usr/bin/env python3
"""Generate one Harbor task dir per video in sequencing_batch2.

Mirrors `generate_task5_4.py` exactly — same task.toml / Dockerfile / setup.sh
/ judge.py / solve.sh templates — but reads its inputs from a local
`~/Downloads/sequencing_batch2` bundle instead of an HF dataset, and uses
the L1 prompt level (single-line story description) for every task.

For each of the 22 videos:
  - emits `tasks/video-edit-bench-task-5-5-task<N>/`
  - builds `dist/task5_5_materials/<N>.zip` (clips renamed to `1.mp4`…`N.mp4`
    inside the zip, matching the agent-facing layout).

The setup.sh inside each task dir points at
`https://huggingface.co/datasets/{HF_DATASET}/resolve/main/materials/<N>.zip`.
Upload the built zips to that path before running rollouts (see the script's
final report for the exact `huggingface_hub.upload_folder` invocation).

Run:
    .venv/bin/python scripts/generate_task5_5.py [--overwrite] [--task-id N]
"""
from __future__ import annotations

import argparse
import json
import shutil
import stat
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks" / "task5_5"
TASK_PREFIX = "video-edit-bench-task-5-5-task"

# Source: local bundle the user supplied. Treated as raw input (the same way
# `sources/` is for the v4 suite — not committed, regenerable upstream).
SEQ_BATCH = Path.home() / "Downloads" / "sequencing_batch2"
PROMPT_LEVEL = "L1"

# Where the per-task zips land. Gitignored. Upload these to HF before rollout.
MATERIALS_OUT_DIR = REPO_ROOT / "dist" / "task5_5_materials"

# HF dataset that will host the materials zips. Mirrors the 5_4 convention.
HF_DATASET = "ameddserM/video_edit_bench_task_5_5"

INSTRUCTION_FOOTER = """

---

## Workspace layout

- The candidate clips have been pre-downloaded to `/workspace/materials/`
  (named `1.mp4` through `N.mp4`). Read them from there.
- Use `/workspace/work/` for any intermediate scratch files.
- Use `/workspace/output/` only for the two final deliverables.
- `ffmpeg` and `ffprobe` are available on `PATH`.
"""

# Composed locally from L1's `## Story overview` text + the title parsed from
# the requirement.md header. Path references are rewritten to /workspace/output
# to match the 5_4 instruction.md style.
INSTRUCTION_TEMPLATE = """\
# Video Ordering Task — {title}

You are given **{n_slots} candidate video clips**: {clip_list}.

These clips are the shots of a single chapter from a short film, **renamed and shuffled into a random order**. Each clip appears **exactly once** in the correct ordering — there are no extra clips and no duplicates.

## Your job

Reassemble the clips into the original narrative order described below.

## Story overview

{story_overview}

## Additional notes

- Stay inside this working directory. Don't read, write, or search
  files outside it — no parent directories, no other paths on the
  system.
- Don't try to identify the source film or look it up online.
  Don't search for the original chapter, transcripts, or related
  metadata to compare against the clips — work only from the bytes
  you've been given. (Other web lookups, e.g. tool docs, are fine.)

## What to submit

1. **`/workspace/output/solution.mp4`** — the {n_slots} clips concatenated in the correct narrative order, in this folder. Each clip is used in full, exactly once.
2. **`/workspace/output/solution.json`** — a manifest describing the order you chose.

### `solution.json` format

```json
{{
  "segments": [
    {{"output": [0.0, 7.417], "source": "2", "source_range": [0.0, 7.417]}},
    {{"output": [7.417, 10.917], "source": "6", "source_range": [0.0, 3.500]}}
  ]
}}
```

### Rules

- Exactly **{n_slots} entries**, one per slot, in slot order.
- Each clip number from `"1"` to `"{n_slots}"` must appear **exactly once** as a `source`.
- Intervals are **half-open** `[start, end)` — end is exclusive.
- `output` — time range where this clip appears in `solution.mp4`.
- `source` — clip number as a string (e.g. `"3"` for `3.mp4`).
- `source_range` — portion of the clip used; should be `[0, clip_duration]` (use each clip in full).
- Segments must be **contiguous**: each `output[0]` equals the previous `output[1]`; first starts at `0.0`, last ends at `solution.mp4`'s total duration.

## Done when

Both `/workspace/output/solution.mp4` and `/workspace/output/solution.json` exist.
"""

TASK_TOML = """\
version = "1.0"

[task]
name = "agentic-vbench/{task_name}"

[metadata]
difficulty = "medium"
category = "video-editing"
tags = ["video-ordering", "video-edit-bench", "task-5-5", "prompt-{level}"]
source = "sequencing_batch2/{video_name} (level={level}, rep_01)"

[environment]
build_timeout_sec = 600.0
cpus = 2
memory_mb = 4096
storage_mb = 10240
allow_internet = true

# HF_TOKEN is plumbed in for materials hosted in gated HF datasets. Harbor
# resolves ${{HF_TOKEN}} from the host's environment at trial start.
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
"""Score one task5_5 solution. Same metric as task5_4 (porting
video-agent-runner/verifiers/video_order/runner.py, no S3, stdlib only).

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


def _write_exec(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _parse_l1(req_md: str) -> tuple[str, str]:
    """Extract (title, story_overview) from a batch2 L1 requirement.md."""
    title = ""
    for line in req_md.splitlines():
        if line.startswith("# Video Ordering Task"):
            title = line.split("—", 1)[1].strip() if "—" in line else line[1:].strip()
            break
    # The `## Story overview` paragraph runs until the next `##` heading.
    story = []
    in_story = False
    for line in req_md.splitlines():
        if line.strip() == "## Story overview":
            in_story = True
            continue
        if in_story:
            if line.startswith("## "):
                break
            story.append(line)
    return title, "\n".join(story).strip()


def _build_zip(video_name: str, out_zip: Path) -> int:
    clips_dir = SEQ_BATCH / "runs" / "batch2" / "tasks" / video_name / PROMPT_LEVEL / "rep_01" / "video_clips"
    if not clips_dir.exists():
        raise FileNotFoundError(f"clips dir missing: {clips_dir}")
    clips = sorted(clips_dir.glob("*.mp4"), key=lambda p: int(p.stem))
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_STORED) as zf:
        for clip in clips:
            zf.write(clip, arcname=clip.name)
    return len(clips)


def _clip_list_str(n: int) -> str:
    return ", ".join(f"`{i}.mp4`" for i in range(1, n + 1))


def emit_task(task_id: int, video_name: str, *, overwrite: bool, build_zips: bool) -> None:
    task_name = f"{TASK_PREFIX}{task_id}"
    task_dir = TASKS_DIR / task_name
    if task_dir.exists():
        if not overwrite:
            print(f"  skip {task_name} (exists)")
            return
        shutil.rmtree(task_dir)

    req_path = SEQ_BATCH / "runs" / "batch2" / "tasks" / video_name / PROMPT_LEVEL / "rep_01" / "requirement.md"
    ans_path = SEQ_BATCH / "answer_keys" / "batch2" / video_name / "rep_01.json"
    if not req_path.exists() or not ans_path.exists():
        print(f"  skip {task_name}: missing requirement.md or answer_key", file=sys.stderr)
        return

    answer = json.loads(ans_path.read_text())
    n_slots = int(answer["n_slots"])
    # correct_assembly_in_slot_order: ["4.mp4", "12.mp4", ...] → ["4", "12", ...]
    correct_order = [Path(s).stem for s in answer["correct_assembly_in_slot_order"]]
    assert len(correct_order) == n_slots, f"slot/order count mismatch for {video_name}"

    title, story = _parse_l1(req_path.read_text())
    prompt = INSTRUCTION_TEMPLATE.format(
        title=title or video_name,
        n_slots=n_slots,
        clip_list=_clip_list_str(n_slots),
        story_overview=story,
    )

    materials_url = (
        f"https://huggingface.co/datasets/{HF_DATASET}/resolve/main/materials/{task_id}.zip"
    )

    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "environment" / "Dockerfile").write_text(DOCKERFILE)
    (task_dir / "task.toml").write_text(
        TASK_TOML.format(task_name=task_name, video_name=video_name, level=PROMPT_LEVEL)
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

    if build_zips:
        out_zip = MATERIALS_OUT_DIR / f"{task_id}.zip"
        n = _build_zip(video_name, out_zip)
        size_mb = out_zip.stat().st_size / (1024 * 1024)
        print(f"  wrote {task_name} ({video_name}, n_slots={n_slots}, zip={n} clips, {size_mb:.1f} MB)")
    else:
        print(f"  wrote {task_name} ({video_name}, n_slots={n_slots})")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--overwrite", action="store_true",
                   help="Replace existing task dirs (default: skip).")
    p.add_argument("--task-id", action="append", type=int, default=None,
                   help="Generate only specific task_id(s).")
    p.add_argument("--no-zips", action="store_true",
                   help="Skip building materials zips (only emit task dirs).")
    args = p.parse_args()

    if not SEQ_BATCH.exists():
        print(f"missing source bundle: {SEQ_BATCH}", file=sys.stderr)
        return 1

    inputs_dir = SEQ_BATCH / "inputs"
    video_names = sorted(p.name for p in inputs_dir.iterdir() if p.is_dir())
    print(f"found {len(video_names)} videos under {inputs_dir}")
    print(f"prompt level: {PROMPT_LEVEL}")
    print(f"task dirs    → {TASKS_DIR}")
    print(f"materials    → {MATERIALS_OUT_DIR}")
    print(f"HF dataset   → {HF_DATASET}")
    print()

    n_written = 0
    for task_id, name in enumerate(video_names, start=1):
        if args.task_id and task_id not in args.task_id:
            continue
        emit_task(task_id, name, overwrite=args.overwrite, build_zips=not args.no_zips)
        n_written += 1

    print()
    print(f"done: {n_written} task dirs under {TASKS_DIR}")
    if not args.no_zips:
        print()
        print("To upload materials to HF (one-time):")
        print(f"  huggingface-cli upload {HF_DATASET} {MATERIALS_OUT_DIR} \\")
        print(f"      materials --repo-type=dataset")
        print(f"  # or via the Python API:")
        print(f"  #   from huggingface_hub import upload_folder")
        print(f"  #   upload_folder(folder_path='{MATERIALS_OUT_DIR}',")
        print(f"  #                 path_in_repo='materials', repo_id='{HF_DATASET}',")
        print(f"  #                 repo_type='dataset')")
    return 0


if __name__ == "__main__":
    sys.exit(main())
