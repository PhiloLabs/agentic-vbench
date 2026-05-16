# linux/amd64 so the verifier's pesq sdist compiles cleanly (no
# manylinux_aarch64 wheel on PyPI). On arm64 hosts (e.g. Apple Silicon)
# docker runs this via qemu.
FROM --platform=linux/amd64 python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        ca-certificates \
        gcc \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
