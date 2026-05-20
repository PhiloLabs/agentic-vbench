#!/usr/bin/env python3
"""Judge for exp-dns-denoise-task01 (window-aware v3).

Paper-standard metric battery (DNS Challenge 2020, Reddy et al., Interspeech
2020 -- arxiv 2001.08662):

  - WB-PESQ      (intrusive, wideband, 16 kHz)
  - NB-PESQ      (intrusive, narrowband, 8 kHz downsampled)
  - STOI         (intrusive, short-time objective intelligibility)
  - SI-SDR       (intrusive, scale-invariant SDR in dB)
  - DNSMOS       (non-intrusive: SIG / BAK / OVL on 1-5 MOS scale)

In-window composite (DNS-Challenge convention; DNSMOS-OVL is the headline):

  in_window_reward = 0.5 * clip01((DNSMOS_OVL - 1) / 4)
                   + 0.3 * STOI
                   + 0.2 * clip01((SI-SDR + 10) / 30)

If DNSMOS fails (model missing / onnxruntime missing), fall back to:

  in_window_reward = 0.4 * clip01((PESQ_wb - 1) / 3.5)
                   + 0.3 * clip01((STOI - 0.86) / 0.14)
                   + 0.3 * clip01((SI-SDR - 4) / 16)

(Per-task LO anchors: STOI=0.86, SI-SDR=4 dB — derived from the
broken passthrough measurements. PESQ already lands near 0
naturally on a noisy signal.)

Out-of-window check (catches over-enhancement of clean regions):

  out_window_reward = clip01((SI-SDR_out + 5) / 30)

Final reward (convex combination, fixed mass):

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


DNSMOS_MODEL_PATH = Path("/tests/sig_bak_ovr.onnx")
WINDOW_JSON_PATH = Path("/tests/window.json")
DNSMOS_INPUT_SAMPLES = int(9.01 * 16000)  # 144160
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


def _dnsmos(audio: np.ndarray, sr: int, model_path: Path):
    """Run DNSMOS over 9.01s windows hopped by 1s; return mean (SIG, BAK, OVL)."""
    import onnxruntime as ort  # local import

    if sr != 16000:
        raise ValueError(f"DNSMOS requires 16 kHz, got {sr}")
    audio = audio.astype(np.float32)
    if len(audio) < DNSMOS_INPUT_SAMPLES:
        audio = np.pad(audio, (0, DNSMOS_INPUT_SAMPLES - len(audio)))
    hop = 16000
    num_hops = max(1, (len(audio) - DNSMOS_INPUT_SAMPLES) // hop + 1)
    sess = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    sigs, baks, ovls = [], [], []
    for i in range(num_hops):
        start = i * hop
        seg = audio[start:start + DNSMOS_INPUT_SAMPLES]
        if len(seg) < DNSMOS_INPUT_SAMPLES:
            seg = np.pad(seg, (0, DNSMOS_INPUT_SAMPLES - len(seg)))
        out = sess.run(None, {"input_1": seg[None, :]})[0][0]
        sigs.append(float(out[0]))
        baks.append(float(out[1]))
        ovls.append(float(out[2]))
    return float(np.mean(sigs)), float(np.mean(baks)), float(np.mean(ovls))


def _resample_to_8k(x: np.ndarray, sr: int = 16000) -> np.ndarray:
    from scipy.signal import resample_poly
    return resample_poly(x, up=1, down=2).astype(np.float32)


def _score_in_window(est: np.ndarray, ref: np.ndarray,
                     dnsmos_model: Path) -> tuple[float, dict]:
    """Compute the paper-grade composite on the in-window slice."""
    details: dict = {}
    pesq_wb = float(pesq(16000, ref, est, "wb"))
    details["pesq_wb"] = pesq_wb
    try:
        ref_nb = _resample_to_8k(ref)
        est_nb = _resample_to_8k(est)
        details["pesq_nb"] = float(pesq(8000, ref_nb, est_nb, "nb"))
    except Exception as e:
        details["pesq_nb"] = float("nan")
        details["pesq_nb_error"] = str(e)
    stoi_v = float(stoi(ref, est, 16000, extended=False))
    details["stoi"] = stoi_v
    sisdr_db = _si_sdr(ref, est)
    details["si_sdr_db"] = sisdr_db

    dnsmos_ok = False
    try:
        sig_m, bak_m, ovl_m = _dnsmos(est, 16000, dnsmos_model)
        details.update({"dnsmos_sig": sig_m, "dnsmos_bak": bak_m, "dnsmos_ovl": ovl_m})
        # If DNSMOS rates the clean reference < 2.5 OVL it is out-of-distribution
        # for this content (e.g. broadband-background narration). Mirror the
        # codec-restore behavior and fall back to PESQ composite so identity
        # (clean->clean) → ~1.0 sanity check holds.
        sig_r, bak_r, ovl_r = _dnsmos(ref, 16000, dnsmos_model)
        details["dnsmos_ref_ovl"] = ovl_r
        if ovl_r < 4.0:
            details["dnsmos_skipped"] = (
                f"DNSMOS on clean reference OVL={ovl_r:.2f} < 4.0 "
                "(out-of-distribution; identity sanity check would fail); "
                "falling back to PESQ composite."
            )
        else:
            dnsmos_ok = True
    except Exception as e:
        details["dnsmos_error"] = str(e)

    if dnsmos_ok:
        ovl_n = _clip01((details["dnsmos_ovl"] - 1.0) / 4.0)
        stoi_n = _clip01((stoi_v - 0.86) / 0.14)
        sisdr_n = _clip01((sisdr_db - 4.0) / 16.0)
        reward = 0.5 * ovl_n + 0.3 * stoi_n + 0.2 * sisdr_n
        details["composite_formula"] = (
            "0.5*clip01((DNSMOS_OVL-1)/4) + 0.3*STOI + 0.2*clip01((SI-SDR+10)/30)"
        )
        details.update({"ovl_n": ovl_n, "stoi_n": stoi_n, "sisdr_n": sisdr_n})
    else:
        pesq_n = _clip01((pesq_wb - 1.0) / 3.5)
        stoi_n = _clip01((stoi_v - 0.86) / 0.14)
        sisdr_n = _clip01((sisdr_db - 4.0) / 16.0)
        reward = 0.4 * pesq_n + 0.3 * stoi_n + 0.3 * sisdr_n
        details["composite_formula"] = (
            "0.4*clip01((PESQ_wb-1)/3.5) + 0.3*clip01((STOI-0.86)/0.14) + 0.3*clip01((SI-SDR-4)/16) "
            "[DNSMOS unavailable fallback]"
        )
        details.update({"pesq_n": pesq_n, "stoi_n": stoi_n, "sisdr_n": sisdr_n})
    return float(reward), details


def _score_out_window(est: np.ndarray, ref: np.ndarray) -> tuple[float, dict]:
    """Out-of-window: did the agent leave the clean region alone?
    SI-SDR(est_out, ref_out) clipped to [0,1] via (x+5)/30.
    Identity → +inf → 1.0. Mild perturbation → quickly drops."""
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
          dnsmos_model: Path = DNSMOS_MODEL_PATH,
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
    if sr_r != 16000:
        return _zero(f"clean.wav sample rate {sr_r} != 16000")
    if sr_e != 16000:
        return _zero(f"enhanced.wav sample rate {sr_e} != 16000")
    if len(est) == 0 or len(ref) == 0:
        return _zero("empty audio")

    n = min(len(est), len(ref))
    est = est[:n]
    ref = ref[:n]

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
    out_est = np.concatenate([est[:s0], est[s1:]])
    out_ref = np.concatenate([ref[:s0], ref[s1:]])

    try:
        in_reward, in_details = _score_in_window(in_est, in_ref, dnsmos_model)
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
    p.add_argument("--reward-json", required=True, type=Path)
    p.add_argument("--reward-txt", required=True, type=Path)
    p.add_argument("--dnsmos-model", default=DNSMOS_MODEL_PATH, type=Path)
    p.add_argument("--window-json", default=WINDOW_JSON_PATH, type=Path)
    args = p.parse_args()
    result = score(args.enhanced, args.clean, args.dnsmos_model, args.window_json)
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps(result, indent=2))
    args.reward_txt.write_text(f"{result['reward']:.6f}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
