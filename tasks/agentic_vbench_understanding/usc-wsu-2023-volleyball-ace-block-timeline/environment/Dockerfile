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
#     https://www.youtube.com/watch?v=RgJjVgi7rZY
#     "WSU Volleyball: #25 USC at #9 Washington State | Full Match | 11/12/23"
#   Prepared: downloaded at 720p, audio track stripped (ffmpeg -an) so the task is
#     single-modality video, then re-hosted at a stable URL so the bytes are pinned.
#
# NOTE: MATERIALS_SHA256 below is a placeholder pending the one-time bake+upload
# (run environment/bake_media.sh, upload the .mp4 to the dataset repo, then paste the
# printed sha256 here). The build verifies the hash, so it will fail loudly until set.
ARG MATERIALS_URL=https://huggingface.co/datasets/gavinlaw/agentic-vbench-media/resolve/main/usc-wsu-2023-11-12-720p-noaudio.mp4
ARG MATERIALS_SHA256=PENDING_BAKE_UPLOAD
RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MATERIALS_URL" -o /baked/match.mp4 \
 && echo "${MATERIALS_SHA256}  /baked/match.mp4" | sha256sum -c - \
 && test -s /baked/match.mp4

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
