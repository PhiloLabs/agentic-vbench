ARG PYTHON_IMAGE=python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

FROM ${PYTHON_IMAGE} AS ffmpeg-build

ARG FFMPEG_COMMIT=8c62d77139ca07390414fcfd26b2a4d506fed3b9
ARG FFMPEG_SOURCE_SHA256=88f8bd47f57d8581cb2191f241720e0a4d3b44e4cef5ed091e1d465fcd140047

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /src/ffmpeg \
    && curl --fail --silent --show-error --location --retry 5 \
        "https://github.com/FFmpeg/FFmpeg/archive/${FFMPEG_COMMIT}.tar.gz" \
        -o /tmp/ffmpeg.tar.gz \
    && echo "${FFMPEG_SOURCE_SHA256}  /tmp/ffmpeg.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/ffmpeg.tar.gz --strip-components=1 -C /src/ffmpeg \
    && cd /src/ffmpeg \
    && ./configure \
        --prefix=/opt/media-ffmpeg \
        --disable-autodetect \
        --disable-debug \
        --disable-doc \
        --disable-everything \
        --disable-ffplay \
        --disable-ffprobe \
        --disable-x86asm \
        --enable-demuxer=mov \
        --enable-muxer=mp4 \
        --enable-parser=aac,h264 \
        --enable-protocol=file \
    && make -j"$(nproc)" \
    && make install

FROM ${PYTHON_IMAGE} AS media-build

ARG YTDLP_VERSION=2026.07.04
ARG YTDLP_SHA256=495be29ff4d9d4e9be7eabdfef225221e5d5282e77f2f505abc6dca80349f3fd
ARG MATERIALS_URL=https://www.youtube.com/watch?v=O669aZhH0LI
ARG VIDEO_FORMAT=136
ARG AUDIO_FORMAT=140
ARG VIDEO_SHA256=8d5bbc888e370491fa1349fc7f07cbe948fe5938af0399e0a5bd810d6fb5f6b1
ARG AUDIO_SHA256=749071aa052e7896970e53337d47b7206f746c66f28cc0710349c78b1f165bd5
ARG MATERIALS_SHA256=63e53e871beaa993ff69c210842ac6fc8e9a3290b7d6021daa5eab7a88cef95c

COPY --from=ffmpeg-build /opt/media-ffmpeg/bin/ffmpeg /usr/local/bin/media-ffmpeg

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl --fail --silent --show-error --location --retry 5 \
        "https://github.com/yt-dlp/yt-dlp/releases/download/${YTDLP_VERSION}/yt-dlp" \
        -o /usr/local/bin/yt-dlp \
    && echo "${YTDLP_SHA256}  /usr/local/bin/yt-dlp" | sha256sum -c - \
    && chmod +x /usr/local/bin/yt-dlp \
    && mkdir -p /baked /tmp/media \
    && yt-dlp --no-playlist --format "${VIDEO_FORMAT}" \
        --output /tmp/media/video.mp4 "${MATERIALS_URL}" \
    && yt-dlp --no-playlist --format "${AUDIO_FORMAT}" \
        --output /tmp/media/audio.m4a "${MATERIALS_URL}" \
    && echo "${VIDEO_SHA256}  /tmp/media/video.mp4" | sha256sum -c - \
    && echo "${AUDIO_SHA256}  /tmp/media/audio.m4a" | sha256sum -c - \
    && media-ffmpeg -hide_banner -loglevel error -y \
        -i /tmp/media/video.mp4 -i /tmp/media/audio.m4a \
        -c copy -movflags +faststart /baked/game.mp4 \
    && echo "${MATERIALS_SHA256}  /baked/game.mp4" | sha256sum -c -

FROM ${PYTHON_IMAGE}

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=media-build /baked/game.mp4 /baked/game.mp4
COPY court-grid.png /baked/court-grid.png

RUN echo "63e53e871beaa993ff69c210842ac6fc8e9a3290b7d6021daa5eab7a88cef95c  /baked/game.mp4" \
      | sha256sum -c - \
 && echo "c21425d4a358bdf9665e54feda8a7cedab2e3217a3fa8bddc32509cbc7536d08  /baked/court-grid.png" \
      | sha256sum -c -

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
