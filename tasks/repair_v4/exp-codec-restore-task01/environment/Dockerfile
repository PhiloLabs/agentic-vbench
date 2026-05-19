FROM --platform=linux/amd64 python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        ca-certificates \
        gcc \
        python3-dev \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
