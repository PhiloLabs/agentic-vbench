FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The agent uses ffmpeg/ffprobe to seek, sample frames, and extract audio. The grader
# is pure stdlib (it only compares integers and strings), so it needs nothing extra.

# Bake the full-game broadcast at build time, the same way the v1.0 families do, with a
# pinned URL and a SHA256 verified at build. The file is a pre-existing archive.org
# upload; it is pinned directly (pin, not re-host), matching the gsw-cle worked example.
#
# SHA256 computed by streaming the archive.org file through sha256sum (2026-07-25).
ARG MATERIALS_URL=https://archive.org/download/youtube-noLK78Hgq0A/noLK78Hgq0A.mp4
ARG MATERIALS_SHA256=ba2281d6293b3ee6a180decd508bb871de581841e6ea183ac17455c0344ba998
RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MATERIALS_URL" -o /baked/game.mp4 \
 && echo "${MATERIALS_SHA256}  /baked/game.mp4" | sha256sum -c - \
 && test -s /baked/game.mp4

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
