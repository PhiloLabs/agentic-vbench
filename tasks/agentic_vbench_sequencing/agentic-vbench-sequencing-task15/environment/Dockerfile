FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg unzip curl ca-certificates libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Verifier deps installed at build time (no trial-time pip install).
RUN pip install --no-cache-dir \
        "numpy<3" "opencv-python-headless==4.13.*"

# Bake task materials at build time from the public video dataset.
# Workers pull this prebuilt image — no trial-time HF fetch.
ARG MATERIALS_URL=https://huggingface.co/datasets/ameddserM/agentic_vbench_video_sequencing/resolve/00e704c2053e2260a40ef8432fe34af8258888d3/materials/15.zip
ARG MATERIALS_SHA256=d9d1e0aa59c1c0292a79ed93545d4e3db69dad4877f351dfb2e819d1f6915ecb
RUN mkdir -p /baked/materials \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MATERIALS_URL" -o /tmp/m.zip \
 && echo "${MATERIALS_SHA256}  /tmp/m.zip" | sha256sum -c - \
 && unzip -q /tmp/m.zip -d /baked/materials/ \
 && rm /tmp/m.zip

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
