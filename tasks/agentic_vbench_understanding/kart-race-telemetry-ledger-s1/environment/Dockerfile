FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ARG MATERIALS_URL=https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/main/kart-race-telemetry-ledger-s1/race.mp4
ARG MATERIALS_SHA256=4b4cee91675cf7b9699e645dc490343026a7022a2de008b7e1397c69ee59eb42
RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 "$MATERIALS_URL" -o /baked/race.mp4 \
 && echo "${MATERIALS_SHA256}  /baked/race.mp4" | sha256sum -c - && test -s /baked/race.mp4
WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
