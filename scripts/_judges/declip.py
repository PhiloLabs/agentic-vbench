#!/usr/bin/env python3
"""Judge for exp-declip-task01 (window-aware v3).

Paper-standard metric battery (URGENT Challenge 2024 + Speech Declipping
Transformer 2024):

  - PESQ-wb         (intrusive, wideband, 16 kHz)
  - STOI            (short-time objective intelligibility)
  - ESTOI           (extended STOI; pystoi.stoi with extended=True)
  - SI-SDR          (full-signal scale-invariant SDR in dB)
  - masked_SI_SDR   (SI-SDR computed only over the clipped-region samples)

In-window composite (URGENT 2024 + SDT 2024 convention):

  in_window_reward = 0.5 * clip01((masked_SI_SDR + 5) / 25)
                   + 0.3 * ESTOI
                   + 0.2 * clip01((PESQ_wb - 1) / 3.5)

Out-of-window check (catches over-enhancement of clean regions):

  out_window_reward = clip01((SI-SDR_out + 5) / 30)

Final reward:

  reward = 0.85 * in_window_reward + 0.15 * out_window_reward
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from pesq import pesq
from pystoi import stoi


WINDOW_JSON_PATH = Path("/tests/window.json")
IN_WEIGHT = 0.85
OUT_WEIGHT = 0.15


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _read_mono(path: Path):
    data, sr = sf.read(str(path), always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data.astype(np.float32), int(sr)


def _zero(reason: str) -> dict:
    return {"reward": 0.0, "details": {"reason": reason}}


def _si_sdr(ref: np.ndarray, est: np.ndarray) -> float:
    ref = ref - ref.mean()
    est = est - est.mean()
    a = float(np.dot(est, ref) / (np.dot(ref, ref) + 1e-12))
    target = a * ref
    err = est - target
    num = float(np.dot(target, target) + 1e-12)
    den = float(np.dot(err, err) + 1e-12)
    return 10.0 * np.log10(num / den)


def _masked_si_sdr(ref: np.ndarray, est: np.ndarray, mask: np.ndarray) -> float:
    return _si_sdr(ref[mask], est[mask])


def _score_in_window(est: np.ndarray, ref: np.ndarray,
                     mask: np.ndarray) -> tuple[float, dict]:
    details: dict = {}
    pesq_wb = float(pesq(16000, ref, est, "wb"))
    details["pesq_wb"] = pesq_wb
    stoi_v = float(stoi(ref, est, 16000, extended=False))
    details["stoi"] = stoi_v
    estoi_v = float(stoi(ref, est, 16000, extended=True))
    details["estoi"] = estoi_v
    sisdr_full = _si_sdr(ref, est)
    details["si_sdr_db"] = sisdr_full
    n_clipped = int(mask.sum())
    details["n_clipped_samples_in_window"] = n_clipped
    if n_clipped == 0:
        # Window has no clipped samples (build mistake / mask shifted);
        # fall back to full SI-SDR over the in-window slice.
        msisdr = sisdr_full
        details["masked_si_sdr_fallback"] = "no clipped samples in window"
    else:
        msisdr = _masked_si_sdr(ref, est, mask)
    details["masked_si_sdr_db"] = msisdr

    msisdr_n = _clip01((msisdr + 5.0) / 25.0)
    estoi_n = _clip01(estoi_v)
    pesq_n = _clip01((pesq_wb - 1.0) / 3.5)
    reward = 0.5 * msisdr_n + 0.3 * estoi_n + 0.2 * pesq_n
    details.update({
        "msisdr_n": msisdr_n,
        "estoi_n": estoi_n,
        "pesq_n": pesq_n,
        "composite_formula": (
            "0.5*clip01((masked_SI_SDR+5)/25) + 0.3*ESTOI "
            "+ 0.2*clip01((PESQ_wb-1)/3.5)"
        ),
    })
    return float(reward), details


def _score_out_window(est: np.ndarray, ref: np.ndarray) -> tuple[float, dict]:
    if len(ref) == 0:
        return 1.0, {"out_si_sdr_db": float("inf"), "out_n_samples": 0,
                     "note": "no out-of-window samples"}
    sisdr = _si_sdr(ref, est)
    reward = _clip01((sisdr + 5.0) / 30.0)
    return float(reward), {"out_si_sdr_db": float(sisdr),
                           "out_n_samples": int(len(ref))}


def _load_window(window_json: Path) -> tuple[float, float]:
    if not window_json.exists():
        return None
    obj = json.loads(window_json.read_text())
    return float(obj["window_start_s"]), float(obj["window_end_s"])


def score(enhanced: Path, clean: Path, clip_mask_path: Path,
          window_json: Path = WINDOW_JSON_PATH) -> dict:
    if not enhanced.exists():
        return _zero(f"enhanced.wav not found at {enhanced}")
    if not clean.exists():
        return _zero(f"clean.wav not found at {clean}")
    if not clip_mask_path.exists():
        return _zero(f"clip_mask.npy not found at {clip_mask_path}")

    try:
        est, sr_e = _read_mono(enhanced)
        ref, sr_r = _read_mono(clean)
        mask = np.load(str(clip_mask_path)).astype(bool)
    except Exception as e:
        return _zero(f"failed to read inputs: {e}")
    if sr_r != 16000 or sr_e != 16000:
        return _zero(f"sample rate mismatch enh={sr_e} clean={sr_r}")

    n = min(len(est), len(ref), len(mask))
    if n == 0:
        return _zero("empty audio")
    est, ref, mask = est[:n], ref[:n], mask[:n]

    win = _load_window(window_json)
    if win is None:
        return _zero(f"window.json not found at {window_json}")
    win_s, win_e = win
    s0 = max(0, int(round(win_s * 16000)))
    s1 = min(n, int(round(win_e * 16000)))
    if s1 <= s0:
        return _zero(f"invalid window: {win_s}..{win_e}")

    in_est = est[s0:s1]
    in_ref = ref[s0:s1]
    in_mask = mask[s0:s1]
    out_est = np.concatenate([est[:s0], est[s1:]])
    out_ref = np.concatenate([ref[:s0], ref[s1:]])

    try:
        in_reward, in_details = _score_in_window(in_est, in_ref, in_mask)
    except Exception as e:
        return _zero(f"in-window scoring failed: {e}")
    try:
        out_reward, out_details = _score_out_window(out_est, out_ref)
    except Exception as e:
        return _zero(f"out-window scoring failed: {e}")

    reward = IN_WEIGHT * in_reward + OUT_WEIGHT * out_reward
    return {
        "reward": float(reward),
        "in_window_reward": float(in_reward),
        "out_window_reward": float(out_reward),
        "window": [float(win_s), float(win_e)],
        "details": {
            "reason": "ok",
            "n_samples_scored": int(n),
            "in_window_samples": int(s1 - s0),
            "out_window_samples": int(len(out_est)),
            "weights": {"in": IN_WEIGHT, "out": OUT_WEIGHT},
            "in_window": in_details,
            "out_window": out_details,
        },
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--enhanced", required=True, type=Path)
    p.add_argument("--clean", required=True, type=Path)
    p.add_argument("--clip-mask", required=True, type=Path)
    p.add_argument("--reward-json", required=True, type=Path)
    p.add_argument("--reward-txt", required=True, type=Path)
    p.add_argument("--window-json", default=WINDOW_JSON_PATH, type=Path)
    args = p.parse_args()
    result = score(args.enhanced, args.clean, args.clip_mask, args.window_json)
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps(result, indent=2))
    args.reward_txt.write_text(f"{result['reward']:.6f}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
