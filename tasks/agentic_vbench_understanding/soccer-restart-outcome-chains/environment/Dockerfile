FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The agent uses ffmpeg/ffprobe to seek and sample the broadcast. The grader is pure
# stdlib (it only compares tuples), so it needs nothing extra.

# Bake the full-match broadcast at build time, verified by SHA256.
#
# Provenance. The source is the Bundesliga's own YouTube upload of the match,
#   https://www.youtube.com/watch?v=U-Glif5abSY
#   "Borussia Dortmund vs. Bayer 04 Leverkusen | Full Game | 2016/17 Season"
# which is SoccerNet-v2's germany_bundesliga/2016-2017 "2017-03-04 - 17-30 Dortmund
# 6 - 2 Bayer Leverkusen", the match the answer key is derived from. The baked file is
# YouTube format 136 of that upload exactly as served: 1280x720 H.264 at 25 fps, video
# only, 6426.52 s, 1,836,710,763 bytes. It is not re-encoded, trimmed or remuxed, so the
# digest below is the publisher's own stream and anyone with yt-dlp can re-derive it.
#
# By default the build fetches it with a pinned yt-dlp, the way the merged dota2 and
# pac12 tasks do. MATERIALS_URL, when set, fetches the same bytes from a mirror instead;
# the digest check is the same either way.
ARG YT_DLP_VERSION=2026.8.19
ARG VIDEO_ID=U-Glif5abSY
ARG VIDEO_FORMAT=136
ARG MATERIALS_URL=
ARG MATERIALS_SHA256=7648b622c196ca5c844eb6162dfda2532d8e46ced99728f720f62fb6d3d695e2
RUN mkdir -p /baked \
 && if [ -n "$MATERIALS_URL" ]; then \
        curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
          "$MATERIALS_URL" -o /baked/game.mp4; \
    else \
        pip install --no-cache-dir --root-user-action=ignore "yt-dlp==${YT_DLP_VERSION}" \
        && yt-dlp --no-warnings --no-playlist --format "$VIDEO_FORMAT" \
             --output /baked/game.mp4 "https://www.youtube.com/watch?v=${VIDEO_ID}" \
        && pip uninstall -y yt-dlp; \
    fi \
 && echo "${MATERIALS_SHA256}  /baked/game.mp4" | sha256sum -c - \
 && test -s /baked/game.mp4

# Build-time assertions on the baked media, so a silently different file cannot ship.
# The task is answered from the picture alone and the stream carries no audio.
RUN set -eu; \
    DUR=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 /baked/game.mp4); \
    H=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of default=nw=1:nk=1 /baked/game.mp4); \
    A=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 /baked/game.mp4 | wc -l); \
    echo "duration=$DUR height=$H audio_streams=$A"; \
    test "$H" -ge 720; \
    test "$A" -eq 0; \
    python3 -c "import sys; d=float('$DUR'); sys.exit(0 if 6420 < d < 6430 else 1)"

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
