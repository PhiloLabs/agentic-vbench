#!/usr/bin/env python3
"""Emit environment/Dockerfile from the derived key and the media manifest.

    python3 provenance/make_dockerfile.py --derived provenance/step-derived.json \
        --media provenance/media_manifest.json --base <url prefix or PLACEHOLDER> \
        --out environment/Dockerfile

Twenty-two ARG pairs and twenty-two bake invocations are exactly the kind of list that
drifts from the key when it is edited by hand, so it is generated. The base URL is a parameter so
that moving the media is one command rather than an edit: the shipped Dockerfile points
at the HuggingFace dataset named in README.md, and passing a different --base rewrites
it. PLACEHOLDER is still accepted, and environment/bake.sh refuses to bake a placeholder
URL rather than failing later on a bad download.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# The base is pinned by digest, not by tag. `python:3.12-slim` moves, and a task image
# rebuilt a month from now against a moved tag is a different environment than the one the
# calibration ran in, with nothing in the file recording that it changed. This digest is
# the base the shipped image was actually built on, checked layer for layer against it.
BASE_IMAGE = ("python:3.12-slim@sha256:"
              "09f7da3bc104798d0afb40bc08d23ab2da20a76130cec1f2ef170848f5d85217")

HEAD = '''FROM ''' + BASE_IMAGE + '''

RUN apt-get update && apt-get install -y --no-install-recommends \\
        ffmpeg curl ca-certificates \\
    && rm -rf /var/lib/apt/lists/*

# The agent uses ffmpeg/ffprobe to seek and sample the {n} recordings. Pillow and numpy
# are here because the calibration runs used them to build contact sheets, and the
# family's rule is that a local calibration is only valid in an environment carrying the
# image's exact libraries. The grader itself is pure stdlib and needs neither. Pinned to
# the versions the calibration environment actually carries.
RUN pip install --no-cache-dir pillow==11.1.0 numpy==2.4.3

# Bake the {n} recordings at build time from pinned URLs, each verified by SHA256, the
# same pattern the v1.0 families (PR #10 / #37) and the understanding worked example use.
# The bake step strips container metadata, chapters and any data or subtitle stream so
# the image carries no recording identifiers, and asserts the result is clean.
#
# WHAT IS PINNED AND WHY IT IS NOT THE PUBLISHER'S OWN OBJECT. CaptainCook4D publishes
# each recording as a 3840x2160 HEVC file at about 45 Mbit/s. The {n} of them are
# {src_gib:.0f} GiB, which is not a sane thing to pull and transcode inside an image build, so
# what is pinned here is a derivative: the same recording scaled to 1080p with the audio
# dropped, {out_gib:.1f} GiB in total. CaptainCook4D is released under the Apache License 2.0,
# which permits redistributing a derivative with attribution, and NOTICE carries that
# attribution. Nothing is cropped, cut or reordered; only the resolution changes.
#
# The publisher's own URL and the SHA256 of the publisher's own object are recorded for
# every letter in provenance/media_manifest.json, so a reviewer can download the 4K
# original, confirm our source was the real one, and rerun
# provenance/data_setup/02_prepare_media.sh to reproduce the derivative.
#
# Source: CaptainCook4D (arXiv:2312.14556), https://captaincook4d.github.io/captain-cook/
# Annotations pinned by commit in provenance/data_setup/01_download_annotations.sh.
#
{listing}
'''

TAIL = '''
COPY bake.sh /tmp/bake.sh
RUN chmod +x /tmp/bake.sh \\
{bakes} \\
 && rm -f /tmp/bake.sh \\
 && test "$(find /baked -name '*.mp4' -size +0c | wc -l)" -eq {n}

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--derived", required=True, type=Path)
    ap.add_argument("--media", required=True, type=Path)
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    d = json.loads(args.derived.read_text())
    media = json.loads(args.media.read_text())
    vids = d["videos"]
    missing = [v["letter"] for v in vids if v["letter"] not in media]
    assert not missing, f"media manifest is missing {missing}"

    listing = "\n".join(
        f"# {v['letter']} = {v['recording_id']:<8} {v['activity_name']:<22} "
        f"{v['duration_sec']:8.2f} s  {media[v['letter']]['derivative_bytes']/2**20:6.0f} MiB"
        for v in vids)
    lines = [HEAD.format(
        n=len(vids), listing=listing,
        src_gib=sum(m["source_bytes"] for m in media.values()) / 2**30,
        out_gib=sum(m["derivative_bytes"] for m in media.values()) / 2**30)]
    lines.append(f'ARG BASE={args.base}')
    for v in vids:
        L = v["letter"]
        lines.append(f'ARG {L}_URL=${{BASE}}/{L}.mp4')
        lines.append(f'ARG {L}_SHA256={media[L]["derivative_sha256"]}')
    bakes = " \\\n".join(f' && /tmp/bake.sh {v["letter"]} "${v["letter"]}_URL" '
                         f'"${v["letter"]}_SHA256"' for v in vids)
    lines.append(TAIL.format(bakes=bakes, n=len(vids)))
    args.out.write_text("\n".join(lines))
    print(f"wrote {args.out} for {len(vids)} recordings, base {args.base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
