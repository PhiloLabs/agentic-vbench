#!/usr/bin/env python3
"""Offline speech-to-text for the session audio. Prints timestamped lines.

    transcribe /workspace/materials/session.mp4 [--start S] [--end S]

Output: one line per segment, "[start_s-end_s] text" in seconds from the start of the
media. No speaker labels — the model does not do diarization.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

MODEL_DIR = "/baked/asr"


def extract_audio(src: str, start: float | None, end: float | None) -> str:
    wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    cmd = ["ffmpeg", "-loglevel", "error", "-y"]
    if start is not None:
        cmd += ["-ss", str(start)]
    if end is not None:
        cmd += ["-to", str(end)]
    cmd += ["-i", src, "-vn", "-ac", "1", "-ar", "16000", wav]
    subprocess.run(cmd, check=True)
    return wav


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("media")
    ap.add_argument("--start", type=float, default=None, help="seconds into the media")
    ap.add_argument("--end", type=float, default=None)
    args = ap.parse_args()

    if not Path(args.media).is_file():
        sys.exit(f"no such media file: {args.media}")
    wav = extract_audio(args.media, args.start, args.end)

    from faster_whisper import WhisperModel
    model = WhisperModel(MODEL_DIR, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(wav, vad_filter=True)
    base = args.start or 0.0
    for s in segments:
        print(f"[{base + s.start:.1f}-{base + s.end:.1f}] {s.text.strip()}", flush=True)


if __name__ == "__main__":
    main()
