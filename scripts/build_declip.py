#!/usr/bin/env python3
"""Generate `exp-declip-task01`.

Casey Neistat marathon vlog (clip 120-155s) hard-clipped only inside a
centered 10 s window. Out-of-window samples stay clean. Clip mask + window
metadata go into the test bundle so the judge can compute masked SI-SDR
on in-window destroyed peaks AND penalize over-enhancement on the
out-of-window region.
"""
from __future__ import annotations

import json
import shutil
import stat
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _audio_window import pick_window  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CLIP = ROOT / "clips" / "04-casey.wav"
TASK_DIR = ROOT / "tasks" / "agentic_vbench_repair" / "exp-declip-task01"
JUDGE_SRC = Path(__file__).resolve().parent / "_judges" / "declip.py"

SEED = 42
WINDOW_S = 10.0

TASK_TOML = """\
version = "1.0"

[task]
name = "agentic-vbench/exp-declip-task01"

[metadata]
difficulty = "medium"
category = "audio-repair"
tags = ["declipping", "speech-enhancement", "urgent2024", "experiment"]
source = "Casey Neistat marathon vlog speech (clip 120-155s)"
corruption = "hard clip np.clip(±q) at q={q}-quantile of |x|, threshold={threshold:.4f}, clipped_frac={frac:.4f} (seed=42)"

[environment]
build_timeout_sec = 600.0
cpus = 2
memory_mb = 4096
storage_mb = 10240
allow_internet = true

[[steps]]
name = "solve"

[steps.agent]
timeout_sec = 1800.0

[steps.verifier]
timeout_sec = 600.0
"""

DOCKERFILE = """\
FROM --platform=linux/amd64 python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \\
        ffmpeg \\
        curl \\
        ca-certificates \\
        gcc \\
        python3-dev \\
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
"""

INSTRUCTION_MD = """\
# Speech Declipping Task

A hard-clipped 16 kHz mono speech recording is at
`/workspace/materials/noisy.wav` (~35 seconds, 16-bit PCM). The signal
was normalized to [-1, 1] then symmetrically clipped at
`np.clip(x, -q_threshold, +q_threshold)` where `q_threshold` is some
quantile of `|x|` (you don't know which). All peaks exceeding the
threshold have been destroyed (flattened).

## Your job

Produce a reconstructed version at **`/workspace/output/enhanced.wav`**
that recovers the destroyed peaks.

## Output format

- Sample rate: **16000 Hz**
- Channels: **mono**
- Bit depth: **16-bit PCM**
- Length: **same number of samples** as the input.

## Scoring

The judge knows the clip mask (which samples were flattened). Reward:

    masked_SDR = SDR over only the clipped-region samples
    reward = 0.5 * clip01((masked_SDR + 5) / 25) + 0.5 * STOI

Composite reward in `[0, 1]`. Passthrough scores ~0.25-0.35. Cubic
spline interpolation between unclipped peaks scores ~0.40-0.60.
SOTA neural declippers can clear 0.7+.

## Notes

- `ffmpeg` is on `PATH`. Container has internet.
- Useful: `scipy.interpolate` (cubic spline), `librosa` peak picking,
  or neural models like `Speech-Declipping-Transformer`.
- Stay inside `/workspace/`. Do not search the web for the original
  source.
"""

SETUP_SH = """\
#!/bin/bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p /workspace/materials /workspace/output /workspace/work
cp "$HERE/noisy.wav" /workspace/materials/noisy.wav
mkdir -p /logs/artifacts
ls -la /workspace/materials/ > /logs/artifacts/materials-listing.txt
rm -f -- "$HERE/noisy.wav" "$0"
"""

TEST_SH = """\
#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier /logs/artifacts
if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi
pip install --quiet --no-cache-dir \\
    "numpy<3" "scipy<2" "soundfile==0.13.*" "pesq==0.0.4" "pystoi==0.4.*"
python3 /tests/judge.py \\
        --enhanced /workspace/output/enhanced.wav \\
        --clean /tests/clean.wav \\
        --clip-mask /tests/clip_mask.npy \\
        --window-json /tests/window.json \\
        --reward-json /logs/verifier/reward.json \\
        --reward-txt /logs/verifier/reward.txt
"""

# Window-aware v3 judge lives in scripts/_judges/declip.py.

SOLVE_SH = """\
#!/bin/bash
# Reference solver: cubic-spline interpolation between unclipped peaks.
# Detects flat-top runs at +-max(|x|), interpolates over them.
# Calibrated target: ~0.40-0.60.
set -euo pipefail
mkdir -p /workspace/output
pip install --quiet --no-cache-dir "numpy<3" "scipy<2" soundfile
python3 - <<'PY'
import numpy as np
import soundfile as sf
from scipy.interpolate import CubicSpline

x, sr = sf.read("/workspace/materials/noisy.wav")
x = x.astype(np.float32)
# Estimate clip threshold from data: top of |x|.
t = float(np.max(np.abs(x))) * 0.999
mask = np.abs(x) >= t  # detected clipped samples
# Replace each clipped run by cubic spline through neighbor samples.
keep_idx = np.flatnonzero(~mask)
if len(keep_idx) >= 4:
    cs = CubicSpline(keep_idx, x[keep_idx], extrapolate=True)
    bad = np.flatnonzero(mask)
    x_fix = x.copy()
    x_fix[bad] = cs(bad)
    # Soft re-cap to avoid blow-up.
    peak = float(np.max(np.abs(x_fix))) or 1.0
    if peak > 0.99:
        x_fix = x_fix / peak * 0.99
else:
    x_fix = x

sf.write("/workspace/output/enhanced.wav", x_fix.astype(np.float32), sr, subtype="PCM_16")
print(f"ref-solver: cubic-spline declip on {len(x)} samples (n_clipped~{int(mask.sum())})")
PY
"""


def _write_exec(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> int:
    if not CLIP.exists():
        print(f"missing clip: {CLIP}", file=sys.stderr)
        return 1

    np.random.seed(SEED)
    speech, sr = sf.read(str(CLIP), always_2d=False)
    if sr != 16000:
        print(f"unexpected sr {sr}", file=sys.stderr)
        return 1
    speech = speech.astype(np.float32)
    n = len(speech)

    # Normalize to [-1, 1]
    peak0 = float(np.max(np.abs(speech))) or 1.0
    speech_n = speech / peak0
    speech_n = speech_n * 0.99  # keep some headroom

    win_start_s, win_end_s = pick_window(speech_n, 16000, WINDOW_S)
    s0 = int(round(win_start_s * 16000))
    s1 = int(round(win_end_s * 16000))

    q_choices = [0.5, 0.7, 0.9]
    q = float(q_choices[int(np.random.randint(0, len(q_choices)))])
    # Threshold computed from |x| inside the window so the q-quantile is
    # honored on the corruption region (not the whole clip).
    threshold = float(np.quantile(np.abs(speech_n[s0:s1]), q))

    out = speech_n.astype(np.float32).copy()
    in_slice = np.clip(speech_n[s0:s1], -threshold, threshold).astype(np.float32)
    out[s0:s1] = in_slice
    clipped = out

    # Mask: clipped only inside the window.
    clip_mask = np.zeros(len(speech_n), dtype=np.uint8)
    clip_mask[s0:s1] = (np.abs(speech_n[s0:s1]) > threshold).astype(np.uint8)
    frac = float(clip_mask.mean())

    judge_src = JUDGE_SRC.read_text()
    if not judge_src.strip():
        print(f"empty JUDGE_SRC at {JUDGE_SRC}", file=sys.stderr)
        return 1

    if TASK_DIR.exists():
        shutil.rmtree(TASK_DIR)
    (TASK_DIR / "environment").mkdir(parents=True)
    (TASK_DIR / "environment" / "Dockerfile").write_text(DOCKERFILE)
    (TASK_DIR / "task.toml").write_text(TASK_TOML.format(q=q, threshold=threshold, frac=frac))

    step_dir = TASK_DIR / "steps" / "solve"
    step_dir.mkdir(parents=True)
    (step_dir / "instruction.md").write_text(INSTRUCTION_MD)

    workdir = step_dir / "workdir"
    workdir.mkdir()
    _write_exec(workdir / "setup.sh", SETUP_SH)
    sf.write(workdir / "noisy.wav", clipped, 16000, subtype="PCM_16")

    tests = step_dir / "tests"
    tests.mkdir()
    _write_exec(tests / "test.sh", TEST_SH)
    _write_exec(tests / "judge.py", judge_src)
    # Clean reference = the pre-clip normalized signal (this is the GT the
    # agent is asked to recover, not the original un-normalized signal).
    sf.write(tests / "clean.wav", speech_n.astype(np.float32), 16000, subtype="PCM_16")
    np.save(tests / "clip_mask.npy", clip_mask)
    (tests / "window.json").write_text(json.dumps({
        "window_start_s": float(win_start_s),
        "window_end_s": float(win_end_s),
    }))

    _write_exec(step_dir / "solution" / "solve.sh", SOLVE_SH)

    print(f"[declip] wrote {TASK_DIR}")
    print(f"  q: {q}, threshold: {threshold:.4f}, clipped_frac: {frac:.4f}")
    print(f"  window: [{win_start_s:.2f}, {win_end_s:.2f}] s")
    print(f"  clip length: {n} samples / {n/16000:.2f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
