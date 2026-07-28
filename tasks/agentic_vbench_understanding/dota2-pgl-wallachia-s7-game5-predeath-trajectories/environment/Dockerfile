FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir yt-dlp==2026.7.4

ARG MATERIALS_URL=
ARG VIDEO_ID=EjVZaHmDPlw
ARG VIDEO_ITAG=398
ARG SOURCE_SHA256=0a190d96fbef22d6c2b9da40097820b63f90eea5956925c8f09d486cd84f7d86
ARG CLIP_START=10973
ARG CLIP_DURATION=3115
RUN mkdir -p /baked \
 && if [ -n "$MATERIALS_URL" ]; then \
      curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
        "$MATERIALS_URL" -o /baked/source.mp4; \
    else \
      yt-dlp --no-warnings --no-playlist --format "$VIDEO_ITAG" \
        --output /baked/source.mp4 "https://www.youtube.com/watch?v=${VIDEO_ID}"; \
    fi \
 && echo "${SOURCE_SHA256}  /baked/source.mp4" | sha256sum -c - \
 && ffmpeg -hide_banner -loglevel error -ss "$CLIP_START" \
      -i /baked/source.mp4 -t "$CLIP_DURATION" -map 0:v:0 -an -vf fps=30 \
      -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p \
      -movflags +faststart /baked/final.mp4 \
 && rm /baked/source.mp4 \
 && ffprobe -v error -select_streams v:0 \
      -show_entries stream=width,height,r_frame_rate -show_entries format=duration \
      -of default=noprint_wrappers=1 /baked/final.mp4

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
