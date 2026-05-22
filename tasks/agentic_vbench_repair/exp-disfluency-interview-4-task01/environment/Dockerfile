FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg unzip curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Verifier deps installed at build time (no trial-time pip install).
RUN pip install --no-cache-dir \
        "numpy<3" "scikit-image>=0.22,<1.0" "scipy>=1.10"

# Bake task materials at build time. Zip contains input/+golden/ subdirs;
# input/ → agent's /workspace/materials/, golden/ → verifier's /tests/.
ARG MATERIALS_URL=https://huggingface.co/datasets/ameddserM/agentic_vbench_video_repair/resolve/main/materials/exp-disfluency-interview-4-task01.zip
RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MATERIALS_URL" -o /tmp/m.zip \
 && unzip -q /tmp/m.zip "input/*" -d /baked \
 && rm /tmp/m.zip

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
