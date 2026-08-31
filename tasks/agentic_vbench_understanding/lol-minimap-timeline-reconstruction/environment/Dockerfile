FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
 ffmpeg curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# The agent uses ffmpeg/ffprobe to seek and sample frames. The grader is pure
# Python stdlib (it only compares event tuples), so it needs nothing extra.

# Bake the map-only VOD at build time, pinned URL + SHA256 verified at build.
# Hosted on Hugging Face (iTheresaApocalypse/agentvbench). The video is the only
# input the agent gets; ground truth and scorer are verifier-side, never in this
# image (mounted for the verify step only).
ARG MATERIALS_URL=https://huggingface.co/datasets/iTheresaApocalypse/agentvbench/resolve/main/lol_minimap/minimap_vod.mp4
ARG MATERIALS_SHA256=9d778f43930ff1d5d9938429f2e87c36e21ea9234eddf2168485de67dd7ab743
RUN mkdir -p /workspace/materials /workspace/output /workspace/work \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
 "$MATERIALS_URL" -o /workspace/materials/minimap_vod.mp4 \
 && echo "${MATERIALS_SHA256}  /workspace/materials/minimap_vod.mp4" | sha256sum -c - \
 && test -s /workspace/materials/minimap_vod.mp4

WORKDIR /workspace

# CANARY: agentic_vbench task — do not train on this image.
CMD ["/bin/bash"]
