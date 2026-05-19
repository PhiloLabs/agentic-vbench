# agentic-vbench

A benchmark suite for evaluating AI coding agents on video and audio **repair**
tasks, built on top of [Harbor](https://www.harborframework.com/). Each task is
a single Harbor task directory — Harbor handles agent installation, sandbox
orchestration on Modal, concurrency, trial lifecycle, and result collection.
This repo defines the tasks themselves, the verifier (v4), and the local
tooling that drives rollouts + scoring + reporting.

## What's in the suite

20 active repair tasks across 7 families. Each task is a small video or audio
clip with a single localised corruption; the agent's job is to restore the
clip and report which span it fixed.

| Family | Tasks | What the agent sees | What it must restore |
|---|---|---|---|
| `exp-color-shot-*` | 3 (visit-korea, gobelins, v3-s1) | A clip with a bad colour grade applied to a contiguous window. | Match the overall clip's grade across that window. |
| `exp-deblur-*` | 2 (motion-f1, gaussian-mkbhd) | Clip with blur over a time window (full-frame or in-mask). | Sharpen the blurred frames. |
| `exp-sr-*` | 2 (sr-2x, sr-4x) | Clip with one shot downsampled then bicubic-upscaled. | Restore the lower-quality shot's detail. |
| `exp-swap-*` | 2 (swap-car, swap-product) | Multi-shot clip with two shots in the wrong positions. | Put the shots back in the original order. |
| `exp-glitch-dup-*` | 2 (short, long) | Clip with stuck-frame stutters. | Cut the duplicated frames. |
| `exp-content-cut-*` | 2 (mkbhd, wsj) | Video where a specific segment needs removing. | Cut that segment, keep the join smooth. |
| `exp-disfluency-interview-*` | 2 (3, 4) | Interview clip with brief hesitant moments. | Cut the hesitations without losing content. |
| audio (5) | dns-denoise, voicebank, dereverb, declip, codec-restore | 16 kHz speech with a windowed corruption. | Clean the in-window audio. |

The earlier Harbor-adapter prototypes (`tasks/task5_4/*` ×31 and
`tasks/task7_3/*` ×24) are kept in the repo as historical context but are no
longer the active benchmark. A newer video-ordering family (`tasks/task5_5/*`
×22, built from a local `~/Downloads/sequencing_batch2` bundle) lives alongside.

## v4 verifier — universal normalize-improvement

Every task scores under the same affine form, anchored at broken=0 / golden=1
by construction:

- higher-is-better: `score = clip((M_out − M_broken) / (M_golden − M_broken), 0, 1)`
- lower-is-better: `score = clip((M_broken − M_out) / (M_broken − M_golden), 0, 1)`

Per-family base metrics chosen for paper alignment + clean broken→golden
spread:

| Family | Metric | Source |
|---|---|---|
| dns-denoise / voicebank | PESQ-WB in-window | DNS Challenge / Valentini 2016 |
| dereverb | SRMR + PESQ-WB sanity gate | REVERB Challenge |
| declip | masked SI-SDR on clip_mask only | URGENT 2024 |
| codec-restore | LSD in-window | Codec-SUPERB |
| color-shot | CIEDE2000 in-window | CIE perceptual standard |
| deblur | LPIPS (in-mask × in-window) | NTIRE perceptual track |
| sr | 0.7 × LPIPS + 0.3 × Y-PSNR in-shot | NTIRE 2022+ composite |
| swap | LPIPS on swap-window, ±5-frame tolerance | — |
| cut / glitch / disfluency | binary range-F1 + honesty SSIM | — |

Every oracle ships a ceiling-proof `solution/solve.sh` that copies the
bundled golden reference to the output — all 20 oracles score exactly 1.000
under v4, validated by `scripts/v4/validate_anchors.py`.

Full design rationale: [`docs/v4/V4_DESIGN.md`](docs/v4/V4_DESIGN.md).
Per-family metric audit + comparison vs v3: [`docs/v4/V4_RESULTS_SUMMARY.md`](docs/v4/V4_RESULTS_SUMMARY.md).
Oracle audit + ceiling-proof fixes for 12 tasks: [`docs/v4/ORACLE_AUDIT.md`](docs/v4/ORACLE_AUDIT.md).

## Quick start

```bash
# 1. Install Harbor (pinned)
./scripts/install-harbor.sh

# 2. Local Python env for build scripts + scoring
python3 -m venv .venv
.venv/bin/pip install lpips pesq pystoi srmrpy speechmos librosa soundfile \
                     opencv-python-headless scikit-image scikit-learn torch \
                     torchvision numpy scipy ffmpeg-python

# 3. Build the 20 tasks (idempotent; each script regenerates one task dir)
for f in scripts/build_codec_restore.py scripts/build_color_shot_*.py \
         scripts/build_content_cut_*.py scripts/build_deblur_*.py \
         scripts/build_declip.py scripts/build_dereverb.py \
         scripts/build_disfluency_interview_*.py scripts/build_dns_denoise.py \
         scripts/build_glitch_dup_*.py scripts/build_sr_*.py \
         scripts/build_swap_*.py scripts/build_voicebank_denoise.py; do
    .venv/bin/python $f
done

# 4. Run all 20 tasks on Modal (max 20 parallel)
export ANTHROPIC_API_KEY=...
export MODAL_TOKEN_ID=... MODAL_TOKEN_SECRET=...
.venv/bin/python scripts/parallel_rollout.py \
    --mode claude --env modal --max-parallel 20 \
    --tasks $(ls tasks/repair_v4/ | tr '\n' ' ')

# 5. Score the artifacts under v4 + build the review dashboard
.venv/bin/python scripts/v4/recompute_oracle.py     # oracle smoke artifacts
.venv/bin/python scripts/v4/recompute_all.py        # claude artifacts
.venv/bin/python scripts/build_site_v4.py
open site/index-v4.html
```

## Repo layout

```
agentic-vbench/
├── AGENTS.md / CLAUDE.md      # repo policy (single source of truth)
├── tasks/                     # Harbor task dirs, one subdir per family
│   ├── repair_v4/             # 20 active v4 repair tasks (exp-*)
│   ├── task5_4/               # 31 video-ordering tasks (HF dataset)
│   ├── task5_5/               # 22 video-ordering tasks (local sequencing_batch2)
│   └── task7_3/               # 24 video-assembly tasks
├── scripts/
│   ├── _task_paths.py         # task-name → path resolver across families
│   ├── install-harbor.sh, monitor_job.py
│   ├── generate_task5_4.py, generate_task5_5.py, generate_task7_3.py
│   ├── build_<family>.py × 19                     # v4 task builders
│   ├── _<family>_core.py × 8 + _judges/           # shared verifier cores
│   ├── parallel_rollout.py, fetch_noise_pools.py
│   ├── build_site.py, build_site_v4.py
│   └── v4/                    # v4 verifier framework
│       ├── _framework.py      # universal normalize_improvement helper
│       ├── judge_audio.py     # 5 audio judges
│       ├── judge_video.py     # 9 video judges
│       ├── judge_passthrough.py
│       ├── recompute_all.py, recompute_oracle.py
│       ├── validate_anchors.py
│       └── fix_oracle_solve_sh.py
├── docs/
│   ├── plan.md, status.md, report.md
│   └── v4/V4_DESIGN.md, V4_RESULTS_SUMMARY.md, ORACLE_AUDIT.md
├── sources/, clips/, noise/, .models/    # raw inputs (gitignored)
├── jobs/, site/, logs/                   # runtime outputs (gitignored)
└── .venv/                                # python env (gitignored)
```

## Validation properties

- **Broken = 0, golden = 1 for every task** — verified by
  `scripts/v4/validate_anchors.py` (replays each judge with broken→broken
  and golden→golden as the "claude" input; all 14 non-passthrough tasks
  pass; the 7 cut/glitch tasks are 0/1 by binary range-F1 construction).
- **Oracle = 1.000 for all 20 tasks** — every `solution/solve.sh` ships a
  bundled golden reference (`solution/<golden_file>`) and `cp`s it to the
  output. Re-rolled on Modal and re-scored after each verifier change.

## How a task runs

Each task is a Harbor multi-step dir with a single `solve` step. At trial
start, Harbor uploads `steps/solve/workdir/setup.sh` into the Modal sandbox
and runs it before the agent — that script stages the per-task corruption
materials (e.g., `corrupted.mp4`, `noisy.wav`, `prompt.txt`) into
`/workspace/materials/`. The agent then writes its output to
`/workspace/output/`. Harbor then runs `tests/test.sh`, which invokes the
baked-in `judge.py` and produces `/logs/verifier/reward.json`.

All `cc-*` and `smoke-*` job artifacts land in `jobs/` (gitignored). The v4
recompute drivers pick up the latest artifact per task and rescore against
the current verifier code.

## Known design choices

- **No GPU on Modal** for the v4 suite. All tasks run CPU-only with
  CPU-feasible libraries (faster-whisper tiny.en, noisereduce, scipy.signal,
  etc.). GPU-class work (Real-ESRGAN 4× SR, neural deblur) timed out on the
  agent side in earlier prototypes and isn't a target for this iteration.
- **Audio sources** (`clips/`, `noise/`) are gitignored; regenerable via
  `scripts/fetch_noise_pools.py` and direct HF downloads documented in
  `docs/repair-research.md`.
- **Video sources** (`sources/`) are gitignored binaries; the per-clip
  provenance lives in `sources/SOURCE_DIVERSITY_NOTES.md` (also gitignored).
- **Site assets** (`site/assets/` — 2.2 GB) are regenerated by the dashboard
  builder; not committed.
