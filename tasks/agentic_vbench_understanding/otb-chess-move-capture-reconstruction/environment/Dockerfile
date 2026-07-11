FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir yt-dlp==2026.7.4

# Bake the source video at build time. The source stream is pinned by SHA256
# before the agent-facing material is generated.
ARG SOURCE_URL=https://www.youtube.com/watch?v=xwoRCwMRE54
ARG SOURCE_SHA256=91d05bdf6138e232894cf826b18de91824c2bd9b1dc5045f0fbe40ac4aceb4b8
RUN mkdir -p /baked \
 && python3 -m yt_dlp --no-warnings -f "298" \
      -o "/baked/source.%(ext)s" "$SOURCE_URL" \
 && echo "${SOURCE_SHA256}  /baked/source.mp4" | sha256sum -c - \
 && ffmpeg -hide_banner -loglevel error -y -i /baked/source.mp4 \
      -map 0:v:0 \
      -vf "drawbox=x=488:y=0:w=430:h=407:color=black:t=fill,drawbox=x=0:y=615:w=112:h=105:color=black:t=fill,drawbox=x=1078:y=612:w=202:h=108:color=black:t=fill" \
      -an -map_metadata -1 -map_chapters -1 \
      -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p /baked/game.mp4 \
 && rm /baked/source.mp4 \
 && test -s /baked/game.mp4

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
