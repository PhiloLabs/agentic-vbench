FROM --platform=linux/amd64 python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Precision cut verifier deps: numpy + scikit-image (SSIM) for honesty gate,
# stdlib wave for audio xcorr. No transcription needed.
RUN pip install --no-cache-dir \
        "numpy<3" \
        "scikit-image>=0.22,<1.0" \
        "scipy>=1.10"

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
