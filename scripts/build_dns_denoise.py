#!/usr/bin/env python3
"""Generate the single Harbor task dir `exp-dns-denoise-task01`.

Pipeline:
  1) Read the 35 s clean clip at clips/01-veritasium.wav (16 kHz mono PCM16).
  2) Pick one DNS noise file from noise/dns/ (deterministic via seed=42).
  3) Pick one SNR ~ Uniform(-5, +20) dB (deterministic via seed=42).
  4) Scale noise to target SNR, add to speech ONLY within a centered 10 s
     window. Out-of-window samples stay clean. Emit `window.json` next to
     the judge so it can score in- and out-of-window separately.

Reward formula (window-aware v3 judge, paper-grade DNSMOS composite):
  in_window_reward  = existing v3 composite on in-window slice
  out_window_reward = clip01((SI-SDR_out + 5) / 30)  (close to 1 if untouched)
  reward            = 0.85 * in_window_reward + 0.15 * out_window_reward
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
CLIP = ROOT / "clips" / "01-veritasium.wav"
NOISE_DIR = ROOT / "noise" / "dns"
TASK_DIR = ROOT / "tasks" / "exp-dns-denoise-task01"

SEED = 42
WINDOW_S = 10.0

TASK_TOML = """\
version = "1.0"

[task]
name = "agentic-vbench/exp-dns-denoise-task01"

[metadata]
difficulty = "medium"
category = "audio-repair"
tags = ["speech-enhancement", "denoising", "dns-challenge", "experiment"]
source = "Veritasium 'Blue Roses' narration (clip 60-95s) + DNS-Challenge-2020 noise"
corruption = "additive DNS noise at SNR={snr_db:.2f} dB (seed=42)"

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
# linux/amd64 so the verifier's pesq sdist compiles cleanly (no
# manylinux_aarch64 wheel on PyPI). On arm64 hosts (e.g. Apple Silicon)
# docker runs this via qemu.
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
# Speech Denoising Task (DNS-style)

A noisy 16 kHz mono speech recording is at
`/workspace/materials/noisy.wav` (~35 seconds, 16-bit PCM). Background
noise drawn from the DNS Challenge 2020 noise pool has been mixed on
top of a clean narration track at a random SNR.

## Your job

Produce a denoised version at **`/workspace/output/enhanced.wav`**.

## Output format (must match exactly)

- Sample rate: **16000 Hz**
- Channels: **mono**
- Bit depth: **16-bit PCM**
- Length: **same number of samples** as the input (small alignment
  mismatches are tolerated; large ones tank the score).

## Scoring

Composite reward in `[0, 1]`:

    reward = 0.4 * clip01((PESQ_wb - 1) / 3.5)
           + 0.3 * STOI
           + 0.3 * clip01((SI-SDR + 10) / 30)

Passthrough (no processing) scores around ~0.30. A spectral-gating
denoiser scores ~0.40. A neural denoiser (DeepFilterNet, Demucs)
should clear ~0.55+.

## Notes

- `ffmpeg` is on `PATH`. Built-in option: `afftdn`. Or pip-install a
  neural denoiser (the container has internet).
- Stay inside `/workspace/`. Do not search the web for the original
  clean source or any leaked reference.
- Use `/workspace/work/` for scratch, `/workspace/output/` only for the
  final `enhanced.wav`.
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
    "numpy<3" "scipy<2" "soundfile==0.13.*" "pesq==0.0.4" "pystoi==0.4.*" \\
    "onnxruntime"
python3 /tests/judge.py \\
        --enhanced /workspace/output/enhanced.wav \\
        --clean /tests/clean.wav \\
        --dnsmos-model /tests/sig_bak_ovr.onnx \\
        --window-json /tests/window.json \\
        --reward-json /logs/verifier/reward.json \\
        --reward-txt /logs/verifier/reward.txt
"""

# Window-aware v3 judge is the source-of-truth at scripts/_judges/dns_denoise.py;
# build_*.py reads it and copies into the task dir so the same judge runs
# locally + in the Harbor container.
JUDGE_SRC = Path(__file__).resolve().parent / "_judges" / "dns_denoise.py"

SOLVE_SH = """\
#!/bin/bash
# Reference solver: noisereduce spectral gating. Calibrated to score in
# the 0.30-0.50 range on this instance.
set -euo pipefail
mkdir -p /workspace/output
pip install --quiet --no-cache-dir noisereduce soundfile "numpy<3"
python3 - <<'PY'
import noisereduce as nr, soundfile as sf
data, sr = sf.read("/workspace/materials/noisy.wav")
reduced = nr.reduce_noise(y=data, sr=sr)
sf.write("/workspace/output/enhanced.wav", reduced, sr, subtype="PCM_16")
print(f"ref-solver: noisereduce on {len(data)} samples @ {sr}Hz")
PY
"""


def _write_exec(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _tile_to_length(noise: np.ndarray, n: int) -> np.ndarray:
    if len(noise) >= n:
        return noise[:n]
    reps = int(np.ceil(n / len(noise)))
    return np.tile(noise, reps)[:n]


def main() -> int:
    if not CLIP.exists():
        print(f"missing clean clip: {CLIP}", file=sys.stderr)
        return 1
    noise_files = sorted(NOISE_DIR.glob("*.wav"))
    if not noise_files:
        print(f"no noise files under {NOISE_DIR}; run fetch_noise_pools.py first",
              file=sys.stderr)
        return 1

    rng = np.random.default_rng(SEED)
    np.random.seed(SEED)

    speech, sr = sf.read(str(CLIP), always_2d=False)
    if sr != 16000:
        print(f"unexpected sample rate {sr}", file=sys.stderr)
        return 1
    speech = speech.astype(np.float32)
    n = len(speech)

    # Deterministic draws under seed 42
    snr_db = float(np.random.uniform(-5.0, 20.0))
    noise_path = noise_files[int(np.random.randint(0, len(noise_files)))]

    noise, sr_n = sf.read(str(noise_path), always_2d=False)
    if sr_n != 16000:
        print(f"noise sr {sr_n} != 16000 ({noise_path.name})", file=sys.stderr)
        return 1
    noise = noise.astype(np.float32)
    noise = _tile_to_length(noise, n)

    # Scale noise -> target SNR (RMS computed inside the window for a
    # cleaner per-window SNR contract).
    win_start_s, win_end_s = pick_window(speech, 16000, WINDOW_S)
    s0 = int(round(win_start_s * 16000))
    s1 = int(round(win_end_s * 16000))
    sp_in_norm = float(np.linalg.norm(speech[s0:s1]) + 1e-8)
    n_in_norm = float(np.linalg.norm(noise[s0:s1]) + 1e-8)
    scale = sp_in_norm / n_in_norm * 10.0 ** (-snr_db / 20.0)
    noisy = speech.copy()
    noisy[s0:s1] = speech[s0:s1] + noise[s0:s1] * scale
    peak = float(np.max(np.abs(noisy)))
    if peak > 0.99:
        # Only scale the noisy region; leave clean samples untouched.
        scale_down = 0.99 / peak
        noisy[s0:s1] *= scale_down

    judge_src = JUDGE_SRC.read_text()
    if not judge_src.strip():
        print(f"empty JUDGE_SRC at {JUDGE_SRC}", file=sys.stderr)
        return 1

    if TASK_DIR.exists():
        shutil.rmtree(TASK_DIR)
    (TASK_DIR / "environment").mkdir(parents=True)
    (TASK_DIR / "environment" / "Dockerfile").write_text(DOCKERFILE)
    (TASK_DIR / "task.toml").write_text(TASK_TOML.format(snr_db=snr_db))

    step_dir = TASK_DIR / "steps" / "solve"
    step_dir.mkdir(parents=True)
    (step_dir / "instruction.md").write_text(INSTRUCTION_MD)

    workdir = step_dir / "workdir"
    workdir.mkdir()
    _write_exec(workdir / "setup.sh", SETUP_SH)
    sf.write(workdir / "noisy.wav", noisy.astype(np.float32), 16000, subtype="PCM_16")

    tests = step_dir / "tests"
    tests.mkdir()
    _write_exec(tests / "test.sh", TEST_SH)
    _write_exec(tests / "judge.py", judge_src)
    sf.write(tests / "clean.wav", speech, 16000, subtype="PCM_16")
    (tests / "window.json").write_text(json.dumps({
        "window_start_s": float(win_start_s),
        "window_end_s": float(win_end_s),
    }))
    # Carry DNSMOS model into the test bundle if cached in .models/.
    dnsmos = ROOT / ".models" / "sig_bak_ovr.onnx"
    if dnsmos.exists():
        (tests / "sig_bak_ovr.onnx").write_bytes(dnsmos.read_bytes())

    _write_exec(step_dir / "solution" / "solve.sh", SOLVE_SH)

    print(f"[dns-denoise] wrote {TASK_DIR}")
    print(f"  noise file: {noise_path.name}")
    print(f"  SNR: {snr_db:.2f} dB (seed=42)")
    print(f"  window: [{win_start_s:.2f}, {win_end_s:.2f}] s")
    print(f"  clip length: {n} samples / {n/16000:.2f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
