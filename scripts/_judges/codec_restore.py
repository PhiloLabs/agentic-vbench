#!/usr/bin/env python3
"""Judge for exp-codec-restore-task01 (window-aware v3).

Paper-standard metric battery (Codec-SUPERB SLT 2024 + neural-codec /
bandwidth-extension literature):

  - PESQ-wb         (intrusive, wideband, 16 kHz)
  - STOI            (short-time objective intelligibility)
  - LSD_full        (log-spectral distance, full 0-8 kHz)
  - LSD_4_8kHz      (LSD over the 4-8 kHz band Opus 12k destroys)
  - DNSMOS SIG/BAK/OVL  (non-intrusive MOS, 1-5 scale; if model available)
  - F0_corr         (Pearson correlation of librosa.pyin F0 contours; optional)

In-window composite (Codec-SUPERB convention; DNSMOS-OVL headline):

  in_window_reward = 0.4 * clip01((DNSMOS_OVL - 1) / 4)
                   + 0.3 * STOI
                   + 0.3 * clip01(1 - LSD_4_8kHz / 5)

Fallback when DNSMOS is unavailable / out-of-distribution:

  in_window_reward = 0.5 * clip01((PESQ_wb - 1) / 3.5)
                   + 0.5 * clip01(1 - LSD_4_8kHz / 5)

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

import librosa
import numpy as np
import soundfile as sf
from pesq import pesq
from pystoi import stoi


DNSMOS_MODEL_PATH = Path("/tests/sig_bak_ovr.onnx")
WINDOW_JSON_PATH = Path("/tests/window.json")
DNSMOS_INPUT_SAMPLES = int(9.01 * 16000)  # 144160
IN_WEIGHT = 0.85
OUT_WEIGHT = 0.15


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


def _lsd_band(ref: np.ndarray, est: np.ndarray, sr: int,
              fmin: float, fmax: float,
              n_fft: int = 512, hop_length: int = 128) -> float:
    S_ref = np.abs(librosa.stft(ref, n_fft=n_fft, hop_length=hop_length)) ** 2
    S_est = np.abs(librosa.stft(est, n_fft=n_fft, hop_length=hop_length)) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    band = (freqs >= fmin) & (freqs <= fmax)
    if band.sum() == 0:
        return float("nan")
    S_ref_b = S_ref[band, :]
    S_est_b = S_est[band, :]
    eps = 1e-10
    log_ref = np.log10(S_ref_b + eps)
    log_est = np.log10(S_est_b + eps)
    diff_sq = (log_ref - log_est) ** 2
    per_frame = np.sqrt(diff_sq.mean(axis=0))
    return float(per_frame.mean())


def _dnsmos(audio: np.ndarray, sr: int, model_path: Path):
    import onnxruntime as ort
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


def _f0_corr(ref: np.ndarray, est: np.ndarray, sr: int) -> float:
    fmin, fmax = float(librosa.note_to_hz("C2")), float(librosa.note_to_hz("C7"))
    f0_r, vflag_r, _ = librosa.pyin(ref, fmin=fmin, fmax=fmax, sr=sr,
                                    frame_length=1024)
    f0_e, vflag_e, _ = librosa.pyin(est, fmin=fmin, fmax=fmax, sr=sr,
                                    frame_length=1024)
    voiced = vflag_r & vflag_e & np.isfinite(f0_r) & np.isfinite(f0_e)
    if voiced.sum() < 8:
        return float("nan")
    a = f0_r[voiced]
    b = f0_e[voiced]
    if a.std() < 1e-6 or b.std() < 1e-6:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def _score_in_window(est: np.ndarray, ref: np.ndarray,
                     dnsmos_model: Path) -> tuple[float, dict]:
    details: dict = {}
    pesq_wb = float(pesq(16000, ref, est, "wb"))
    details["pesq_wb"] = pesq_wb
    stoi_v = float(stoi(ref, est, 16000, extended=False))
    details["stoi"] = stoi_v
    lsd_full = _lsd_band(ref, est, 16000, 0.0, 8000.0)
    lsd_hi = _lsd_band(ref, est, 16000, 4000.0, 8000.0)
    details["lsd_full"] = lsd_full
    details["lsd_4_8kHz"] = lsd_hi
    try:
        details["f0_corr"] = _f0_corr(ref, est, 16000)
    except Exception as e:
        details["f0_corr_error"] = str(e)

    dnsmos_ok = False
    try:
        sig_m, bak_m, ovl_m = _dnsmos(est, 16000, dnsmos_model)
        details.update({"dnsmos_sig": sig_m, "dnsmos_bak": bak_m, "dnsmos_ovl": ovl_m})
        sig_r, bak_r, ovl_r = _dnsmos(ref, 16000, dnsmos_model)
        details["dnsmos_ref_ovl"] = ovl_r
        if ovl_r < 4.0:
            details["dnsmos_skipped"] = (
                f"DNSMOS on clean reference OVL={ovl_r:.2f} < 4.0 "
                "(out-of-distribution; identity sanity check would fail); "
                "falling back to PESQ+LSD composite."
            )
        else:
            dnsmos_ok = True
    except Exception as e:
        details["dnsmos_error"] = str(e)

    lsd_hi_n = _clip01(1.0 - lsd_hi / 5.0)
    if dnsmos_ok:
        ovl_n = _clip01((details["dnsmos_ovl"] - 1.0) / 4.0)
        stoi_n = _clip01(stoi_v)
        reward = 0.4 * ovl_n + 0.3 * stoi_n + 0.3 * lsd_hi_n
        details.update({
            "ovl_n": ovl_n,
            "stoi_n": stoi_n,
            "lsd_n": lsd_hi_n,
            "composite_formula": (
                "0.4*clip01((DNSMOS_OVL-1)/4) + 0.3*STOI + 0.3*clip01(1 - LSD_4_8kHz/5)"
            ),
        })
    else:
        pesq_n = _clip01((pesq_wb - 1.0) / 3.5)
        reward = 0.5 * pesq_n + 0.5 * lsd_hi_n
        details.update({
            "pesq_n": pesq_n,
            "lsd_n": lsd_hi_n,
            "composite_formula": (
                "0.5*clip01((PESQ_wb-1)/3.5) + 0.5*clip01(1 - LSD_4_8kHz/5) "
                "[DNSMOS unavailable fallback]"
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
        in_reward, in_details = _score_in_window(est[s0:s1], ref[s0:s1], dnsmos_model)
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
