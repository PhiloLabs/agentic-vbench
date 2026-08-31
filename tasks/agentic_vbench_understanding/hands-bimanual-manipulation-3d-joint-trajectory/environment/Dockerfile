FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The agent uses ffmpeg/ffprobe to seek and sample the clips. The grader is pure
# stdlib + numpy (it only compares 3D coordinates), installed here for the verifier.
RUN pip install --no-cache-dir numpy==2.1.3

# Bake only the agent-facing materials at build time (the three clips plus the camera
# intrinsics and query list), the same way the v1.0 families bake their media: a pinned
# URL with a SHA256 verified at build. The answer key is NOT part of the image. It ships
# on the verifier side (steps/solve/tests/ground_truth.json for the grader, and a copy in
# steps/solve/solution/ for the oracle), so the agent never has access to it.
ARG MATERIALS_BASE=https://huggingface.co/datasets/yalesunxiatao/agentic_vbench_understanding_hands/resolve/main
ARG CLIP01_SHA256=22d4f7e060ee79eb77eadd58b92c0f3a3e840640aba2f3afc6322aee47c8b729
ARG CLIP02_SHA256=5323761ef008f7f0e3d317a9b477c4f9ffd80da6da3504b3280324af93a47544
ARG CLIP03_SHA256=6fc266fd070b00e547642ef3e0613ef82ca13a58b8042a86c4259f7bf8269874
ARG CAMERAS_SHA256=753c37861a52a82d0689a571afed6ce5f90dcc358367a54c8a637919fb565d1c
ARG QUERIES_SHA256=f2dd1a835408b239b979b874c6bc09dee13a8b3bb87a970f1407a1163137bb88
ARG HAND_MODEL_SHA256=5ff5d0b0fa0dec2b6e52bce887299f6bfa2840cdf549eb6778c2f95cc6e0e50b

RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "${MATERIALS_BASE}/clip_01.mp4" -o /baked/clip_01.mp4 \
 && echo "${CLIP01_SHA256}  /baked/clip_01.mp4" | sha256sum -c - \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "${MATERIALS_BASE}/clip_02.mp4" -o /baked/clip_02.mp4 \
 && echo "${CLIP02_SHA256}  /baked/clip_02.mp4" | sha256sum -c - \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "${MATERIALS_BASE}/clip_03.mp4" -o /baked/clip_03.mp4 \
 && echo "${CLIP03_SHA256}  /baked/clip_03.mp4" | sha256sum -c - \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "${MATERIALS_BASE}/cameras.json" -o /baked/cameras.json \
 && echo "${CAMERAS_SHA256}  /baked/cameras.json" | sha256sum -c - \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "${MATERIALS_BASE}/queries.json" -o /baked/queries.json \
 && echo "${QUERIES_SHA256}  /baked/queries.json" | sha256sum -c - \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "${MATERIALS_BASE}/hand_model.json" -o /baked/hand_model.json \
 && echo "${HAND_MODEL_SHA256}  /baked/hand_model.json" | sha256sum -c - \
 && test -s /baked/clip_01.mp4 && test -s /baked/clip_02.mp4 && test -s /baked/clip_03.mp4

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
