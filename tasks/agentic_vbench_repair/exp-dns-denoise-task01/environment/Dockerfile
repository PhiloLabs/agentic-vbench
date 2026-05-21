FROM --platform=linux/amd64 python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg unzip curl ca-certificates gcc python3-dev libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Verifier deps installed at build time (no trial-time pip install).
RUN pip install --no-cache-dir \
        "numpy<3" "scipy<2" "soundfile==0.13.*" "pesq==0.0.4" "pystoi==0.4.*" "onnxruntime"

# Bake task materials at build time. Zip contains input/+golden/ subdirs;
# input/ → agent's /workspace/materials/, golden/ → verifier's /tests/.
ARG MATERIALS_URL=https://huggingface.co/datasets/ameddserM/agentic_vbench_video_repair/resolve/main/materials/exp-dns-denoise-task01.zip
RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MATERIALS_URL" -o /tmp/m.zip \
 && unzip -q /tmp/m.zip -d /baked \
 && rm /tmp/m.zip

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
