FROM --platform=linux/amd64 python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
        "numpy<3" \
        "opencv-python-headless==4.13.*" \
        "scikit-image==0.26.*" \
        "colour-science==0.4.*"

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
