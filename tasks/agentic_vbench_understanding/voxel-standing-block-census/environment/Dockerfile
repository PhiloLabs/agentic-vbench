FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg libgl1 libglib2.0-0 ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Numerics and imaging, pinned. Everything an agent needs to decode frames,
# difference them, and keep its own tallies.
RUN pip install --no-cache-dir \
        numpy==1.26.4 \
        scipy==1.13.1 \
        pandas==2.2.2 \
        scikit-image==0.24.0 \
        opencv-python-headless==4.10.0.84 \
        imageio==2.34.2 \
        imageio-ffmpeg==0.5.1 \
        pillow==10.4.0

RUN mkdir -p /workspace/materials /workspace/output /workspace/work

# The recording is 3.1 GB, too large to carry in the repository, so it is
# fetched at build time and checksummed, the convention this task family uses
# for archive.org and YouTube sources. It is generated for this task from a
# private world seed by a mod written for it, so there is nothing else online
# that matches and nothing for an agent to look up. Build needs network;
# solve does not, and allow_internet=false removes it at runtime.
ARG MEDIA_URL=https://huggingface.co/datasets/Maxine668/avb-luanti-standing-census/resolve/b026589248041ff49ab3da6b5eed142d13d56d55/session.mp4
ARG MEDIA_SHA256=fbf581836598383a4186554a2604e3a3b412954618070b3d681ccc743cf4a327
RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    curl -fL --retry 5 --retry-delay 5 -o /workspace/materials/session.mp4 "$MEDIA_URL" && \
    echo "$MEDIA_SHA256  /workspace/materials/session.mp4" | sha256sum -c - && \
    apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
