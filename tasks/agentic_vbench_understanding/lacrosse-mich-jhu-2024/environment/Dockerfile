FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The agent uses ffmpeg/ffprobe to seek and sample frames from the broadcast.
# The grader is pure stdlib (it only compares integers and strings).

# Bake the masked broadcast at build time with a pinned URL + SHA-256, the same
# way the v1.0 families do. The sha256sum check is a build gate: if the fetched
# bytes do not match the pin, `sha256sum -c` exits non-zero and the BUILD FAILS,
# so a wrong or re-encoded video can never reach the agent or the grader (the
# ground-truth timings are only valid for this exact encode).
ARG MATERIALS_URL=https://huggingface.co/datasets/willw96/agentic_vbench_lacrosse/resolve/main/game.mp4
ARG MATERIALS_SHA256=7e53feeb327da479448203385e3b76016bf9c78f78422bb715a7f906b0429a34
RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MATERIALS_URL" -o /baked/game.mp4 \
 && echo "${MATERIALS_SHA256}  /baked/game.mp4" | sha256sum -c - \
 && test -s /baked/game.mp4

# Small agent-visible materials travel with the image (closed roster + schema).
COPY roster.json schema.json /baked/

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
