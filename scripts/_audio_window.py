"""Window-scoped audio corruption helpers used by the build_* scripts.

Centered 10 s window by default. If the centered window is "silent enough"
(median RMS of 50 ms frames inside window is < 30% of median RMS over the
full clip), shift to the loudest contiguous voiced 10 s region.

Also: equal-power 50 ms crossfade splice used by dereverb/codec-restore
to combine a fully-corrupted stream with a fully-clean stream into a
window-scoped corruption.
"""
from __future__ import annotations

from typing import Tuple

import numpy as np


WINDOW_S = 10.0
CROSSFADE_MS = 50.0


def _frame_rms(y: np.ndarray, sr: int, frame_s: float = 0.05) -> np.ndarray:
    frame = max(1, int(frame_s * sr))
    n_frames = len(y) // frame
    if n_frames == 0:
        return np.zeros(0, dtype=np.float64)
    trimmed = y[: n_frames * frame].reshape(n_frames, frame)
    return np.sqrt((trimmed.astype(np.float64) ** 2).mean(axis=1) + 1e-12)


def pick_window(y: np.ndarray, sr: int, win_s: float = WINDOW_S) -> Tuple[float, float]:
    """Return (start_s, end_s) for a `win_s` window centered on the clip,
    shifted to a voiced region if the centered one is too quiet."""
    n = len(y)
    dur = n / sr
    if dur <= win_s:
        return 0.0, dur
    half = win_s / 2.0
    center = dur / 2.0
    default = (center - half, center + half)

    rms = _frame_rms(y, sr)
    if len(rms) == 0:
        return default
    med_rms = float(np.median(rms))
    if med_rms <= 1e-9:
        return default
    f_per_s = 1.0 / 0.05

    def voiced_frac(start_s: float, end_s: float) -> float:
        i0 = int(start_s * f_per_s)
        i1 = int(end_s * f_per_s)
        if i1 <= i0:
            return 0.0
        seg = rms[i0:i1]
        return float((seg > 0.3 * med_rms).mean())

    if voiced_frac(*default) >= 0.5:
        return default

    # Slide a window of win_s by 0.5 s steps; pick the highest voiced_frac.
    step = 0.5
    best = default
    best_score = voiced_frac(*default)
    t = 0.0
    while t + win_s <= dur + 1e-6:
        score = voiced_frac(t, t + win_s)
        if score > best_score:
            best_score = score
            best = (t, t + win_s)
        t += step
    return best


def equal_power_crossfade_splice(
    corrupted: np.ndarray,
    clean: np.ndarray,
    win_start_s: float,
    win_end_s: float,
    sr: int,
    fade_ms: float = CROSSFADE_MS,
) -> np.ndarray:
    """Splice `corrupted[in_window] ∪ clean[out_window]` with an
    equal-power 50 ms crossfade at each boundary.

    Out-of-window samples (outside the fade ramps) are byte-identical to
    `clean`, so unprocessed regions stay untouched.
    """
    n = min(len(corrupted), len(clean))
    corrupted = corrupted[:n].astype(np.float32)
    clean = clean[:n].astype(np.float32)

    s0 = int(round(win_start_s * sr))
    s1 = int(round(win_end_s * sr))
    fade = max(1, int(round(fade_ms * 1e-3 * sr)))
    fade = min(fade, (s1 - s0) // 2)

    out = clean.copy()

    # Center region (full corruption, no crossfade).
    inner_a = s0 + fade
    inner_b = s1 - fade
    if inner_b > inner_a:
        out[inner_a:inner_b] = corrupted[inner_a:inner_b]

    # Leading crossfade: clean -> corrupted across [s0, s0+fade).
    t = np.arange(fade, dtype=np.float64) / max(1, fade - 1)
    fade_in = np.sin(0.5 * np.pi * t).astype(np.float32)
    fade_out = np.cos(0.5 * np.pi * t).astype(np.float32)
    a0 = max(0, s0)
    b0 = min(n, s0 + fade)
    L = b0 - a0
    if L > 0:
        out[a0:b0] = clean[a0:b0] * fade_out[:L] + corrupted[a0:b0] * fade_in[:L]

    # Trailing crossfade: corrupted -> clean across [s1-fade, s1).
    t2 = np.arange(fade, dtype=np.float64) / max(1, fade - 1)
    fade_out2 = np.sin(0.5 * np.pi * t2).astype(np.float32)
    fade_in2 = np.cos(0.5 * np.pi * t2).astype(np.float32)
    a1 = max(0, s1 - fade)
    b1 = min(n, s1)
    L = b1 - a1
    if L > 0:
        out[a1:b1] = corrupted[a1:b1] * fade_out2[:L] + clean[a1:b1] * fade_in2[:L]

    return out
