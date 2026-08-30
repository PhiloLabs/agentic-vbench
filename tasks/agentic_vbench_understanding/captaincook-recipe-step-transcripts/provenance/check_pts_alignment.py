#!/usr/bin/env python3
"""Does annotation time t land on the same picture in the baked MP4 as in the source?

    python3 provenance/check_pts_alignment.py --letter D \
        --source /abs/4_30.mp4 --derivative /abs/D.mp4 [--derived provenance/step-derived.json]

Comparing total durations does not answer this. Two files can agree on length to the
frame and still be shifted against each other, and a shift is exactly the failure that
would move every annotated boundary in the key without changing anything the build
already checks.

So this compares pictures, not lengths. At each sampled annotation time t it pulls the
frame at t from the publisher's own 4K object, pulls a fan of frames from the baked 1080p
derivative at t plus a range of offsets, reduces all of them to a small greyscale
thumbnail so that resolution and codec do not dominate, and requires that the derivative
frame closest to the source frame is the one at offset ZERO.

The fan is the point. A check that only measured the distance at offset zero would pass on
a video where every frame looks like every other frame, and would have no way to say
whether it could have detected a shift at all. Requiring the argmin to be zero means the
check fails both when the derivative is shifted and when the footage is too static for the
question to be answerable, and those are different messages.

Sample times come from the key's own step boundaries, because those are the numbers the
task is scored on.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Offsets in seconds probed on the derivative side. Zero must win.
OFFSETS = (-2.0, -1.0, -0.5, -0.25, 0.0, 0.25, 0.5, 1.0, 2.0)
THUMB = (160, 90)


def frame(path: str, t: float) -> bytes | None:
    """One frame at t as a raw greyscale thumbnail, or None if the seek fell off the end."""
    cmd = ["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(path),
           "-frames:v", "1", "-vf", f"scale={THUMB[0]}:{THUMB[1]}", "-pix_fmt", "gray",
           "-f", "rawvideo", "-"]
    p = subprocess.run(cmd, capture_output=True)
    want = THUMB[0] * THUMB[1]
    return p.stdout if len(p.stdout) == want else None


def dist(a: bytes, b: bytes) -> float:
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--letter", required=True)
    ap.add_argument("--source", required=True,
                    help="the publisher's object: a local path, or its URL. ffmpeg reads "
                         "the URL with range requests and pulls only the bytes around each "
                         "sampled second, so this check does not need the 4 GB download.")
    ap.add_argument("--derivative", required=True, type=Path)
    ap.add_argument("--derived", type=Path, default=Path(__file__).with_name("step-derived.json"))
    ap.add_argument("--samples", type=int, default=10)
    args = ap.parse_args()

    d = json.loads(args.derived.read_text())
    inst = d["instances"][args.letter]
    dur = next(v["duration_sec"] for v in d["videos"] if v["letter"] == args.letter)
    # Boundaries, evenly thinned across the recording, kept away from both ends so the
    # negative offsets stay inside the file.
    times = sorted({round(g["t_start"], 3) for g in inst} | {round(g["t_end"], 3) for g in inst})
    times = [t for t in times if 3.0 < t < dur - 3.0]
    if len(times) > args.samples:
        step = len(times) / args.samples
        times = [times[int(i * step)] for i in range(args.samples)]
    print(f"  {args.letter}: {len(times)} annotation boundaries sampled across {dur:.1f}s")

    failures, unanswerable = [], []
    for t in times:
        src = frame(args.source, t)
        if src is None:
            unanswerable.append((t, "source frame unreadable"))
            continue
        scores = {}
        for off in OFFSETS:
            got = frame(str(args.derivative), t + off)
            if got is not None:
                scores[off] = dist(src, got)
        if 0.0 not in scores:
            unanswerable.append((t, "derivative frame at offset 0 unreadable"))
            continue
        best = min(scores, key=scores.get)
        spread = max(scores.values()) - min(scores.values())
        # If nothing separates the offsets, the footage is too static here to answer.
        if spread < 1.0:
            unanswerable.append((t, f"all offsets within {spread:.2f} grey levels"))
            continue
        mark = "ok " if best == 0.0 else "OFF"
        print(f"    t={t:8.2f}  best offset {best:+.2f}s  "
              f"d0={scores[0.0]:6.2f}  spread={spread:6.2f}  {mark}")
        if best != 0.0:
            failures.append((t, best, scores))

    print(f"  answerable {len(times) - len(unanswerable)}/{len(times)}, "
          f"misaligned {len(failures)}")
    for t, why in unanswerable:
        print(f"    unanswerable at t={t:.2f}: {why}")
    if not times or len(unanswerable) == len(times):
        print("  RESULT: nothing could be tested, so this is NOT a pass")
        return 1
    if failures:
        print("  RESULT: annotation time does NOT map to the baked PTS")
        return 1
    print("  RESULT: at every answerable boundary the closest derivative frame is the one "
          "at the same timestamp, so annotation time maps to the baked PTS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
