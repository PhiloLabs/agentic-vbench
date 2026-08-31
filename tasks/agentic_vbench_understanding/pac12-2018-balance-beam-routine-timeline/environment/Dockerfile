FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Bake the exact public broadcast at image-build time. The explicit YouTube
# format pair produces the calibrated 1280x720 H.264 + Opus source, and the
# digest gate prevents a silent source revision from entering a trial.
ARG YT_DLP_VERSION=2026.7.4
ARG MATERIALS_URL=https://www.youtube.com/watch?v=0LtLS9wROrk
ARG MATERIALS_SHA256=7dfc9e139254cc9480948af734988bdebc796c89c6e5d439055a248c251130cb

RUN python -m pip install --no-cache-dir "yt-dlp==${YT_DLP_VERSION}" \
 && mkdir -p /baked \
 && yt-dlp --no-playlist \
      --format "136+251" \
      --merge-output-format mp4 \
      --output /baked/source.mp4 \
      "$MATERIALS_URL" \
 && echo "${MATERIALS_SHA256}  /baked/source.mp4" | sha256sum -c - \
 && test -s /baked/source.mp4

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
