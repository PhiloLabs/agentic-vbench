#!/usr/bin/env python3
"""Generate `exp-dereverb-task01`.

SNL Elon Musk cold open (clip 5-40s) convolved with a synthetic shoebox
RIR. RT60 drawn from Uniform(0.2, 1.5) s under seed=42; absorption +
max_order computed via `pra.inverse_sabine(target_rt60, room_dims)`.

Since RIR convolution can't be windowed in isolation (every output sample
depends on history), we splice the fully-reverberant stream with the clean
stream using a 50 ms equal-power crossfade at each window boundary
(Option B): the in-window region is fully reverberant, the out-of-window
region is byte-identical to clean.
"""
from __future__ import annotations

import json
import shutil
import stat
import sys
from pathlib import Path

import numpy as np
import pyroomacoustics as pra
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _audio_window import pick_window, equal_power_crossfade_splice  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CLIP = ROOT / "clips" / "03-snl.wav"
TASK_DIR = ROOT / "tasks" / "repair_v4" / "exp-dereverb-task01"
JUDGE_SRC = Path(__file__).resolve().parent / "_judges" / "dereverb.py"

SEED = 42
WINDOW_S = 10.0
ROOM_DIMS = [6.0, 4.0, 3.0]
SOURCE_POS = [2.0, 3.0, 1.5]
MIC_POS = [4.0, 2.0, 1.5]

TASK_TOML = """\
version = "1.0"

[task]
name = "agentic-vbench/exp-dereverb-task01"

[metadata]
difficulty = "medium"
category = "audio-repair"
tags = ["dereverberation", "speech-enhancement", "pyroomacoustics", "experiment"]
source = "SNL 'Elon Musk Cold Open' studio speech (clip 5-40s)"
corruption = "shoebox RIR convolve, target_rt60={rt60:.3f} s, abs={absorption:.4f}, max_order={max_order}, room=6x4x3 m (seed=42)"

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
        g++ \\
        python3-dev \\
        libsndfile1 \\
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
"""

INSTRUCTION_MD = """\
# Speech Dereverberation Task

A reverberant 16 kHz mono speech recording is at
`/workspace/materials/noisy.wav` (~35 seconds, 16-bit PCM). A clean
studio narration has been convolved with a synthetic shoebox room
impulse response (RT60 ~ Uniform(0.2, 1.5) s).

## Your job

Produce a dereverberated version at **`/workspace/output/enhanced.wav`**.

## Output format

- Sample rate: **16000 Hz**
- Channels: **mono**
- Bit depth: **16-bit PCM**
- Length: **same number of samples** as the input. (The judge will
  truncate to the shorter of the two if you over-pad.)

## Scoring

    reward = 0.5 * clip01(SRMR / 8) + 0.5 * clip01((PESQ_wb - 1) / 3.5)

Composite reward in `[0, 1]`. Passthrough scores ~0.30-0.40. A
classical Wiener / WPE-style filter should reach ~0.40-0.50. SOTA
neural dereverb clears 0.6+.

## Notes

- `ffmpeg` is on `PATH`. Container has internet for pip installs.
- Useful libraries: `scipy.signal.wiener`, `nara_wpe`, or neural
  models from `speechbrain` / `asteroid`.
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
    "numpy<3" "scipy<2" "soundfile==0.13.*" "pesq==0.0.4" "pystoi==0.4.*" \\
    "pysepm @ git+https://github.com/schmiph2/pysepm.git" \\
    "gammatone @ git+https://github.com/detly/gammatone.git" "srmrpy==1.0"
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

# Window-aware v3 judge lives in scripts/_judges/dereverb.py.

SOLVE_SH = """\
#!/bin/bash
# Reference solver: passthrough. scipy.signal.wiener was empirically
# worse than passthrough on this RT60=0.69s instance (0.09 vs 0.12);
# passthrough is the honest baseline. True dereverb requires WPE / a
# neural model. Calibrated target: ~0.10-0.30.
set -euo pipefail
mkdir -p /workspace/output
cp /workspace/materials/noisy.wav /workspace/output/enhanced.wav
echo "ref-solver: passthrough"
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

    target_rt60 = float(np.random.uniform(0.2, 1.5))
    absorption, max_order = pra.inverse_sabine(target_rt60, ROOM_DIMS)
    absorption = float(absorption)
    max_order = int(max_order)

    room = pra.ShoeBox(
        ROOM_DIMS,
        fs=16000,
        materials=pra.Material(absorption),
        max_order=max_order,
    )
    room.add_source(SOURCE_POS, signal=speech)
    room.add_microphone(MIC_POS)
    room.simulate()
    reverberant = np.asarray(room.mic_array.signals[0], dtype=np.float32)
    # Trim to clean length so judge length-alignment is trivial.
    if len(reverberant) >= n:
        reverberant = reverberant[:n]
    else:
        pad = np.zeros(n - len(reverberant), dtype=np.float32)
        reverberant = np.concatenate([reverberant, pad])
    peak = float(np.max(np.abs(reverberant)))
    if peak > 0.99:
        reverberant = reverberant / peak * 0.99

    # Splice corrupted in-window with clean out-of-window via 50 ms
    # equal-power crossfade. Out-window samples remain byte-identical
    # to clean.
    win_start_s, win_end_s = pick_window(speech, 16000, WINDOW_S)
    noisy = equal_power_crossfade_splice(
        reverberant, speech, win_start_s, win_end_s, 16000
    )

    judge_src = JUDGE_SRC.read_text()
    if not judge_src.strip():
        print(f"empty JUDGE_SRC at {JUDGE_SRC}", file=sys.stderr)
        return 1

    if TASK_DIR.exists():
        shutil.rmtree(TASK_DIR)
    (TASK_DIR / "environment").mkdir(parents=True)
    (TASK_DIR / "environment" / "Dockerfile").write_text(DOCKERFILE)
    (TASK_DIR / "task.toml").write_text(TASK_TOML.format(
        rt60=target_rt60, absorption=absorption, max_order=max_order
    ))

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

    print(f"[dereverb] wrote {TASK_DIR}")
    print(f"  RT60: {target_rt60:.3f} s, absorption: {absorption:.4f}, max_order: {max_order}")
    print(f"  room: {ROOM_DIMS} m, src: {SOURCE_POS}, mic: {MIC_POS}")
    print(f"  window: [{win_start_s:.2f}, {win_end_s:.2f}] s")
    print(f"  clip length: {n} samples / {n/16000:.2f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
