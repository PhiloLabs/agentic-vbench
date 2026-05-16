#!/usr/bin/env python3
"""Fetch noise pools used by build_dns_denoise.py and build_voicebank_denoise.py.

DNS pool: derive noise = noisy - clean from a handful of rows of
`nkdem/DNS-Challenge-2020-DevTest-16k`. Save under experiment/noise/dns/*.wav.

DEMAND pool: pull a handful of (noisy, clean) pairs from
`JacobLinCool/VoiceBank-DEMAND-16k`, derive noise = noisy - clean, save under
experiment/noise/demand/*.wav. Filename encodes the original VCTK id so the
generator can reuse it as a noise source.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from datasets import Audio, load_dataset

ROOT = Path(__file__).resolve().parents[1]
DNS_DIR = ROOT / "noise" / "dns"
DEMAND_DIR = ROOT / "noise" / "demand"


def _read_bytes(b: bytes) -> tuple[np.ndarray, int]:
    data, sr = sf.read(io.BytesIO(b), always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data.astype(np.float32), int(sr)


def fetch_dns(n: int = 20) -> int:
    DNS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[dns] loading nkdem/DNS-Challenge-2020-DevTest-16k ...")
    ds = load_dataset("nkdem/DNS-Challenge-2020-DevTest-16k", split="synthetic_no_reverb")
    print(f"[dns] {len(ds)} rows; deriving noise = noisy - clean for first {n}")
    written = 0
    for i, row in enumerate(ds):
        if written >= n:
            break
        try:
            noisy, sr_n = _read_bytes(row["noisy"]["bytes"])
            clean, sr_c = _read_bytes(row["clean"]["bytes"])
        except Exception as e:
            print(f"  skip row {i}: {e}", file=sys.stderr)
            continue
        if sr_n != 16000 or sr_c != 16000:
            continue
        m = min(len(noisy), len(clean))
        noise = noisy[:m] - clean[:m]
        out = DNS_DIR / f"dns_{int(row['fileid']):04d}.wav"
        sf.write(out, noise, 16000, subtype="PCM_16")
        written += 1
        if written % 5 == 0:
            print(f"  wrote {written}/{n}")
    print(f"[dns] done: {written} wav files in {DNS_DIR}")
    return written


def fetch_demand(n: int = 20) -> int:
    DEMAND_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[demand] loading JacobLinCool/VoiceBank-DEMAND-16k ...")
    ds = load_dataset("JacobLinCool/VoiceBank-DEMAND-16k", split="test")
    ds = ds.cast_column("clean", Audio(decode=False)).cast_column("noisy", Audio(decode=False))
    print(f"[demand] {len(ds)} rows; deriving noise = noisy - clean for first {n}")
    written = 0
    for i, row in enumerate(ds):
        if written >= n:
            break
        try:
            noisy, sr_n = _read_bytes(row["noisy"]["bytes"])
            clean, sr_c = _read_bytes(row["clean"]["bytes"])
        except Exception as e:
            print(f"  skip row {i}: {e}", file=sys.stderr)
            continue
        if sr_n != 16000 or sr_c != 16000:
            continue
        m = min(len(noisy), len(clean))
        noise = noisy[:m] - clean[:m]
        out = DEMAND_DIR / f"demand_{i:04d}_{row['id']}.wav"
        sf.write(out, noise, 16000, subtype="PCM_16")
        written += 1
        if written % 5 == 0:
            print(f"  wrote {written}/{n}")
    print(f"[demand] done: {written} wav files in {DEMAND_DIR}")
    return written


if __name__ == "__main__":
    fetch_dns(20)
    fetch_demand(20)
