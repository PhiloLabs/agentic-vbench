FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG MATERIALS_REVISION=457f5752fcd2c08b7b47889a8061535b80f1edc7
ARG VIDEO_URL=https://huggingface.co/datasets/Jordan8717/agentic-vbench-europarl/resolve/${MATERIALS_REVISION}/debate.mp4
ARG VIDEO_SHA256=844fb01dd7806105ebdde677d190822f80e46c2d140c7499006b20345870e1b7
ARG ROSTER_URL=https://huggingface.co/datasets/Jordan8717/agentic-vbench-europarl/resolve/${MATERIALS_REVISION}/roster.tar.gz
ARG ROSTER_SHA256=c233ecc799a025badd1d6f3d6818ea1dca392fafab2ac2c3f4481a31e664966b

RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$VIDEO_URL" -o /baked/debate.mp4 \
 && echo "${VIDEO_SHA256}  /baked/debate.mp4" | sha256sum -c - \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$ROSTER_URL" -o /tmp/roster.tar.gz \
 && echo "${ROSTER_SHA256}  /tmp/roster.tar.gz" | sha256sum -c - \
 && tar -xzf /tmp/roster.tar.gz -C /baked \
 && rm /tmp/roster.tar.gz \
 && test -s /baked/debate.mp4 \
 && test -s /baked/roster.json \
 && test "$(find /baked/roster -type f -name 'speaker_*.jpg' | wc -l)" = "79" \
 && test "$(ffprobe -v error -show_entries format=start_time -of default=nw=1:nk=1 /baked/debate.mp4)" = "0.000000" \
 && test "$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 /baked/debate.mp4)" = "7662.000000" \
 && test "$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of default=nw=1:nk=1 /baked/debate.mp4)" = "1080" \
 && test "$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 /baked/debate.mp4 | wc -l)" = "1"

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work

# CANARY: agentic_vbench task — do not train on this image.
CMD ["/bin/bash"]
