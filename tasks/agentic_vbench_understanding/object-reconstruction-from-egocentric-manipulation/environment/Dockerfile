# python:3.12-slim, digest-pinned so the base cannot drift after merge
FROM python@sha256:423ed6ab25b1921a477529254bfeeabf5855151dc2c3141699a1bfc852199fbf

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The agent uses ffmpeg/ffprobe to seek and sample the clips. The grader samples and
# aligns point clouds, so it needs numpy + scipy + trimesh.
RUN pip install --no-cache-dir numpy==2.1.3 scipy==1.14.1 trimesh==4.5.3

# Bake only the agent-facing materials at build time (the three clips, the camera
# intrinsics, and the target-object names), each pinned with a SHA256 verified at build.
# Media hosted on Hugging Face, same host as the v1.0 families. The reference meshes are
# the answer key and are NOT in the image: they ship verifier-side (a copy in
# steps/solve/solution/ for the oracle), and the grader scores against the point set
# baked into steps/solve/tests/ground_truth.json. So the agent never sees a reference mesh.
ARG MATERIALS_BASE=https://huggingface.co/datasets/yalesunxiatao/agentic_vbench_understanding_recon/resolve/ab18893ae61a4050aa80c383bf18ee6e9be326da
ARG CLIP01_SHA256=2f153d49b5c6b61e58d6b648af1002718dddd2fe2b32c6ba28d4e9d80d388a1c
ARG CLIP02_SHA256=56c42f94baecf5a78e2b6e32ed5af59719b51badfc6405d3f67d9b26bbc77520
ARG CLIP03_SHA256=9d2cd0f8127622bc5805f4cbaf83efcbf17a9ad8d1f46748a26a9ccb7c5ab546
ARG CAMERAS_SHA256=753c37861a52a82d0689a571afed6ce5f90dcc358367a54c8a637919fb565d1c
ARG OBJECTS_SHA256=08ceed454127f4d8f2186d92a97bfab7f3c183c58e348808ff863a020a857798

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
      "${MATERIALS_BASE}/objects.json" -o /baked/objects.json \
 && echo "${OBJECTS_SHA256}  /baked/objects.json" | sha256sum -c - \
 && test -s /baked/clip_01.mp4 && test -s /baked/clip_02.mp4 && test -s /baked/clip_03.mp4

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
