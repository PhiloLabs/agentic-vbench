FROM --platform=linux/amd64 python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates gcc g++ python3-dev \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
        "numpy<3" \
        "opencv-python-headless==4.13.*"

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
