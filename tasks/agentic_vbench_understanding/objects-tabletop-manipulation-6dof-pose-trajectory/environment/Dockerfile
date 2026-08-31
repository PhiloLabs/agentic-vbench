FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The agent uses ffmpeg/ffprobe to seek and sample the clips. The grader is pure
# stdlib + numpy (it transforms baked mesh points by the reported poses).
RUN pip install --no-cache-dir numpy==2.1.3

# Bake only the agent-facing materials at build time: the three clips, the camera
# intrinsics, the query list, the target-object names, and the object point sets (the
# canonical mesh points the pose is defined against, so the task is solvable). Each is
# pinned with a SHA256 verified at build. Media hosted on Hugging Face, same host as the
# v1.0 families. The answer key (the poses) is NOT in the image: it ships verifier-side
# (steps/solve/tests/ for the grader, a copy in steps/solve/solution/ for the oracle).
ARG MATERIALS_BASE=https://huggingface.co/datasets/yalesunxiatao/agentic_vbench_understanding_objects/resolve/main
ARG CLIP01_SHA256=aefb41b216cc2cbacfca639de8175a29f37006c3be730b118928ce20e27d19ee
ARG CLIP02_SHA256=b187d5cbaba972ca715f0ffd670b99b1c77ee9ad579d40b3acdff1b564c114ae
ARG CLIP03_SHA256=56c42f94baecf5a78e2b6e32ed5af59719b51badfc6405d3f67d9b26bbc77520
ARG CAMERAS_SHA256=753c37861a52a82d0689a571afed6ce5f90dcc358367a54c8a637919fb565d1c
ARG QUERIES_SHA256=f9f4f7ec0f65d0bbec38a700e2c3492579f2dc9d44c569643f94cb8c23b150ae
ARG OBJECTS_SHA256=cc9906530da3bfd8b6a97a7586cfc541b23a3e8e2cbe4b9f77e2362562c82f19
ARG OBJECT_POINTS_SHA256=da0889b30ec5dee3723533ab85fa819ec2e49988ee99b76c69669b64ccea22eb

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
      "${MATERIALS_BASE}/objects.json" -o /baked/objects.json \
 && echo "${OBJECTS_SHA256}  /baked/objects.json" | sha256sum -c - \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "${MATERIALS_BASE}/object_points.json" -o /baked/object_points.json \
 && echo "${OBJECT_POINTS_SHA256}  /baked/object_points.json" | sha256sum -c - \
 && test -s /baked/clip_01.mp4 && test -s /baked/clip_02.mp4 && test -s /baked/clip_03.mp4

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
