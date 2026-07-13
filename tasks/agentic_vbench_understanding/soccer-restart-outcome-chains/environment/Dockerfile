FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The agent uses ffmpeg/ffprobe to seek and sample the broadcast. The grader is pure
# stdlib (it only compares tuples), so it needs nothing extra.

# Bake the full-match broadcast at build time from a pinned URL, verified by SHA256,
# the same pattern the v1.0 families (PR #10 / #37) and the understanding worked example
# use, and the same self-hosting pattern as PR #6 and the egocentric tasks (#45 / #47).
#
# ==> OPEN QUESTION FOR REVIEWERS (see the PR description) <==
# The ground truth here derives entirely from SoccerNet-v2's public, free Labels-v2.json
# (no NDA needed for the labels). The *video*, though, is the one wrinkle: SoccerNet
# distributes the full-match broadcast under an NDA that restricts public redistribution,
# and the copies are 224p / 720p rather than a pinnable archive.org / YouTube URL.
#
# The egocentric tasks (#45 / #47) handle gated research footage by re-hosting an
# ANONYMIZED derivative of only the clips they use on a public Hugging Face dataset and
# baking from a pinned URL + SHA256. For this task the intended derivative is the full
# match re-encoded to >= 720p with the scoreboard and broadcaster logos blurred (which
# also removes the match-identity shortcut the task needs closed anyway).
#
# We are asking in the PR whether re-hosting that anonymized derivative on a public
# `agentic_vbench_understanding` HF dataset is the accepted path for an NDA-restricted
# broadcast, or whether a fully public source is preferred. Until that is settled the
# URL below is a PLACEHOLDER and this image will not build; everything else in the task
# (prompt, oracle, verifier, calibration) is complete and runs against a locally staged
# copy of the same match.
ARG MATERIALS_URL=https://huggingface.co/datasets/PLACEHOLDER/agentic_vbench_understanding/resolve/main/soccer-restart-outcome-chains/game.mp4
ARG MATERIALS_SHA256=0000000000000000000000000000000000000000000000000000000000000000
RUN mkdir -p /baked \
 && if [ "$MATERIALS_SHA256" = "0000000000000000000000000000000000000000000000000000000000000000" ]; then \
        echo "MATERIALS_URL is a placeholder pending the media-hosting decision (see Dockerfile comment)"; \
        exit 1; \
    fi \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MATERIALS_URL" -o /baked/game.mp4 \
 && echo "${MATERIALS_SHA256}  /baked/game.mp4" | sha256sum -c - \
 && test -s /baked/game.mp4

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
