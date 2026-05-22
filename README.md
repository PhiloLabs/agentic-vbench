# agentic-vbench

A benchmark suite for evaluating AI coding agents on **video and audio editing tasks**. Built on top of [Harbor](https://www.harborframework.com/) — agent installation, sandboxed execution, concurrency, and trial scoring are handled for you.

Four task families, **100 tasks total**, every task scored on a 0–1 scale.

---

## 📊 What's in the suite

| Family | Count | What the agent does |
|---|---:|---|
| `agentic_vbench_repair` | 18 | Restore a localized corruption (color shift, blur, low-res, swapped object, glitch, content cut, disfluency, or audio defect) in a clip. |
| `agentic_vbench_assembly` | 18 | Pick 4 candidate clips from a pool and place them in the correct slot order to satisfy a prompt. |
| `agentic_vbench_sequencing` | 28 | Re-order a set of shuffled clips into the correct narrative sequence. |
| `agentic_vbench_repurpose` | 36 | Re-cut a long-form source video into a short vertical clip that satisfies a per-task creative brief. |

The `repair`, `assembly`, and `sequencing` families score with deterministic per-family judges and ship a bundled **golden solution** + **broken/random baseline** — by construction the golden scores 1.0 and the baseline scores 0.0. See [`docs/VERIFIER_DESIGN.md`](docs/VERIFIER_DESIGN.md) for the per-family scoring math. The `repurpose` family uses a rubric-based LLM-as-judge against a per-task creative brief (deterministic format checks + Gemini/Opus content judges; same 0–1 reward shape).

---

## 🚀 Quick start

### Install

```bash
git clone https://github.com/PhiloLabs/agentic-vbench.git
cd agentic-vbench
./scripts/install-harbor.sh
python3 -m venv .venv && .venv/bin/pip install --upgrade pip
```

### Sanity check (Docker + oracle agent → reward ≈ 1.0)

```bash
harbor run -p tasks/agentic_vbench_repair/exp-codec-restore-task01 \
           -e docker -a oracle
```

### Run the full suite (Modal + claude-code agent)

```bash
export ANTHROPIC_API_KEY=...
export MODAL_TOKEN_ID=... MODAL_TOKEN_SECRET=...

.venv/bin/python scripts/parallel_rollout.py \
    --mode claude --env modal --max-parallel 20 \
    --tasks $(ls tasks/agentic_vbench_repair/ | tr '\n' ' ')
```

Same pattern for `tasks/agentic_vbench_assembly/` and `tasks/agentic_vbench_sequencing/`. Per-task rewards land in `logs/rollout-results.tsv`.

---

## ⚙️ Supported executors

| Executor | Use when | Required env |
|---|---|---|
| `docker` | Local sanity checks, single-task debugging | none |
| `modal` | Large parallel runs across the suite | `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` |
| `daytona` | Cloud sandboxes (alternative to Modal) | `DAYTONA_API_KEY` |

All task materials are hosted on Hugging Face under [`ameddserM/agentic_vbench_video_*`](https://huggingface.co/ameddserM) and baked into each task's Docker image at build time, so the same image runs on any executor without provider-specific configuration.

---

## 📁 Repo layout

```
agentic-vbench/
├── tasks/                              # 100 Harbor task directories
│   ├── agentic_vbench_repair/          # 18 repair tasks
│   ├── agentic_vbench_assembly/        # 18 assembly tasks
│   ├── agentic_vbench_sequencing/      # 28 sequencing tasks
│   └── agentic_vbench_repurpose/       # 36 repurpose tasks
├── scripts/
│   ├── install-harbor.sh               # Harbor CLI pin
│   ├── parallel_rollout.py             # batched rollout + reward collection
│   ├── monitor_job.py                  # tail a running trial
│   └── _task_paths.py                  # task-name → path resolver
├── docs/VERIFIER_DESIGN.md             # per-family scoring math
└── README.md, LICENSE, AGENTS.md
```
