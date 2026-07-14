FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The agent uses ffmpeg/ffprobe to seek and sample frames. The grader is pure
# stdlib (it only compares strings and integers), so it needs nothing extra.

# Bake the full-match broadcast at build time with a pinned URL and a SHA256
# verified at build, the same way the worked example does.
#
# Provenance and preparation (see environment/bake_media.sh):
#   Source: official WSU Athletics YouTube upload (1080p),
#     https://www.youtube.com/watch?v=5KC1jC90lT8
#     "WSU Volleyball: #8 BYU at #13 Washington State | Full Match | 9/8/23"
#   Prepared: downloaded at 720p, audio track stripped (ffmpeg -an) so the task is
#     single-modality video, then re-hosted at a stable URL so the bytes are pinned.
#   An archive.org mirror of the same upload exists (youtube-5KC1jC90lT8, 480p)
#     as a fallback provenance record.
#
ARG MATERIALS_URL=https://huggingface.co/datasets/gavinlaw/agentic-vbench-media/resolve/main/byu-wsu-2023-09-08-720p-noaudio.mp4
ARG MATERIALS_SHA256=ee887b18cf3dc9afce05087b24b629d1c44433344d7d4ccf612a4e548796dc60
RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MATERIALS_URL" -o /baked/match.mp4 \
 && echo "${MATERIALS_SHA256}  /baked/match.mp4" | sha256sum -c - \
 && test -s /baked/match.mp4

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
