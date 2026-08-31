#!/usr/bin/env python3
import argparse
import fcntl
import json
import subprocess
from pathlib import Path

import torch
import whisper

MAX_AUDIO_SECONDS = 180.0
LOCK_PATH = Path("/tmp/transcribe-audio.lock")


def duration_seconds(path: Path) -> float:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(completed.stdout.strip())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--task",
        choices=("transcribe", "translate"),
        default="transcribe",
    )
    parser.add_argument("audio", nargs="+", type=Path)
    args = parser.parse_args()

    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    for path in args.audio:
        duration = duration_seconds(path)
        if duration > MAX_AUDIO_SECONDS:
            raise ValueError(
                f"{path} is {duration:.1f}s; split audio into excerpts "
                f"no longer than {MAX_AUDIO_SECONDS:.0f}s"
            )
    with LOCK_PATH.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(
                "another transcribe-audio process is running; wait for it "
                "or batch all clips into one invocation"
            ) from error
        model = whisper.load_model("base", download_root="/opt/whisper")
        results = []
        for path in args.audio:
            result = model.transcribe(
                str(path),
                fp16=False,
                task=args.task,
            )
            results.append(
                {
                    "file": str(path),
                    "language": result["language"],
                    "text": result["text"].strip(),
                }
            )
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
