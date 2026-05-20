# agentic-vbench

A benchmark suite for evaluating AI coding agents on three families of
video/audio editing tasks, built on top of
[Harbor](https://www.harborframework.com/). Each task is a single Harbor
task directory — Harbor handles agent installation, sandbox orchestration on
Modal, concurrency, trial lifecycle, and result collection. This repo ships
the tasks themselves plus a thin wrapper for running and scoring them.

## What's in the suite

| Family | Count | What the agent does |
|---|---:|---|
| `agentic_vbench_repair` | 20 | Restore a single localised corruption (color, blur, super-res, swap, glitch, cut, disfluency, or audio defect) inside a clip. |
| `agentic_vbench_assembly` | 18 | Assemble 4 candidate clips into the correct slot order to satisfy a prompt. |
| `agentic_vbench_sequencing` | 31 | Re-order shuffled clips into the correct narrative sequence. |

Per-task materials (input clips for the agent, reference goldens for the
verifier) live on HuggingFace under `ameddserM/agentic_vbench_*` and are
fetched at trial start by the task's `workdir/setup.sh`. The verifier is
baked into each task's `tests/judge.py` at build time and runs at trial
end — Harbor writes the per-trial reward to `/logs/verifier/reward.json`.

## How repair tasks are scored

For repair tasks, every metric is normalized so that the broken input scores
0 and the bundled golden scores 1 by construction:

- higher-is-better: `score = clip((M_out − M_broken) / (M_golden − M_broken), 0, 1)`
- lower-is-better: `score = clip((M_broken − M_out) / (M_broken − M_golden), 0, 1)`

Per-family metrics: PESQ-WB (denoise), SRMR (dereverb), SI-SDR (declip), LSD
(codec), CIEDE2000 (color), LPIPS (deblur, swap), LPIPS+Y-PSNR composite
(super-res), binary range-F1 + SSIM honesty gate (cut / glitch / disfluency).

Full math + per-family details: [`docs/VERIFIER_DESIGN.md`](docs/VERIFIER_DESIGN.md).

Assembly and sequencing tasks score deterministically off the agent's
reported ordering — assembly uses exact-slot accuracy with `.mp4`
normalization; sequencing uses a composite
`0.4·(1 − normalized_footrule) + 0.3·LIS_ratio + 0.3·adjacency`.

## Quick start

```bash
# 1. Install Harbor (pinned)
./scripts/install-harbor.sh

# 2. Local Python env (only needed for the rollout wrapper)
python3 -m venv .venv
.venv/bin/pip install --upgrade pip

# 3. Run one task locally on Docker, oracle mode (sanity check — expect reward ≈ 1.0)
harbor run -p tasks/agentic_vbench_repair/exp-codec-restore-task01 \
           -e docker -a oracle

# 4. Run the full suite on Modal with claude-code as the agent
export ANTHROPIC_API_KEY=...
export MODAL_TOKEN_ID=... MODAL_TOKEN_SECRET=...

.venv/bin/python scripts/parallel_rollout.py \
    --mode claude --env modal --max-parallel 20 \
    --tasks $(ls tasks/agentic_vbench_repair/ | tr '\n' ' ')

# Same pattern for the other two families:
.venv/bin/python scripts/parallel_rollout.py \
    --mode claude --env modal --max-parallel 20 \
    --tasks $(ls tasks/agentic_vbench_assembly/ | tr '\n' ' ')
```

Rewards land in `logs/rollout-results.tsv` (one row per task) and in each
trial's `jobs/<job-name>/<trial>/verifier/reward.json`.

## Repo layout

```
agentic-vbench/
├── AGENTS.md / CLAUDE.md             # repo policy
├── README.md, LICENSE
├── tasks/
│   ├── agentic_vbench_repair/        # 20 repair tasks
│   ├── agentic_vbench_assembly/      # 18 assembly tasks
│   └── agentic_vbench_sequencing/    # 31 sequencing tasks
├── scripts/                          # Harbor wrapper (no task generation)
│   ├── install-harbor.sh
│   ├── parallel_rollout.py           # run + collect rewards across tasks
│   ├── monitor_job.py                # tail a running trial
│   └── _task_paths.py                # task-name → path resolver
├── docs/VERIFIER_DESIGN.md           # verifier math (repair tasks)
└── jobs/, logs/, site/               # runtime outputs (gitignored)
```

## How a task runs

Each task is a Harbor multi-step dir with a single `solve` step. At trial
start, Harbor runs `steps/solve/workdir/setup.sh`, which `curl`s the
per-task materials zip from HuggingFace and unpacks the agent-facing
`input/` files into `/workspace/materials/`. The agent then writes its
output to `/workspace/output/`. Harbor then runs `tests/test.sh`, which
fetches the verifier-only `golden/` files (kept separate from the agent's
view) and invokes the baked-in `judge.py` to produce
`/logs/verifier/reward.json`.

Oracles ship a `solution/solve.sh` that fetches the golden materials and
writes them to `/workspace/output/` directly; running with `-a oracle`
should yield reward ≈ 1.0 on every task.
