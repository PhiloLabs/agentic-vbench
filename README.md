# agentic-vbench

A benchmark suite for evaluating AI coding agents on video-related tasks, built on top of [Harbor](https://www.harborframework.com/).

Tasks live in Harbor's task format; Harbor handles agent installation, sandbox orchestration on Modal, concurrency, trial lifecycle, and result collection. This repo focuses on the tasks themselves.

## Status

| Family | Source dataset | Instances generated | Runnable | Integrated |
|---|---|---|---|---|
| `video-edit-bench-task-5-4` (clip ordering) | `ameddserM/video_edit_bench_task_5_4` | 31 | 31 (29 anon + 2 with HF_TOKEN) | ✅ |
| `video-edit-bench-task-7-3` (storyboard assembly) | `ameddserM/video_edit_bench_task_7_3` | 24 | 24 (all gated; requires HF_TOKEN) | ✅ |
| `video-edit-bench-task-6` (video repair) | `ameddserM/video_edit_bench_task_6` | — | — | planned |
| `video-edit-bench-task-4-2` (open-ended editing) | `ameddserM/video_edit_bench_task_4_2` | — | — | planned |

Two task5_4 instances (`task_id` 22 and 30) point at the gated `_5_3` HF dataset. All 24 task7_3 instances point at the gated `_7` HF dataset. Both groups need `HF_TOKEN` to be set on the host that invokes `harbor run` — Harbor's `[environment.env]` block plumbs it into the container. Suite still emits valid task dirs and works for public-only materials if `HF_TOKEN` is unset.

A claude-code (sonnet 4.6) baseline run on Modal at `--n-concurrent 31` completed in 17m 30s, $29.14, with a mean reward of **0.526** across 29 valid trials (range 0.279 – 0.854).

## Quick start

```bash
# 1. Install Harbor (pinned)
./scripts/install-harbor.sh

# 2. Local Python env for the task generator
uv venv .venv --python 3.12 && source .venv/bin/activate
uv pip install datasets huggingface_hub

# 3. Generate task directories from the HF datasets
python scripts/generate_task5_4.py --overwrite     # 31 dirs for task5_4
python scripts/generate_task7_3.py --overwrite     # 24 dirs for task7_3

# 4. Run on Modal (requires MODAL_TOKEN_ID / MODAL_TOKEN_SECRET / ANTHROPIC_API_KEY)
harbor run \
    -p ./tasks \
    -a claude-code \
    -m anthropic/claude-sonnet-4-6 \
    -e modal \
    --n-concurrent 31 \
    --ae ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
    --job-name <name> \
    -y

# 5. Per-trial state and live sandbox count while a run is in flight
python scripts/monitor_job.py jobs/<name>/
```

Trial outputs land in `jobs/<name>/<trial>/`:
- `result.json` — reward, token counts, cost, any exception
- `steps/solve/agent/trajectory.json` — full ATIF trajectory
- `steps/solve/artifacts/` — `solution.json`, `solution.mp4`, and the `materials/` listing
- `steps/solve/verifier/reward.json` — per-metric breakdown (footrule, LIS, adjacency, strict_match)

## Repo layout

```
agentic-vbench/
├── AGENTS.md / CLAUDE.md     # agent-facing repo policy
├── scripts/
│   ├── install-harbor.sh     # pins Harbor version
│   ├── generate_task5_4.py   # HF dataset → 31 task5_4 dirs
│   ├── generate_task7_3.py   # HF dataset → 24 task7_3 dirs
│   └── monitor_job.py        # poll a running job for state changes
└── tasks/
    ├── video-edit-bench-task-5-4-task<N>/      # 31 clip-ordering tasks
    └── video-edit-bench-task-7-3-task<N>/      # 24 storyboard-assembly tasks
        ├── task.toml         # Harbor multi-step task config
        ├── environment/
        │   └── Dockerfile    # python:3.12-slim + ffmpeg
        └── steps/solve/
            ├── instruction.md
            ├── workdir/setup.sh   # pre-agent: curl materials zip from HF
            ├── tests/{test.sh, judge.py}
            └── solution/solve.sh  # oracle
```

## How it works

Each generated task directory is a Harbor multi-step task with a single `solve` step. At trial start, Harbor uploads `steps/solve/workdir/setup.sh` into the Modal sandbox and runs it before the agent — that script curls the per-task materials zip from HuggingFace into `/workspace/materials/`. The agent then has the clips on disk and writes its answer to `/workspace/output/`. After the agent finishes, Harbor copies `tests/` into the same container and runs `test.sh`, which republishes the rollout outputs to `/logs/artifacts/` and scores `solution.json` against the inline ground truth.

No S3, no per-task Docker images: one shared image per benchmark family, materials fetched at trial start, all communication with the host via Harbor's `/logs/{agent,verifier,artifacts}/` bind mounts.

## Known gaps

- Verifier scores `solution.json` only; `solution.mp4` is preserved but not checked against the manifest. Mirrors upstream `video-agent-runner/verifiers/video_order/runner.py` behavior.
- Other three task families (4_2, 6, 7_3) still pending.
- No aggregate-results storage in git; per-job `result.json` lives under `jobs/` which is gitignored.
