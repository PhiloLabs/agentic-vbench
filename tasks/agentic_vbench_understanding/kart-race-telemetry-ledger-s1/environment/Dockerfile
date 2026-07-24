FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ARG MATERIALS_URL=https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/main/kart-race-telemetry-ledger-s1/race.mp4
ARG MATERIALS_SHA256=ceffb7b11c29f01f7f7603a7bca8db0ae38937ded14ff750bba9b79d87e54ddf
RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 "$MATERIALS_URL" -o /baked/race.mp4 \
 && echo "${MATERIALS_SHA256}  /baked/race.mp4" | sha256sum -c - && test -s /baked/race.mp4
WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
