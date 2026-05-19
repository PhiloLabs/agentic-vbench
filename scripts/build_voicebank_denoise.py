#!/usr/bin/env python3
"""Generate `exp-voicebank-denoise-task01`.

Reuters anchor read (clip 5-40s) + DEMAND-derived noise at SNR ∈ {0, 5, 10, 15} dB
(deterministic choice via seed=42). Noise mixed only inside a centered 10 s
window so the judge can score over-enhancement on the out-of-window region.
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
CLIP = ROOT / "clips" / "02-reuters.wav"
NOISE_DIR = ROOT / "noise" / "demand"
TASK_DIR = ROOT / "tasks" / "repair_v4" / "exp-voicebank-denoise-task01"
JUDGE_SRC = Path(__file__).resolve().parent / "_judges" / "voicebank_denoise.py"

SEED = 42
WINDOW_S = 10.0

TASK_TOML = """\
version = "1.0"

[task]
name = "agentic-vbench/exp-voicebank-denoise-task01"

[metadata]
difficulty = "medium"
category = "audio-repair"
tags = ["speech-enhancement", "denoising", "voicebank-demand", "experiment"]
source = "Reuters anchor read (clip 5-40s) + VoiceBank-DEMAND-derived noise"
corruption = "additive DEMAND-derived noise at SNR={snr_db:d} dB (seed=42)"

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
# Speech Denoising Task (VoiceBank-DEMAND-style)

A noisy 16 kHz mono speech recording is at
`/workspace/materials/noisy.wav` (~35 seconds, 16-bit PCM). Background
noise drawn from a DEMAND-style environmental noise pool (cafeteria /
office / kitchen / car / public square) has been mixed on top of a clean
anchor read at SNR in {0, 5, 10, 15} dB.

## Your job

Produce a denoised version at **`/workspace/output/enhanced.wav`**.

## Output format

- Sample rate: **16000 Hz**
- Channels: **mono**
- Bit depth: **16-bit PCM**
- Length: **same number of samples** as the input.

## Scoring

    reward = 0.4 * clip01((PESQ_wb - 1) / 3.5)
           + 0.3 * STOI
           + 0.3 * clip01((SI-SDR + 10) / 30)

Composite reward in `[0, 1]`. Passthrough scores ~0.40. Spectral
gating ~0.60. A neural denoiser (DeepFilterNet, Demucs) should clear 0.75+.

## Notes

- `ffmpeg` is on `PATH`. The container has internet.
- Stay inside `/workspace/`. Use `/workspace/work/` for scratch,
  `/workspace/output/` only for the final `enhanced.wav`.
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
    "numpy<3" "scipy<2" "soundfile==0.13.*" "pesq==0.0.4" \\
    "pysepm @ git+https://github.com/schmiph2/pysepm.git"
# Patch pysepm's np.NaN reference for NumPy 2.x compatibility.
python3 - <<'PY'
from pathlib import Path
p = Path("/usr/local/lib/python3.12/site-packages/pysepm/qualityMeasures.py")
if p.exists():
    s = p.read_text()
    if "np.NaN" in s:
        p.write_text(s.replace("np.NaN", "np.nan"))
PY
python3 /tests/judge.py \\
        --enhanced /workspace/output/enhanced.wav \\
        --clean /tests/clean.wav \\
        --window-json /tests/window.json \\
        --reward-json /logs/verifier/reward.json \\
        --reward-txt /logs/verifier/reward.txt
"""

# Window-aware v3 judge lives in scripts/_judges/voicebank_denoise.py.

SOLVE_SH = """\
#!/bin/bash
# Reference solver: noisereduce spectral gating. Calibrated to score ~0.55-0.75.
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
        print(f"missing clip: {CLIP}", file=sys.stderr)
        return 1
    noise_files = sorted(NOISE_DIR.glob("*.wav"))
    if not noise_files:
        print(f"no noise files under {NOISE_DIR}", file=sys.stderr)
        return 1

    np.random.seed(SEED)
    speech, sr = sf.read(str(CLIP), always_2d=False)
    if sr != 16000:
        print(f"unexpected sr {sr}", file=sys.stderr)
        return 1
    speech = speech.astype(np.float32)
    n = len(speech)

    snr_choices = [0, 5, 10, 15]
    snr_db = int(snr_choices[int(np.random.randint(0, len(snr_choices)))])
    noise_path = noise_files[int(np.random.randint(0, len(noise_files)))]

    noise, sr_n = sf.read(str(noise_path), always_2d=False)
    if sr_n != 16000:
        print(f"noise sr {sr_n} != 16000", file=sys.stderr)
        return 1
    noise = noise.astype(np.float32)
    noise = _tile_to_length(noise, n)

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
        noisy[s0:s1] *= 0.99 / peak

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

    _write_exec(step_dir / "solution" / "solve.sh", SOLVE_SH)

    print(f"[voicebank-denoise] wrote {TASK_DIR}")
    print(f"  noise file: {noise_path.name}")
    print(f"  SNR: {snr_db} dB (seed=42)")
    print(f"  window: [{win_start_s:.2f}, {win_end_s:.2f}] s")
    print(f"  clip length: {n} samples / {n/16000:.2f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
