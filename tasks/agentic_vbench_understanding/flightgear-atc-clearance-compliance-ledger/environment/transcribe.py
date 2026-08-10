#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
import wave
from pathlib import Path


MODEL_DIR = "/baked/asr"


def extract_audio(media: Path, start: float | None, end: float | None) -> Path:
    temporary = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temporary.close()
    output = Path(temporary.name)
    command = ["ffmpeg", "-loglevel", "error", "-y"]
    if start is not None:
        command.extend(["-ss", str(start)])
    if end is not None:
        command.extend(["-to", str(end)])
    command.extend(
        ["-i", str(media), "-vn", "-ac", "1", "-ar", "16000", str(output)]
    )
    subprocess.run(command, check=True)
    return output


def speech_intervals(wav: Path) -> list[tuple[float, float]]:
    with wave.open(str(wav), "rb") as source:
        duration_s = source.getnframes() / source.getframerate()
    detected = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(wav),
            "-af",
            "silencedetect=noise=-45dB:d=0.4",
            "-f",
            "null",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stderr
    events = []
    for line in detected.splitlines():
        start_match = re.search(r"silence_start: ([0-9.]+)", line)
        if start_match:
            events.append((float(start_match.group(1)), "start"))
        end_match = re.search(r"silence_end: ([0-9.]+)", line)
        if end_match:
            events.append((float(end_match.group(1)), "end"))
    events.sort()

    intervals = []
    speech_start = 0.0
    for timestamp, event_type in events:
        if event_type == "start":
            if timestamp - speech_start >= 0.2:
                intervals.append((speech_start, timestamp))
        else:
            speech_start = timestamp
    if duration_s - speech_start >= 0.2:
        intervals.append((speech_start, duration_s))
    return intervals


def extract_interval(wav: Path, start_s: float, end_s: float) -> Path:
    temporary = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temporary.close()
    output = Path(temporary.name)
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            str(start_s),
            "-to",
            str(end_s),
            "-i",
            str(wav),
            "-c",
            "copy",
            str(output),
        ],
        check=True,
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("media", type=Path)
    parser.add_argument("--start", type=float)
    parser.add_argument("--end", type=float)
    args = parser.parse_args()

    if not args.media.is_file():
        raise SystemExit(f"no such media file: {args.media}")
    if args.start is not None and args.end is not None and args.end <= args.start:
        raise SystemExit("--end must be greater than --start")

    wav = extract_audio(args.media, args.start, args.end)
    try:
        from faster_whisper import WhisperModel

        model = WhisperModel(MODEL_DIR, device="cpu", compute_type="int8")
        offset = args.start or 0.0
        for start_s, end_s in speech_intervals(wav):
            clip = extract_interval(wav, start_s, end_s)
            try:
                segments, _ = model.transcribe(
                    str(clip),
                    vad_filter=False,
                    condition_on_previous_text=False,
                    initial_prompt=(
                        "Air traffic control clearance. Callsign November seven "
                        "two alpha. Headings are spoken as three separate digits."
                    ),
                    hotwords=(
                        "zero one two three four five six seven eight nine heading "
                        "climb descend maintain knots feet"
                    ),
                )
                text = " ".join(
                    segment.text.strip() for segment in segments if segment.text.strip()
                )
            finally:
                clip.unlink(missing_ok=True)
            if text:
                print(
                    f"[{offset + start_s:.1f}-{offset + end_s:.1f}] {text}",
                    flush=True,
                )
    finally:
        wav.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
