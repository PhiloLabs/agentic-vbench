FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        unzip \
        curl \
        ca-certificates \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Verifier deps: SSIM-honesty gate uses opencv + numpy to read sampled
# frames from solution.mp4 and the candidate clips.
RUN pip install --no-cache-dir \
        "numpy<3" "opencv-python-headless==4.13.*"

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
