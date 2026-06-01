# agentic-vbench

<p align="center">
  <a href="https://agenticvbench.com/"><img src="https://img.shields.io/badge/🌐_Website-agenticvbench.com-green" alt="Website"></a>
  <a href="https://arxiv.org/abs/2605.27705"><img src="https://img.shields.io/badge/📖_Paper-arXiv:2605.27705-b31b1b" alt="Paper"></a>
  <a href="https://agenticvbench.com/leaderboard"><img src="https://img.shields.io/badge/🏆_Leaderboard-Live-yellow" alt="Leaderboard"></a>
</p>

<p align="center">
  <img src="asset/overall_fig.png" alt="AgenticVBench: four task families — Assembly, Repair, Sequencing, Repurpose" width="100%">
</p>

**AgenticVBench** is a 100-task benchmark for evaluating AI agents on real-world video post-production workflows — **Assembly**, **Repair**, **Sequencing**, and **Repurpose**. Tasks are authored by 20 industry experts (avg. 6 years of professional experience) and scored on a 0–1 scale, mixing programmatic verifiers with rubric-based LLM judges.

Built on [Harbor](https://www.harborframework.com/) — agent installation, sandboxed execution, concurrency, and trial scoring are handled for you.

---

## 🔥 News

*   **`2026.06.01`** 📖 Our paper is now public on [arXiv](https://arxiv.org/abs/2605.27705) — read the full description of the benchmark, task families, and verifier design.

---

## 📊 What's in the suite

| Family | Count | What the agent does |
|---|---:|---|
| `agentic_vbench_repair` | 18 | Restore a localized corruption (color shift, blur, low-res, swapped object, glitch, content cut, disfluency, or audio defect) in a clip. |
| `agentic_vbench_assembly` | 18 | Pick 4 candidate clips from a pool and place them in the correct slot order to satisfy a prompt. |
| `agentic_vbench_sequencing` | 28 | Re-order a set of shuffled clips into the correct narrative sequence. |
| `agentic_vbench_repurpose` | 36 | Re-cut a long-form source video into a short vertical clip that satisfies a per-task creative brief. |

The `repair`, `assembly`, and `sequencing` families score with deterministic per-family judges and ship a bundled **oracle solver** + **broken/random baseline** — by construction the oracle scores 1.0 and the baseline scores 0.0. See [`docs/VERIFIER_DESIGN.md`](docs/VERIFIER_DESIGN.md) for the per-family scoring math. The `repurpose` family uses a rubric-based LLM-as-judge against a per-task creative brief (deterministic format checks + Gemini/Opus content judges; same 0–1 reward shape) — running it requires both `GEMINI_API_KEY` and `ANTHROPIC_API_KEY` on the verifier side.

Typical model scores live on the [leaderboard](https://agenticvbench.com/leaderboard) — use it to gauge whether your run is in the expected range.

---

## 🚀 Quick start

### 1. Install

```bash
git clone https://github.com/PhiloLabs/agentic-vbench.git
cd agentic-vbench
./scripts/install-harbor.sh
python3 -m venv .venv && .venv/bin/pip install --upgrade pip
```

### 2. Run one task with an agent

Pick any agent supported by Harbor (`claude-code`, `codex`, `gemini-cli`, `opencode`, …), export the matching API key, and run via the `./avb` CLI (a thin wrapper that auto-injects per-agent + per-family env vars into `harbor run`):

```bash
# Claude Code (Anthropic):
export ANTHROPIC_API_KEY=...
./avb run exp-codec-restore-task01 -a claude-code -m anthropic/claude-sonnet-4-6

# Codex (OpenAI):
export OPENAI_API_KEY=...
./avb run exp-codec-restore-task01 -a codex -m openai/gpt-5.5
```

For `agentic_vbench_repurpose` tasks the **verifier** additionally needs `GEMINI_API_KEY` (the rubric LLM judge uses Gemini for audio/video grading) — export it and `avb` will forward it via Harbor's `--ve` flag. Run `./avb tasks env <task>` to see what credentials a given task and agent combo need.

**Bringing your own agent.** The four agents listed above are vendor-native Harbor agents that work against the task set out of the box. Custom agents — including open-source harnesses and proprietary stacks — plug into Harbor through a small adapter. See [Harbor's agents docs](https://www.harborframework.com/docs/agents) for the adapter contract.

**Free smoke test (no agent API spend).** Every repair/assembly/sequencing task ships a bundled oracle solver. Use it to confirm the harness is wired up end-to-end:

```bash
./avb run exp-codec-restore-task01 -a oracle -e docker
# reward.json → ≈ 1.0, ~30 s on a cached image, zero agent cost
```

**Time + cost budget.** A real-agent rollout on Modal typically takes ~10 min per task wall clock. Cost depends entirely on agent + model — order-of-magnitude $0.10–$2 per task with mid-tier models, scaling linearly with the agent's token use. Plan accordingly for a 100-task sweep.

**Here's what a task prompt actually looks like** (`exp-codec-restore-task01`):

> # Restore A Muffled Stretch Of Audio
>
> I have a short mono speech recording at `/workspace/materials/noisy.wav`. For a stretch in it, the audio sounds muffled — like the high end has been chopped off and the voice lost its sparkle. The rest of the recording sounds clean and full.
>
> Please restore the muffled stretch so it sounds as clear and full as the rest of the recording. Leave the already-clean parts unchanged.
>
> ## What to deliver
> - `/workspace/output/enhanced.wav` — 16-bit PCM mono at 16 kHz, same total length (sample count) as the input.

Each task ships its own such brief at `tasks/<family>/<task>/steps/solve/instruction.md`.

**Inspect the result.** Each trial drops four artifacts under `jobs/<job-name>/<trial-id>/`:

| File | What it is |
|---|---|
| `steps/solve/verifier/reward.json` | Final score + per-metric breakdown. |
| `agent/trajectory.json` | Full event stream Harbor captured for the agent (tool calls, tool results, model messages, final output). |
| `result.json` | Per-trial Harbor summary (timings, exit codes, exception info). |
| `trial.log` | Combined stdout/stderr stream for the whole trial. |

```bash
./avb results show          # rewards from the latest job
cat jobs/<job-name>/*/steps/solve/verifier/reward.json
# {
#   "reward": 0.55,
#   "details": { "reason": "ok", ... }
# }
```

While a trial is running, `./avb run` prints `tail -F jobs/<job>/*/trial.log` — copy that to watch progress in another shell.

Run `./avb -h` to see every subcommand (`tasks list / check / env`, `run`, `rollout`, `results show`).

### 3. Run a full family in parallel

```bash
export ANTHROPIC_API_KEY=...
export MODAL_TOKEN_ID=... MODAL_TOKEN_SECRET=...

./avb rollout --family repair --agent claude-code --env modal --max-parallel 20
```

Same pattern for the other families. Per-task rewards land in `logs/rollout-results.tsv`; full per-trial artifacts (agent trajectory, verifier breakdown) under `jobs/<job-name>/`.

---

## 🏆 Submitting to the leaderboard

Once you've run all 100 tasks, zip the `jobs/` directory (which contains the `reward.json` + `trajectory.json` + `result.json` per trial) and follow the submission flow at [agenticvbench.com](https://agenticvbench.com/) — that page has the email template + a Google Drive link prompt. Reviewers verify that every task in the suite has an intact trajectory and that scores fall in `[0, 1]`, then publish to the [leaderboard](https://agenticvbench.com/leaderboard).

---

## ⚙️ Supported executors

Any executor that [Harbor](https://www.harborframework.com/) supports works — pass `-e <executor>` to `harbor run` (or `./avb run`). Common picks:

| Executor | Use when | Required env |
|---|---|---|
| `docker` | Local sanity checks, single-task debugging | none |
| `modal` | Large parallel runs across the suite | `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` |
| `daytona` | Cloud sandboxes (alternative to Modal) | `DAYTONA_API_KEY` |
| `e2b` | Sandbox-as-a-service for code execution | `E2B_API_KEY` |
| `runloop` | Long-running cloud workspaces | `RUNLOOP_API_KEY` |

Plus `apple_container`, `gke`, `singularity`, `tensorlake`, and anything else Harbor adds — see Harbor's `--env` choices in `harbor run -h` for the live list.

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
