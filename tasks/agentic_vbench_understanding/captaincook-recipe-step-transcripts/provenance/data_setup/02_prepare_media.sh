#!/bin/sh
# Build the media package: for each selected recording, fetch the published 4K GoPro
# stream, transcode it down to 1080p, and drop the audio, the container metadata and
# every non-video stream.
#
#   sh provenance/data_setup/02_prepare_media.sh <derived.json> <workdir>
#
# One downloader and one transcoder run as a pipeline: while a recording is being
# transcoded the next one is already coming down the wire. Measured on this material,
# the download is the binding constraint and it is link-limited rather than
# connection-limited (one stream 9 MB/s, four parallel byte ranges of the same file
# 11 MB/s, two whole files in parallel 6 MB/s), so the downloader deliberately runs ONE
# stream at a time. Splitting it costs throughput rather than buying any.
#
# The 4K source is deleted as soon as it has been transcoded. The queue holds one item,
# which means up to THREE sources can be on disk at once: the one being transcoded, the
# one waiting in the queue, and the one coming down. Budget about 15 GiB of scratch on
# top of the roughly 12 GiB of finished output.
#
# Each finished recording writes its own sidecar under <workdir>/work/, and the sidecars
# are merged into media_manifest.json at the end. Lanes therefore never write the same
# file, and an interrupted run resumes by skipping whatever already has a sidecar.
#
# CaptainCook4D is Apache 2.0, so this derivative may be redistributed; the NOTICE file
# in the task root carries the attribution that licence requires. Both checksums are
# recorded, the one over the publisher's own object and the one over the derivative, so
# a reviewer can verify our copy came from the real source and that the shipped file is
# the one we measured.
set -eu
DERIVED="$1"
WORK="$2"
mkdir -p "$WORK/out" "$WORK/work"
python3 - "$DERIVED" "$WORK" <<'ZZ_PY_ZZ'
import hashlib
import json
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

derived, work = Path(sys.argv[1]), Path(sys.argv[2])
spec = json.loads(derived.read_text())
man = work / "media_manifest.json"
prior = json.loads(man.read_text()) if man.exists() else {}
for letter, rec in prior.items():                       # carry a previous run forward
    side = work / "work" / f"{letter}.json"
    if not side.exists():
        side.write_text(json.dumps(rec) + "\n")

lock = threading.Lock()


def say(msg):
    with lock:
        print(msg, flush=True)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def fetch(video, attempts=6):
    """Pull one 4K source. Runs alone: see the note at the top about link limits.

    --http1.1 is not cosmetic. Partway through a full run the host returned curl exit 92,
    a stream error in the HTTP/2 framing layer, and killed the job at 11 of 22. Forcing
    1.1 removes that failure mode. `-C -` resumes a part-file instead of restarting a
    multi-gigabyte download, and the retry loop here is on top of curl's own --retry
    because curl's does not cover an error it has already reported as fatal.
    """
    letter = video["letter"]
    src = work / f"{letter}.src.mp4"
    # The publisher does not ship checksums, so the only independent statement about how
    # many bytes this object has is the server's own. Ask first and check after: without
    # it a truncated transfer produces a plausible-looking file and a source_sha256 that
    # is a hash of the wrong bytes, and nothing downstream would notice.
    head = subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error",
                           "--http1.1", "-r", "0-0", "-D", "-", "-o", "/dev/null",
                           video["source_url"]], capture_output=True, text=True, check=True)
    m = re.search(r"content-range:\s*bytes\s+\d+-\d+/(\d+)", head.stdout, re.I)
    assert m, f"{letter}: the host did not report a size"
    want = int(m.group(1))
    last = None
    for attempt in range(1, attempts + 1):
        try:
            subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error",
                            "--http1.1", "--retry", "5", "--retry-delay", "5",
                            "--retry-all-errors", "-C", "-", "-o", str(src),
                            video["source_url"]], check=True)
            got = src.stat().st_size
            if got != want:
                raise RuntimeError(f"{letter}: got {got} bytes, host says {want}")
            return src, sha(src), got
        except (subprocess.CalledProcessError, RuntimeError) as exc:
            last = exc
            why = (f"curl exit {exc.returncode}"
                   if isinstance(exc, subprocess.CalledProcessError) else str(exc))
            say(f"{letter} download attempt {attempt}/{attempts} failed ({why}), retrying")
            src.unlink(missing_ok=True)          # a short file must not be resumed onto
            time.sleep(10 * attempt)
    raise RuntimeError(f"{letter}: download failed after {attempts} attempts") from last


def transcode(video, src, src_sha, src_bytes):
    letter = video["letter"]
    side = work / "work" / f"{letter}.json"
    dst = work / "out" / f"{letter}.mp4"
    # Hardware decode and hardware encode. The source is 4K HEVC and the CPU path runs
    # at about half real time, which is most of the wall clock of the whole job. The
    # bitrate is set high enough that the encoder is not what limits legibility: 6 Mbit/s
    # at 1080p is above what the CPU encoder produced at CRF 24 on the same material.
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-hwaccel", "videotoolbox",
                    "-i", str(src), "-map", "0:v:0", "-vf", "scale=-2:1080",
                    "-c:v", "h264_videotoolbox", "-b:v", "6000k",
                    "-pix_fmt", "yuv420p", "-an", "-dn", "-sn",
                    "-map_metadata", "-1", "-map_chapters", "-1", str(dst)], check=True)
    src.unlink()
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(dst)],
        capture_output=True, text=True, check=True).stdout.split()
    width, height, dur = int(probe[0]), int(probe[1]), float(probe[2])
    assert height >= 1080, f"{letter}: transcoded to {width}x{height}, below 1080p"
    assert abs(dur - video["duration_sec"]) < 2.0, \
        f"{letter}: transcode is {dur}s, key says {video['duration_sec']}s"
    side.write_text(json.dumps({
        "recording_id": video["recording_id"], "source_url": video["source_url"],
        "source_sha256": src_sha, "source_bytes": src_bytes,
        "derivative_sha256": sha(dst), "derivative_bytes": dst.stat().st_size,
        "width": width, "height": height, "duration_sec": round(dur, 3)}) + "\n")
    say(f"{letter} {video['recording_id']} {src_bytes/2**30:.2f}GiB -> "
        f"{dst.stat().st_size/2**20:.0f}MiB  {width}x{height}  {dur:.1f}s")


todo = spec["videos"]
pending = [v for v in todo if not (work / "work" / f"{v['letter']}.json").exists()]
for v in todo:
    if v not in pending:
        say(f"{v['letter']} already done")

q: queue.Queue = queue.Queue(maxsize=1)
errors: list = []


def downloader():
    """One recording at a time; a recording that will not come down is recorded and
    skipped rather than taking the other 21 with it."""
    for v in pending:
        try:
            q.put((v,) + fetch(v))
        except Exception as exc:                  # noqa: BLE001
            errors.append(exc)
            say(f"{v['letter']} SKIPPED: {exc}")
    q.put(None)


def transcoder():
    while True:
        item = q.get()
        if item is None:
            return
        try:
            transcode(*item)
        except Exception as exc:                  # noqa: BLE001
            errors.append(exc)
            say(f"{item[0]['letter']} TRANSCODE FAILED: {exc}")


threads = [threading.Thread(target=downloader), threading.Thread(target=transcoder)]
for t in threads:
    t.start()
for t in threads:
    t.join()

merged = {}
for v in todo:
    side = work / "work" / f"{v['letter']}.json"
    if side.exists():
        merged[v["letter"]] = json.loads(side.read_text())
man.write_text(json.dumps(merged, indent=1) + "\n")
total = sum(m["derivative_bytes"] for m in merged.values())
print(f"done {len(merged)}/{len(todo)}, {total/2**30:.2f} GiB in {work/'out'}")
if errors:
    print(f"{len(errors)} recording(s) did not complete; rerun to pick them up")
    raise SystemExit(1)
ZZ_PY_ZZ
