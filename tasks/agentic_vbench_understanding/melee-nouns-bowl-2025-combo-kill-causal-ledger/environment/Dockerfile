FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg ca-certificates curl nodejs npm ripgrep \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g @openai/codex@0.147.0-alpha.6.5

COPY fetch_youtube.py /usr/local/bin/fetch_youtube.py
COPY concat.txt /baked/concat.txt

ARG MATERIALS_URL=
ARG FERRISWHEEL_ZAIN_SHA256=4b9a6da0b6ee68488e2eb32a90fb3319d17b1f7bb1245c437d63dedfba462ec4
ARG JOJO_BARD_SHA256=d726413360a809da8a72ec0289c9ab731b9e2b98a4dbee8562e7fe3b3bc9f7d2
ARG AXE_SRM13_SHA256=af05250e0c2f7ff9744968a6a1df13bed8de83d6d66db72b731912ad61fe0a01
ARG MATERIALS_SHA256=02f18fd7f4796800eece0400b1b1f315a36778b57b9ef4a64d1b30aa3b539749
RUN mkdir -p /baked/parts \
 && if [ -n "$MATERIALS_URL" ]; then \
      curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
        "$MATERIALS_URL" -o /baked/match.mp4; \
      echo "${MATERIALS_SHA256}  /baked/match.mp4" | sha256sum -c -; \
    else \
      python3 /usr/local/bin/fetch_youtube.py --video-id 3VJYGJ3KrZM --itag 298 \
        --output /baked/parts/ferriswheel-zain.mp4; \
      python3 /usr/local/bin/fetch_youtube.py --video-id tmZTwrLVceI --itag 298 \
        --output /baked/parts/jojo-bard.mp4; \
      python3 /usr/local/bin/fetch_youtube.py --video-id 44jQnPR24zM --itag 298 \
        --output /baked/parts/axe-srm13.mp4; \
      echo "${FERRISWHEEL_ZAIN_SHA256}  /baked/parts/ferriswheel-zain.mp4" | sha256sum -c -; \
      echo "${JOJO_BARD_SHA256}  /baked/parts/jojo-bard.mp4" | sha256sum -c -; \
      echo "${AXE_SRM13_SHA256}  /baked/parts/axe-srm13.mp4" | sha256sum -c -; \
      ffmpeg -v error -f concat -safe 0 -i /baked/concat.txt -c copy \
        -movflags +faststart /baked/match.mp4; \
    fi \
 && printf '%s  /baked/match.mp4\n' "$MATERIALS_SHA256" | sha256sum -c - \
 && ffprobe -v error -select_streams v:0 \
      -show_entries stream=width,height,r_frame_rate -show_entries format=duration \
      -of default=noprint_wrappers=1 /baked/match.mp4 \
 && rm -rf /baked/parts /usr/local/bin/fetch_youtube.py

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
