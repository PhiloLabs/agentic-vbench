FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 --shell /bin/bash agent

# The answer key is NOT baked into this image. It ships only in the task's
# steps/solve/tests/ directory, which Harbor uploads to /tests inside the
# verifier phase (user = root). This task has a single step, so /tests never
# exists while the agent phase is running.

ARG MEDIA_URL=https://huggingface.co/datasets/Jordan8717/agentic-vbench-meva-activity-ledgers/resolve/c3c7b0dc1d8cba7834564350b90d0c96b4178d46/meva_activity_montage.mp4
ARG MEDIA_SHA256=2d51338a954cb726037116b9b9715ef8dccb7c242753a0e709a03c266fbce344
ARG ROSTER_URL=https://huggingface.co/datasets/Jordan8717/agentic-vbench-meva-activity-ledgers/resolve/c3c7b0dc1d8cba7834564350b90d0c96b4178d46/meva_roster.tar.gz
ARG ROSTER_SHA256=1b2d92993f8509c71688ae6721b76a50a3dc82a419dce222ef80b84fb3de1487

RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MEDIA_URL" -o /baked/meva_activity_montage.mp4 \
 && echo "${MEDIA_SHA256}  /baked/meva_activity_montage.mp4" | sha256sum -c - \
 && test -s /baked/meva_activity_montage.mp4 \
 && test "$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 /baked/meva_activity_montage.mp4)" = "600.000000" \
 && test "$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of default=nw=1:nk=1 /baked/meva_activity_montage.mp4)" = "1080" \
 && test "$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 /baked/meva_activity_montage.mp4 | wc -l)" = "0"

RUN curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$ROSTER_URL" -o /tmp/meva_roster.tar.gz \
 && echo "${ROSTER_SHA256}  /tmp/meva_roster.tar.gz" | sha256sum -c - \
 && tar -xzf /tmp/meva_roster.tar.gz -C /baked \
 && rm /tmp/meva_roster.tar.gz \
 && test -s /baked/roster.json \
 && test "$(find /baked/roster -type f -name 'reference_*.jpg' | wc -l)" = "10"

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
RUN chown -R agent:agent /workspace

# CANARY: agentic_vbench task — do not train on this image.
CMD ["/bin/bash"]
