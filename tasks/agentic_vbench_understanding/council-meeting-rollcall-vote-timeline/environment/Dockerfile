FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Bake the full Issaquah City Council meeting video at build time. The direct
# archive.org file is pinned by SHA256 so the task material is stable.
ARG MATERIALS_URL=https://archive.org/download/ciwa-Issaquah_City_Council_Regular_Meeting_-_December_6_2021/Issaquah_City_Council_Regular_Meeting_-_December_6_2021.HD.mov?download=1
ARG MATERIALS_SHA256=d7a08e70571efdfa2ffa9e9e2ed2f98064337b86892916943c218af78bb8a6f1
RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MATERIALS_URL" -o /baked/meeting.mov \
 && echo "${MATERIALS_SHA256}  /baked/meeting.mov" | sha256sum -c - \
 && test -s /baked/meeting.mov

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
