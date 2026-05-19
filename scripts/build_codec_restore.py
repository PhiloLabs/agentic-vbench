#!/usr/bin/env python3
"""Generate `exp-codec-restore-task01`.

Visit Korea voiceover (clip 0-30s) encoded through Opus @ 12 kbps then
decoded back to PCM. Fixed codec tier (seed=42 but deterministic anyway).

Opus roundtrip can't be windowed in isolation. Apply Option B: encode the
full clip, then splice corrupted in-window with clean out-of-window via
a 50 ms equal-power crossfade. Out-window samples are byte-identical to
clean so over-enhancement of clean regions is detected.
"""
from __future__ import annotations

import json
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _audio_window import pick_window, equal_power_crossfade_splice  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CLIP = ROOT / "clips" / "05-korea.wav"
TASK_DIR = ROOT / "tasks" / "agentic_vbench_repair" / "exp-codec-restore-task01"
JUDGE_SRC = Path(__file__).resolve().parent / "_judges" / "codec_restore.py"

SEED = 42
WINDOW_S = 10.0
CODEC_TIER = "opus_12k"
OPUS_BITRATE = "12k"

TASK_TOML = """\
version = "1.0"

[task]
name = "agentic-vbench/exp-codec-restore-task01"

[metadata]
difficulty = "medium"
category = "audio-repair"
tags = ["codec-restoration", "bandwidth-extension", "opus", "experiment"]
source = "Visit Korea travel voiceover (clip 0-30s)"
corruption = "ffmpeg roundtrip: pcm_s16le -> libopus @ 12kbps -> pcm_s16le (seed=42; tier={tier})"

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
        libsndfile1 \\
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
"""

INSTRUCTION_MD = """\
# Codec Restoration Task

A codec-degraded 16 kHz mono speech recording is at
`/workspace/materials/noisy.wav` (~30 seconds, 16-bit PCM). The audio
has been passed through an ffmpeg Opus encode @ 12 kbps and decoded
back to PCM, destroying high-frequency detail (especially in the
4-8 kHz band where Opus 12k aggressively cuts).

## Your job

Produce a restored version at **`/workspace/output/enhanced.wav`** that
recovers fidelity (especially the high band).

## Output format

- Sample rate: **16000 Hz**
- Channels: **mono**
- Bit depth: **16-bit PCM**
- Length: **same number of samples** as the input.

## Scoring

    LSD = mean log-spectral distance between agent and reference,
          measured on the 4-8 kHz band (where Opus 12k loses most).
    reward = 0.5 * clip01((PESQ_wb - 1) / 3.5)
           + 0.5 * clip01(1 - LSD / 5)

Composite reward in `[0, 1]`. Passthrough (decoded WAV without
restoration) scores ~0.40-0.55. A bandwidth-extension model can
clear 0.6+.

## Notes

- `ffmpeg` is on `PATH` with `libopus`. Container has internet for
  pip-installing restoration models.
- Useful: classical methods (HF re-synthesis via spectral folding,
  noise injection), or neural models like `NU-Wave` / `NVSR` /
  `AudioSR`.
- Stay inside `/workspace/`. Do not search the web for the original.
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
    "librosa==0.11.*" "onnxruntime"
python3 /tests/judge.py \\
        --enhanced /workspace/output/enhanced.wav \\
        --clean /tests/clean.wav \\
        --dnsmos-model /tests/sig_bak_ovr.onnx \\
        --window-json /tests/window.json \\
        --reward-json /logs/verifier/reward.json \\
        --reward-txt /logs/verifier/reward.txt
"""

# Window-aware v3 judge lives in scripts/_judges/codec_restore.py.

SOLVE_SH = """\
#!/bin/bash
# Reference solver: passthrough (copy noisy.wav -> enhanced.wav). This
# represents "do nothing"; codec-restoration genuinely needs a
# bandwidth-extension model to score well. Target: ~0.40-0.55.
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
    np.random.seed(SEED)  # not used in the corruption draw, but honored

    # Probe clean length for end-of-pipeline length alignment.
    clean, sr = sf.read(str(CLIP), always_2d=False)
    if sr != 16000:
        print(f"unexpected sr {sr}", file=sys.stderr)
        return 1
    clean = clean.astype(np.float32)
    n = len(clean)

    if TASK_DIR.exists():
        shutil.rmtree(TASK_DIR)
    TASK_DIR.mkdir(parents=True)

    # ffmpeg roundtrip: clean.wav -> opus 12k -> pcm s16le mono 16k
    tmp_opus = TASK_DIR / "_tmp.opus"
    tmp_wav = TASK_DIR / "_tmp_decoded.wav"
    encode_cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(CLIP),
        "-c:a", "libopus", "-b:a", OPUS_BITRATE,
        "-ac", "1", "-ar", "16000",
        str(tmp_opus),
    ]
    decode_cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(tmp_opus),
        "-c:a", "pcm_s16le", "-ac", "1", "-ar", "16000",
        str(tmp_wav),
    ]
    subprocess.run(encode_cmd, check=True)
    subprocess.run(decode_cmd, check=True)

    degraded, sr_d = sf.read(str(tmp_wav), always_2d=False)
    if sr_d != 16000:
        print(f"degraded sr {sr_d} != 16000", file=sys.stderr)
        return 1
    degraded = degraded.astype(np.float32)
    # Trim or pad to original length so judge length-alignment is trivial.
    if len(degraded) >= n:
        degraded = degraded[:n]
    else:
        pad = np.zeros(n - len(degraded), dtype=np.float32)
        degraded = np.concatenate([degraded, pad])
    tmp_opus.unlink(missing_ok=True)
    tmp_wav.unlink(missing_ok=True)

    # Splice corrupted (in-window) with clean (out-of-window) via 50 ms
    # equal-power crossfade. Out-window samples remain byte-identical to clean.
    win_start_s, win_end_s = pick_window(clean, 16000, WINDOW_S)
    noisy = equal_power_crossfade_splice(
        degraded, clean, win_start_s, win_end_s, 16000
    )

    judge_src = JUDGE_SRC.read_text()
    if not judge_src.strip():
        print(f"empty JUDGE_SRC at {JUDGE_SRC}", file=sys.stderr)
        return 1

    (TASK_DIR / "environment").mkdir(parents=True)
    (TASK_DIR / "environment" / "Dockerfile").write_text(DOCKERFILE)
    (TASK_DIR / "task.toml").write_text(TASK_TOML.format(tier=CODEC_TIER))

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
    sf.write(tests / "clean.wav", clean, 16000, subtype="PCM_16")
    (tests / "window.json").write_text(json.dumps({
        "window_start_s": float(win_start_s),
        "window_end_s": float(win_end_s),
    }))
    dnsmos = ROOT / ".models" / "sig_bak_ovr.onnx"
    if dnsmos.exists():
        (tests / "sig_bak_ovr.onnx").write_bytes(dnsmos.read_bytes())

    _write_exec(step_dir / "solution" / "solve.sh", SOLVE_SH)

    print(f"[codec-restore] wrote {TASK_DIR}")
    print(f"  codec tier: {CODEC_TIER} (libopus @ {OPUS_BITRATE})")
    print(f"  window: [{win_start_s:.2f}, {win_end_s:.2f}] s")
    print(f"  clip length: {n} samples / {n/16000:.2f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
