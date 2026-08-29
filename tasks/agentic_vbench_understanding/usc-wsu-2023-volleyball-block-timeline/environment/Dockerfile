FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates tesseract-ocr imagemagick \
    && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir --root-user-action=ignore numpy==2.1.3 pillow==11.0.0

# The tool profile is the working set for a video task: ffmpeg/ffprobe to seek and
# sample, ImageMagick and Pillow to crop and upscale a still, NumPy to compare one
# against another, and Tesseract to read the score graphic. Without these the task
# would measure whether an agent can reimplement image processing in pure Python,
# which is not the skill under test. The grader itself is pure stdlib — it only
# compares strings and integers — so it needs none of them.

# Bake the full-match broadcast at build time with a pinned URL and a SHA256
# verified at build, the same way the worked example does.
#
# Provenance and preparation (see environment/bake_media.sh):
#   Source: official WSU Athletics YouTube upload (1080p),
#     https://www.youtube.com/watch?v=RgJjVgi7rZY
#     "WSU Volleyball: #25 USC at #9 Washington State | Full Match | 11/12/23"
#   Prepared: downloaded at 720p, audio track stripped (ffmpeg -an) so the task is
#     single-modality video, then re-hosted at a stable URL so the bytes are pinned.
#
# Baked 2026-07-15 via environment/bake_media.sh (yt-dlp 720p + ffmpeg -an) and
# uploaded to the dataset repo below; the build verifies the SHA256.
# Pinned to an immutable dataset revision, so the URL cannot start serving other
# bytes if the dataset's main branch moves; the SHA256 below is checked regardless.
ARG MATERIALS_REVISION=7dc08d8a25c1192b411f586e60db6542776ae075
ARG MATERIALS_URL=https://huggingface.co/datasets/gavinlaw/agentic-vbench-media/resolve/${MATERIALS_REVISION}/usc-wsu-2023-11-12-720p-noaudio.mp4
ARG MATERIALS_SHA256=13ccbabbdd9540da851099d138bef3c8eafe6de9426c3681593edba32d08ba9e
RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MATERIALS_URL" -o /baked/match.mp4 \
 && echo "${MATERIALS_SHA256}  /baked/match.mp4" | sha256sum -c - \
 && test -s /baked/match.mp4

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
