#!/usr/bin/env python3
"""Judge for exp-dereverb-task01 (window-aware v3).

Paper-standard metric battery (REVERB Challenge 2014; Kinoshita et al.):

  - PESQ-wb      (intrusive, wideband, 16 kHz)
  - CD           (cepstrum distance, lower is better)
  - LLR          (log-likelihood ratio, diagnostic)
  - fwSegSNR     (frequency-weighted segmental SNR, diagnostic)
  - STOI         (short-time objective intelligibility)
  - SRMR         (diagnostic only, not in composite)

In-window composite (REVERB-Challenge style):

  in_window_reward = 0.4 * clip01((PESQ_wb - 1.3) / 3.2)
                   + 0.3 * clip01((STOI - 0.20) / 0.80)
                   + 0.3 * clip01(1 - CD/5)

(Per-task LO anchors: PESQ=1.3, STOI=0.20, CD divisor=5 —
derived from the broken passthrough measurements.)

Out-of-window check (catches over-enhancement of clean regions):

  out_window_reward = clip01((SI-SDR_out + 5) / 30)

Final reward:

  reward = 0.90 * in_window_reward + 0.10 * out_window_reward
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
IN_WEIGHT = 0.90
OUT_WEIGHT = 0.10


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _si_sdr(ref: np.ndarray, est: np.ndarray) -> float:
    ref = ref - ref.mean()
    est = est - est.mean()
    a = float(np.dot(est, ref) / (np.dot(ref, ref) + 1e-12))
    target = a * ref
    err = est - target
    num = float(np.dot(target, target) + 1e-12)
    den = float(np.dot(err, err) + 1e-12)
    return 10.0 * np.log10(num / den)


def _read_mono(path: Path):
    data, sr = sf.read(str(path), always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    return data.astype(np.float32), int(sr)


def _zero(reason: str) -> dict:
    return {"reward": 0.0, "details": {"reason": reason}}


def _score_in_window(est: np.ndarray, ref: np.ndarray) -> tuple[float, dict]:
    import pysepm
    details: dict = {}
    pesq_wb = float(pesq(16000, ref, est, "wb"))
    details["pesq_wb"] = pesq_wb
    stoi_v = float(stoi(ref, est, 16000, extended=False))
    details["stoi"] = stoi_v
    est_f = est.astype(np.float64)
    ref_f = ref.astype(np.float64)
    cd_val = float(pysepm.cepstrum_distance(ref_f, est_f, 16000))
    details["cd"] = cd_val
    try:
        details["llr"] = float(pysepm.llr(ref_f, est_f, 16000))
    except Exception as e:
        details["llr"] = float("nan")
        details["llr_error"] = str(e)
    try:
        details["fwsegsnr_db"] = float(pysepm.fwSNRseg(ref_f, est_f, 16000))
    except Exception as e:
        details["fwsegsnr_db"] = float("nan")
        details["fwsegsnr_error"] = str(e)
    try:
        from srmrpy import srmr
        srmr_val, _ = srmr(est, 16000)
        details["srmr"] = float(srmr_val)
    except Exception as e:
        details["srmr_error"] = str(e)

    pesq_n = _clip01((pesq_wb - 1.3) / 3.2)
    stoi_n = _clip01((stoi_v - 0.20) / 0.80)
    cd_n = _clip01(1.0 - cd_val / 5.0)
    reward = 0.4 * pesq_n + 0.3 * stoi_n + 0.3 * cd_n
    details.update({
        "pesq_n": pesq_n,
        "stoi_n": stoi_n,
        "cd_n": cd_n,
        "composite_formula": (
            "0.4*clip01((PESQ_wb-1.3)/3.2) + 0.3*clip01((STOI-0.20)/0.80) + 0.3*clip01(1 - CD/5)"
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


def score(enhanced: Path, clean: Path,
          window_json: Path = WINDOW_JSON_PATH) -> dict:
    if not enhanced.exists():
        return _zero(f"enhanced.wav not found at {enhanced}")
    if not clean.exists():
        return _zero(f"clean.wav not found at {clean}")
    try:
        est, sr_e = _read_mono(enhanced)
        ref, sr_r = _read_mono(clean)
    except Exception as e:
        return _zero(f"failed to read audio: {e}")
    if sr_r != 16000 or sr_e != 16000:
        return _zero(f"sample rate mismatch enh={sr_e} clean={sr_r}")
    if len(est) == 0 or len(ref) == 0:
        return _zero("empty audio")

    n = min(len(est), len(ref))
    est, ref = est[:n], ref[:n]

    win = _load_window(window_json)
    if win is None:
        return _zero(f"window.json not found at {window_json}")
    win_s, win_e = win
    s0 = max(0, int(round(win_s * 16000)))
    s1 = min(n, int(round(win_e * 16000)))
    if s1 <= s0:
        return _zero(f"invalid window: {win_s}..{win_e}")

    try:
        in_reward, in_details = _score_in_window(est[s0:s1], ref[s0:s1])
    except Exception as e:
        return _zero(f"in-window scoring failed: {e}")
    out_est = np.concatenate([est[:s0], est[s1:]])
    out_ref = np.concatenate([ref[:s0], ref[s1:]])
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
    p.add_argument("--reward-json", required=True, type=Path)
    p.add_argument("--reward-txt", required=True, type=Path)
    p.add_argument("--window-json", default=WINDOW_JSON_PATH, type=Path)
    args = p.parse_args()
    result = score(args.enhanced, args.clean, args.window_json)
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps(result, indent=2))
    args.reward_txt.write_text(f"{result['reward']:.6f}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
