#!/usr/bin/env python3
"""Build reviewer-facing native-frame robot-ball contact panels."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path


TASK_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = TASK_ROOT / "calibration" / "contact-evidence"
VIDEO_SHA256 = "076bcc59fc48443d24a72a87162021470b9e645b41c858c3ffa5b5b25bae36cd"
FPS = 50

CASES = (
    {
        "slug": "half1-white-midfield-reversal",
        "frames": range(8311, 8316),
        "source_crop": (260, 180, 360, 240),
        "detail_crop": (70, 80, 180, 120),
        "robot_box": (105, 110, 45, 45),
        "ball_points": ((156, 149), (152, 148), (150, 147), (154, 146), (158, 147)),
    },
    {
        "slug": "half1-black-number3-launch",
        "frames": range(8764, 8769),
        "source_crop": (480, 240, 360, 240),
        "detail_crop": (100, 100, 180, 120),
        "robot_box": (145, 140, 55, 60),
        "ball_points": (None, None, None, (194, 164), (198, 162)),
    },
    {
        "slug": "half1-white-lower-field-reversal",
        "frames": range(10297, 10302),
        "source_crop": (360, 360, 360, 240),
        "detail_crop": (160, 80, 180, 120),
        "robot_box": (275, 110, 60, 60),
        "ball_points": ((249, 134), (260, 136), None, (260, 133), (245, 125)),
    },
    {
        "slug": "half2-cluster-launch",
        "frames": range(38096, 38101),
        "source_crop": (160, 260, 400, 240),
        "detail_crop": (0, 90, 200, 120),
        "robot_box": (15, 145, 105, 75),
        "ball_points": ((70, 184), (68, 182), None, (85, 155), (98, 136)),
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    return parser.parse_args()


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stack(ffmpeg: str, inputs: list[Path], output: Path, direction: str) -> None:
    filters = "hstack" if direction == "horizontal" else "vstack"
    run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *sum((["-i", str(path)] for path in inputs), []),
            "-filter_complex",
            f"{filters}=inputs={len(inputs)}",
            str(output),
        ]
    )


def main() -> None:
    args = parse_args()
    ffmpeg = shutil.which(args.ffmpeg) or args.ffmpeg
    if not Path(ffmpeg).is_file() and shutil.which(ffmpeg) is None:
        raise RuntimeError(f"ffmpeg not found: {args.ffmpeg}")
    actual_digest = sha256(args.input)
    if actual_digest != VIDEO_SHA256:
        raise RuntimeError(f"unexpected input SHA256: {actual_digest}")
    args.output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="robocup-contact-evidence-") as directory:
        temporary = Path(directory)
        for case in CASES:
            native_frames = []
            detail_frames = []
            source_x, source_y, source_w, source_h = case["source_crop"]
            detail_x, detail_y, detail_w, detail_h = case["detail_crop"]
            robot_x, robot_y, robot_w, robot_h = case["robot_box"]
            for frame, ball_point in zip(case["frames"], case["ball_points"]):
                native = temporary / f"{case['slug']}-{frame}-native.png"
                detail = temporary / f"{case['slug']}-{frame}-detail.png"
                run(
                    [
                        ffmpeg,
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-y",
                        "-ss",
                        f"{frame / FPS:.2f}",
                        "-i",
                        str(args.input),
                        "-frames:v",
                        "1",
                        "-vf",
                        f"crop={source_w}:{source_h}:{source_x}:{source_y}",
                        str(native),
                    ]
                )
                robot_filter = (
                    f"drawbox=x={(robot_x - detail_x) * 2}:"
                    f"y={(robot_y - detail_y) * 2}:w={robot_w * 2}:h={robot_h * 2}:"
                    "color=cyan@0.95:t=4"
                )
                filters = [
                    f"crop={detail_w}:{detail_h}:{detail_x}:{detail_y}",
                    f"scale={detail_w * 2}:{detail_h * 2}:flags=neighbor",
                    robot_filter,
                ]
                if ball_point is not None:
                    ball_x, ball_y = ball_point
                    filters.append(
                        f"drawbox=x={(ball_x - detail_x) * 2 - 10}:"
                        f"y={(ball_y - detail_y) * 2 - 10}:w=20:h=20:"
                        "color=magenta@0.95:t=3"
                    )
                run(
                    [
                        ffmpeg,
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-y",
                        "-i",
                        str(native),
                        "-vf",
                        ",".join(filters),
                        str(detail),
                    ]
                )
                native_frames.append(native)
                detail_frames.append(detail)

            native_strip = temporary / f"{case['slug']}-native-strip.png"
            detail_strip = temporary / f"{case['slug']}-detail-strip.png"
            stack(ffmpeg, native_frames, native_strip, "horizontal")
            stack(ffmpeg, detail_frames, detail_strip, "horizontal")
            stack(
                ffmpeg,
                [native_strip, detail_strip],
                args.output / f"{case['slug']}.png",
                "vertical",
            )

    for output in sorted(args.output.glob("*.png")):
        print(f"{sha256(output)}  {output.name}")


if __name__ == "__main__":
    main()
