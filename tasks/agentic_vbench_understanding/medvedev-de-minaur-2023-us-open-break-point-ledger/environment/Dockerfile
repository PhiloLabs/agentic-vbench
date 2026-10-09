FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# The original official source is https://www.youtube.com/watch?v=kYxKCsl4uN0.
# Its high-resolution formats require a short-lived, video-specific PO token, so
# bake the verified 720p reconstruction from a pinned release asset instead. The
# source contains commentary, so expose only a lossless copy of its video stream.
ARG MATERIALS_SOURCE_URL=https://github.com/inFaaa/agentic-vbench/releases/download/medvedev-de-minaur-2023-us-open-r4-media-v1/medvedev-de-minaur-2023-us-open-r4-720p.mp4
ARG MATERIALS_SOURCE_SHA256=d78c9246d5dd36b812c71b5f39bfa43ab86d1a7adf711fb7bbc6ff1d66d618b2

RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MATERIALS_SOURCE_URL" -o /tmp/match-with-audio.mp4 \
 && echo "${MATERIALS_SOURCE_SHA256}  /tmp/match-with-audio.mp4" | sha256sum -c - \
 && ffmpeg -v error -i /tmp/match-with-audio.mp4 -map 0:v:0 -c:v copy -an \
      -map_metadata -1 -movflags +faststart /baked/match.mp4 \
 && rm /tmp/match-with-audio.mp4 \
 && test -s /baked/match.mp4 \
 && test "$(ffprobe -v error -select_streams v:0 -show_entries stream=width \
      -of default=noprint_wrappers=1:nokey=1 /baked/match.mp4)" = "1280" \
 && test "$(ffprobe -v error -select_streams v:0 -show_entries stream=height \
      -of default=noprint_wrappers=1:nokey=1 /baked/match.mp4)" = "720" \
 && test -z "$(ffprobe -v error -select_streams a \
      -show_entries stream=index -of csv=p=0 /baked/match.mp4)"

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
