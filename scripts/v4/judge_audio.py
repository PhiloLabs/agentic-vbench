"""v4 audio judges — five families.

Each judge:
  1. Loads broken / golden / claude at 16 kHz mono.
  2. Crops to the in-window segment (per tests/window.json) — out-of-window scoring removed.
  3. Computes the family-canonical base metric on each signal.
  4. Applies the universal normalize-improvement formula.

Metric per family:
  dns-denoise       PESQ-WB (primary) + DNSMOS-OVRL (secondary)
  voicebank-denoise PESQ-WB (primary) + DNSMOS-OVRL (secondary)
  dereverb          SRMR (primary, no-reference)
  declip            masked SI-SDR on clip_mask samples only (URGENT 2024)
  codec-restore     MCD (mel-cepstral distortion, lower-is-better)
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _framework import (  # noqa: E402
    align_lengths,
    append_tsv,
    get_task_paths,
    load_audio_16k,
    normalize_improvement,
    read_window_json,
    write_v4_result,
)


SR = 16000


# ── metric implementations ──────────────────────────────────────────────────

def pesq_wb(ref: np.ndarray, deg: np.ndarray) -> float:
    from pesq import pesq

    ref, deg = align_lengths(ref, deg)
    try:
        return float(pesq(SR, ref, deg, "wb"))
    except Exception as e:  # pragma: no cover
        return float("nan")


def stoi_score(ref: np.ndarray, deg: np.ndarray) -> float:
    from pystoi import stoi

    ref, deg = align_lengths(ref, deg)
    return float(stoi(ref, deg, SR, extended=False))


def si_sdr(ref: np.ndarray, deg: np.ndarray, eps: float = 1e-10) -> float:
    ref, deg = align_lengths(ref, deg)
    ref = ref - ref.mean()
    deg = deg - deg.mean()
    alpha = float(np.dot(deg, ref)) / (float(np.dot(ref, ref)) + eps)
    s_target = alpha * ref
    e_noise = deg - s_target
    num = float(np.dot(s_target, s_target)) + eps
    den = float(np.dot(e_noise, e_noise)) + eps
    return 10.0 * float(np.log10(num / den))


def srmr(x: np.ndarray) -> float:
    from srmrpy import srmr as _srmr

    val, _ = _srmr(x, SR, norm=True)
    return float(val)


def dnsmos_ovrl(x: np.ndarray) -> float:
    from speechmos import dnsmos

    res = dnsmos.run(x.astype(np.float32), SR)
    return float(res.get("ovrl_mos", res.get("OVRL", float("nan"))))


def masked_si_sdr(ref: np.ndarray, deg: np.ndarray, mask: np.ndarray, eps: float = 1e-10) -> float:
    """SI-SDR computed on samples where mask==1.

    Following the URGENT 2024 declip protocol: the alpha-scale is fit on the
    full signal (preserves global gain meaning), MSE is summed only over the
    masked subset.
    """
    n = min(len(ref), len(deg), len(mask))
    ref = ref[:n] - ref[:n].mean()
    deg = deg[:n] - deg[:n].mean()
    mask = mask[:n].astype(bool)
    alpha = float(np.dot(deg, ref)) / (float(np.dot(ref, ref)) + eps)
    s_target = alpha * ref
    e_noise = deg - s_target
    num = float(np.sum(s_target[mask] ** 2)) + eps
    den = float(np.sum(e_noise[mask] ** 2)) + eps
    return 10.0 * float(np.log10(num / den))


def lsd(ref: np.ndarray, deg: np.ndarray, sr: int = SR, n_fft: int = 1024,
        hop: int = 160, eps: float = 1e-10) -> float:
    """Log-spectral distance (dB). Lower = better. LSD(x, x) = 0.

    Codec-SUPERB and many codec-restoration papers report LSD as a primary
    metric. Captures spectral envelope distortion well.
    """
    import librosa

    ref, deg = align_lengths(ref, deg)
    X = np.abs(librosa.stft(ref.astype(np.float32), n_fft=n_fft, hop_length=hop)) + eps
    Y = np.abs(librosa.stft(deg.astype(np.float32), n_fft=n_fft, hop_length=hop)) + eps
    n = min(X.shape[1], Y.shape[1])
    logX = 20.0 * np.log10(X[:, :n])
    logY = 20.0 * np.log10(Y[:, :n])
    return float(np.sqrt(np.mean((logX - logY) ** 2)))


# ── per-task judges ─────────────────────────────────────────────────────────

def _crop_window(x: np.ndarray, win: dict) -> np.ndarray:
    s = int(round(win["window_start_s"] * SR))
    e = int(round(win["window_end_s"] * SR))
    return x[s:e]


def judge_dns_denoise(task_id: str = "exp-dns-denoise-task01") -> dict:
    t0 = time.time()
    p = get_task_paths(task_id)
    win = read_window_json(p.window_json)
    broken = _crop_window(load_audio_16k(p.broken), win)
    golden = _crop_window(load_audio_16k(p.golden), win)
    claude = _crop_window(load_audio_16k(p.claude), win)

    m_broken_pesq = pesq_wb(golden, broken)
    m_golden_pesq = pesq_wb(golden, golden)
    m_claude_pesq = pesq_wb(golden, claude)
    score, reason = normalize_improvement(m_claude_pesq, m_broken_pesq, m_golden_pesq, higher_is_better=True)

    # secondary diagnostics
    dn_broken = dnsmos_ovrl(broken)
    dn_golden = dnsmos_ovrl(golden)
    dn_claude = dnsmos_ovrl(claude)
    si_broken = si_sdr(golden, broken)
    si_claude = si_sdr(golden, claude)

    details = {
        "metric_primary": "pesq_wb",
        "in_window_only": True,
        "window": win,
        "pesq_wb": {"broken": m_broken_pesq, "golden": m_golden_pesq, "claude": m_claude_pesq},
        "dnsmos_ovrl": {"broken": dn_broken, "golden": dn_golden, "claude": dn_claude},
        "si_sdr_vs_golden": {"broken": si_broken, "claude": si_claude},
        "elapsed_s": time.time() - t0,
        "reason": reason,
    }
    write_v4_result(task_id, "audio_inj", "pesq_wb",
                    m_broken_pesq, m_golden_pesq, m_claude_pesq, score, score, details)
    append_tsv(task_id, "audio_inj", "pesq_wb",
               m_broken_pesq, m_golden_pesq, m_claude_pesq, score, score)
    return {"task": task_id, "score": score, "details": details}


def judge_voicebank_denoise(task_id: str = "exp-voicebank-denoise-task01") -> dict:
    # Identical metric setup to DNS; just a different audio source.
    t0 = time.time()
    p = get_task_paths(task_id)
    win = read_window_json(p.window_json)
    broken = _crop_window(load_audio_16k(p.broken), win)
    golden = _crop_window(load_audio_16k(p.golden), win)
    claude = _crop_window(load_audio_16k(p.claude), win)

    m_broken = pesq_wb(golden, broken)
    m_golden = pesq_wb(golden, golden)
    m_claude = pesq_wb(golden, claude)
    score, reason = normalize_improvement(m_claude, m_broken, m_golden, higher_is_better=True)

    dn_b = dnsmos_ovrl(broken); dn_g = dnsmos_ovrl(golden); dn_c = dnsmos_ovrl(claude)

    details = {
        "metric_primary": "pesq_wb",
        "in_window_only": True,
        "window": win,
        "pesq_wb": {"broken": m_broken, "golden": m_golden, "claude": m_claude},
        "dnsmos_ovrl": {"broken": dn_b, "golden": dn_g, "claude": dn_c},
        "elapsed_s": time.time() - t0,
        "reason": reason,
    }
    write_v4_result(task_id, "audio_inj", "pesq_wb", m_broken, m_golden, m_claude, score, score, details)
    append_tsv(task_id, "audio_inj", "pesq_wb", m_broken, m_golden, m_claude, score, score)
    return {"task": task_id, "score": score, "details": details}


def judge_dereverb(task_id: str = "exp-dereverb-task01") -> dict:
    t0 = time.time()
    p = get_task_paths(task_id)
    win = read_window_json(p.window_json)
    broken = _crop_window(load_audio_16k(p.broken), win)
    golden = _crop_window(load_audio_16k(p.golden), win)
    claude = _crop_window(load_audio_16k(p.claude), win)

    m_broken = srmr(broken)
    m_golden = srmr(golden)
    m_claude_raw = srmr(claude)
    # Cap overshoot: SRMR > golden often means dry-sounding artifacts, not
    # better-than-clean dereverberation. Reflect any value above golden back
    # towards broken; values at or below golden pass through unchanged.
    overshoot = max(0.0, m_claude_raw - m_golden)
    if overshoot > 0:
        m_claude = m_golden - overshoot
    else:
        m_claude = m_claude_raw
    score, reason = normalize_improvement(m_claude, m_broken, m_golden, higher_is_better=True)

    # diagnostic: also PESQ-WB. Sanity gate: if PESQ collapsed, the SRMR boost
    # is artifactual (often white-ish noise). Apply soft penalty.
    pesq_b = pesq_wb(golden, broken); pesq_c = pesq_wb(golden, claude); pesq_g = pesq_wb(golden, golden)
    pesq_floor = 1.05
    if pesq_c < pesq_floor + 0.5 * (pesq_g - pesq_floor):
        # Claude's PESQ is in the low half of the noisy→clean range.
        pesq_factor = max(0.0, (pesq_c - pesq_floor)) / max(1e-6, (pesq_g - pesq_floor))
        score = score * pesq_factor

    details = {
        "metric_primary": "srmr",
        "in_window_only": True,
        "window": win,
        "srmr": {"broken": m_broken, "golden": m_golden,
                 "claude_raw": m_claude_raw, "claude_reflected": m_claude,
                 "overshoot_penalty_applied": overshoot > 0},
        "pesq_wb_sanity": {"broken": pesq_b, "golden": pesq_g, "claude": pesq_c,
                           "penalty_active": pesq_c < pesq_floor + 0.5 * (pesq_g - pesq_floor)},
        "elapsed_s": time.time() - t0,
        "reason": reason,
    }
    # Use 'srmr' key in the standard shape so the printer can locate broken/golden/claude.
    details["srmr"]["broken"] = m_broken
    details["srmr"]["golden"] = m_golden
    details["srmr"]["claude"] = m_claude
    write_v4_result(task_id, "audio_inj", "srmr", m_broken, m_golden, m_claude, score, score, details)
    append_tsv(task_id, "audio_inj", "srmr", m_broken, m_golden, m_claude, score, score)
    return {"task": task_id, "score": score, "details": details}


def judge_declip(task_id: str = "exp-declip-task01") -> dict:
    """Masked SI-SDR on clip_mask samples (URGENT 2024 protocol)."""
    t0 = time.time()
    p = get_task_paths(task_id)
    win = read_window_json(p.window_json)
    broken_full = load_audio_16k(p.broken)
    golden_full = load_audio_16k(p.golden)
    claude_full = load_audio_16k(p.claude)
    mask_full = np.load(p.clip_mask_npy).astype(np.uint8)

    # Crop everything to the in-window slice for a fair comparison.
    s = int(round(win["window_start_s"] * SR))
    e = int(round(win["window_end_s"] * SR))
    broken = broken_full[s:e]
    golden = golden_full[s:e]
    claude = claude_full[s:e]
    mask = mask_full[s:e]
    if mask.sum() == 0:
        # No clipped samples in window — fallback to full mask
        mask = mask_full
        broken, golden, claude = broken_full, golden_full, claude_full

    m_broken = masked_si_sdr(golden, broken, mask)
    m_claude = masked_si_sdr(golden, claude, mask)
    # Golden anchor: SI-SDR(clean, clean) is +∞; use the URGENT convention of
    # capping at +40 dB (above this is indistinguishable from numerical noise).
    m_golden = 40.0

    score, reason = normalize_improvement(m_claude, m_broken, m_golden, higher_is_better=True)

    # Diagnostic: also full PESQ-WB and unmasked SI-SDR
    pesq_b = pesq_wb(golden, broken); pesq_c = pesq_wb(golden, claude); pesq_g = pesq_wb(golden, golden)
    si_b = si_sdr(golden, broken); si_c = si_sdr(golden, claude)

    details = {
        "metric_primary": "masked_si_sdr",
        "in_window_only": True,
        "window": win,
        "n_clipped_samples": int(mask.sum()),
        "n_total_samples": int(len(mask)),
        "masked_si_sdr": {"broken": m_broken, "golden": m_golden, "claude": m_claude,
                          "golden_anchor_note": "URGENT cap at +40 dB (clean self-SDR is +inf)"},
        "pesq_wb_full_signal": {"broken": pesq_b, "golden": pesq_g, "claude": pesq_c},
        "si_sdr_unmasked": {"broken": si_b, "claude": si_c},
        "elapsed_s": time.time() - t0,
        "reason": reason,
    }
    write_v4_result(task_id, "audio_inj", "masked_si_sdr", m_broken, m_golden, m_claude, score, score, details)
    append_tsv(task_id, "audio_inj", "masked_si_sdr", m_broken, m_golden, m_claude, score, score)
    return {"task": task_id, "score": score, "details": details}


def judge_codec_restore(task_id: str = "exp-codec-restore-task01") -> dict:
    t0 = time.time()
    p = get_task_paths(task_id)
    win = read_window_json(p.window_json)
    broken = _crop_window(load_audio_16k(p.broken), win)
    golden = _crop_window(load_audio_16k(p.golden), win)
    claude = _crop_window(load_audio_16k(p.claude), win)

    m_broken = lsd(golden, broken)
    m_golden = lsd(golden, golden)
    m_claude = lsd(golden, claude)
    score, reason = normalize_improvement(m_claude, m_broken, m_golden, higher_is_better=False)

    # Diagnostic
    pesq_b = pesq_wb(golden, broken); pesq_c = pesq_wb(golden, claude); pesq_g = pesq_wb(golden, golden)

    details = {
        "metric_primary": "lsd",
        "in_window_only": True,
        "window": win,
        "lsd": {"broken": m_broken, "golden": m_golden, "claude": m_claude,
                "unit": "dB, lower-is-better"},
        "pesq_wb": {"broken": pesq_b, "golden": pesq_g, "claude": pesq_c},
        "elapsed_s": time.time() - t0,
        "reason": reason,
    }
    write_v4_result(task_id, "audio_inj", "lsd", m_broken, m_golden, m_claude, score, score, details)
    append_tsv(task_id, "audio_inj", "lsd", m_broken, m_golden, m_claude, score, score)
    return {"task": task_id, "score": score, "details": details}


# ── driver ──────────────────────────────────────────────────────────────────

JUDGES = {
    "exp-dns-denoise-task01": judge_dns_denoise,
    "exp-voicebank-denoise-task01": judge_voicebank_denoise,
    "exp-dereverb-task01": judge_dereverb,
    "exp-declip-task01": judge_declip,
    "exp-codec-restore-task01": judge_codec_restore,
}


def main(argv: list[str]) -> int:
    tasks = argv[1:] or list(JUDGES.keys())
    print(f"v4 audio judge: scoring {len(tasks)} task(s)")
    for tid in tasks:
        if tid not in JUDGES:
            print(f"[skip] unknown task: {tid}")
            continue
        try:
            r = JUDGES[tid](tid)
            d = r["details"]
            mp = d["metric_primary"]
            ms = d[mp]
            print(f"  {tid:42s} score={r['score']:.3f}  metric={mp}  m_b={ms['broken']:.3g}  m_g={ms['golden']:.3g}  m_c={ms['claude']:.3g}")
        except Exception as e:
            import traceback
            print(f"  {tid:42s} ERROR  {e}")
            traceback.print_exc()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
