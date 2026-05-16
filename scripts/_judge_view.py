"""Helper: transcribe a clip with faster-whisper tiny.en (the model the
judge uses) so we can pre-compute judge-visible filler counts and
anchor-word availability at build time.

Without this, the build-side transcription (whisper-timestamped base.en)
disagrees with the judge-side transcription (faster-whisper tiny.en),
which is what produces false-negative oracle scores.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9'\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def transcribe_with_faster_whisper(clip_path: Path) -> list[dict]:
    """Return judge-style word list with start, end (sec), text."""
    from faster_whisper import WhisperModel

    # Extract WAV
    wav = clip_path.with_suffix(".judge.wav")
    subprocess.run([
        "ffmpeg", "-y", "-i", str(clip_path),
        "-vn", "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_s16le", str(wav),
    ], check=True, capture_output=True)

    model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    segments, _info = model.transcribe(
        str(wav),
        language="en",
        word_timestamps=True,
        vad_filter=False,
        beam_size=1,
    )
    words = []
    for seg in segments:
        for w in (seg.words or []):
            words.append({
                "start": float(w.start),
                "end": float(w.end),
                "text": w.word,
            })

    wav.unlink(missing_ok=True)
    return words


def count_token_occurrences(words: list[dict], token: str) -> int:
    """Count occurrences of a (possibly multi-word) token in word list."""
    parts = _norm(token).split()
    if not parts:
        return 0
    norm_texts = [_norm(w["text"]) for w in words]
    n = 0
    for i in range(len(words) - len(parts) + 1):
        if all(norm_texts[i + j] == parts[j] for j in range(len(parts))):
            n += 1
    return n


def find_phrase(words: list[dict], phrase: list[str],
                start_idx: int = 0) -> int:
    """Return first index i >= start_idx such that words[i:i+L] == phrase
    (normalized). -1 if not found."""
    phrase_norm = [_norm(p) for p in phrase if _norm(p)]
    if not phrase_norm:
        return -1
    norm_texts = [_norm(w["text"]) for w in words]
    L = len(phrase_norm)
    for i in range(start_idx, len(words) - L + 1):
        if all(norm_texts[i + j] == phrase_norm[j] for j in range(L)):
            return i
    return -1
