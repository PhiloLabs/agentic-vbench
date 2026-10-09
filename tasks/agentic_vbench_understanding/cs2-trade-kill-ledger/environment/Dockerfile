FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The agent uses ffmpeg/ffprobe to seek and sample the ten POV renders. The grader
# is pure stdlib, so it needs nothing extra.

# Bake the renders at build time, pinned per file with SHA256, the same pattern as
# the family's other tasks. The archive.org item holds P1.mp4..P10.mp4: ten
# time-aligned 720p30 first-person POV renders of the full match, HUD stripped.
# check_task.py probes ${MATERIALS_BASE_URL}/P1.mp4 directly with ffprobe.
#
# TODO(render): the renders do not exist yet. Once rendered and uploaded to the
# archive.org item, set the base URL and the ten SHA256s and delete the guard.
# The .dem itself must NEVER be baked into this image or be reachable from it.
ARG MATERIALS_BASE_URL=TODO_ARCHIVE_ORG_ITEM_URL_AFTER_RENDER
ARG MATERIALS_SHA256S=TODO_TEN_SHA256S_ONE_PER_POV_IN_ORDER
RUN if [ "$MATERIALS_BASE_URL" = "TODO_ARCHIVE_ORG_ITEM_URL_AFTER_RENDER" ]; then \
        echo "ERROR: materials not yet rendered/hosted; fill MATERIALS_BASE_URL and MATERIALS_SHA256S" >&2; \
        exit 1; \
    fi \
 && mkdir -p /baked \
 && set -- $MATERIALS_SHA256S \
 && for k in $(seq 1 10); do \
        curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
          "${MATERIALS_BASE_URL}/P${k}.mp4" -o "/baked/P${k}.mp4" \
        && echo "$1  /baked/P${k}.mp4" | sha256sum -c - \
        && test -s "/baked/P${k}.mp4" \
        && shift; \
    done

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
