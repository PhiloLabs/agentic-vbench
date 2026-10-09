FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY fetch_youtube.py /usr/local/bin/fetch_youtube.py

ARG MATERIALS_URL=https://github.com/shengjun-zhang/agentic-vbench/releases/download/robocup-possession-chain-media-20260911/match.mp4
ARG VIDEO_ID=364zEAsOclU
ARG MATERIALS_SHA256=076bcc59fc48443d24a72a87162021470b9e645b41c858c3ffa5b5b25bae36cd
ARG VIDEO_WIDTH=1280
ARG VIDEO_HEIGHT=720
ARG VIDEO_FRAME_RATE=50/1
ARG VIDEO_DURATION=880.640000
RUN mkdir -p /baked \
 && if [ -n "$MATERIALS_URL" ]; then \
      curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
        "$MATERIALS_URL" -o /baked/match.mp4; \
    else \
      python3 /usr/local/bin/fetch_youtube.py \
        --video-id "$VIDEO_ID" --itag 298 --output /baked/match.mp4; \
    fi \
 && echo "${MATERIALS_SHA256}  /baked/match.mp4" | sha256sum -c - \
 && test "$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 /baked/match.mp4)" = "$VIDEO_WIDTH" \
 && test "$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 /baked/match.mp4)" = "$VIDEO_HEIGHT" \
 && test "$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of csv=p=0 /baked/match.mp4)" = "$VIDEO_FRAME_RATE" \
 && test "$(ffprobe -v error -show_entries format=duration -of csv=p=0 /baked/match.mp4)" = "$VIDEO_DURATION" \
 && ffprobe -v error -select_streams v:0 \
      -show_entries stream=width,height,r_frame_rate -show_entries format=duration \
      -of default=noprint_wrappers=1 /baked/match.mp4

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
