FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ARG MATERIALS_URL=https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/main/kart-race-telemetry-ledger-s1/race.mp4
ARG MATERIALS_SHA256=2abab6e172b2c828ce961474733007ae4f584cdf1d0e728e29147a3f4ec1eaf2
RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 "$MATERIALS_URL" -o /baked/race.mp4 \
 && echo "${MATERIALS_SHA256}  /baked/race.mp4" | sha256sum -c - && test -s /baked/race.mp4
WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
