FROM --platform=linux/amd64 python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Precision cut verifier deps: numpy + scikit-image (SSIM honesty gate);
# opencv-python-headless retained for agents that want frame I/O.
RUN pip install --no-cache-dir \
        "numpy<3" \
        "opencv-python-headless==4.13.*" \
        "scikit-image>=0.22,<1.0"

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
