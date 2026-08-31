FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

ARG MATERIALS_URL=https://archive.org/download/checkpoint-sequence-recording-01/doom-checkpoint-state-tracking.mp4
ARG MATERIALS_SHA256=257680b3284d97a108b779fab034f5ad8d89ed08db4527bd203a601806b5736c

RUN mkdir -p /baked
RUN curl -fL --retry 3 "$MATERIALS_URL" \
      -o /baked/doom-checkpoint-state-tracking.mp4 \
 && echo "$MATERIALS_SHA256  /baked/doom-checkpoint-state-tracking.mp4" \
      | sha256sum -c - \
 && cd /baked \
 && ffprobe -v error -select_streams v:0 \
      -show_entries stream=width,height:format=duration \
      -of json doom-checkpoint-state-tracking.mp4 > /tmp/media-probe.json \
 && test -s doom-checkpoint-state-tracking.mp4

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
