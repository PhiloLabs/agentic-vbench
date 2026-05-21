FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg unzip curl ca-certificates libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Verifier deps installed at build time (no trial-time pip install).
RUN pip install --no-cache-dir \
        "numpy<3" "opencv-python-headless==4.13.*"

# Bake task materials at build time from the public video dataset.
# Workers pull this prebuilt image — no trial-time HF fetch.
ARG MATERIALS_URL=https://huggingface.co/datasets/ameddserM/agentic_vbench_video_sequencing/resolve/main/materials/21.zip
RUN mkdir -p /baked/materials \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MATERIALS_URL" -o /tmp/m.zip \
 && unzip -q /tmp/m.zip -d /baked/materials/ \
 && rm /tmp/m.zip

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
