FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The agent uses ffmpeg/ffprobe to seek, sample frames, and extract audio. The grader
# is pure stdlib (it only compares integers and strings), so it needs nothing extra.

# The referee's jersey-number call is audio-only evidence (see PROVENANCE.md) -- bake a
# pinned ASR path rather than rely on an agent installing its own at runtime, so every
# trial has the same deterministic transcription tool regardless of allow_internet.
RUN pip install --no-cache-dir faster-whisper==1.2.1

# Pre-download and cache the model at build time, pinned to an exact HF commit rather
# than "small.en" -> whatever "main" resolves to -- the same reproducibility bar as the
# video's SHA256 pin below. small.en balances accuracy on short spoken numbers against a
# CPU-only, no-torch runtime (ctranslate2 backend).
#
# Cached twice while still online: once at the pinned commit (verifies the pin resolves,
# fails the build if it ever doesn't), and once with no revision arg, which is how an
# agent will naturally call WhisperModel('small.en', ...) and defaults to resolving
# "main". Without the second call, HF_HUB_OFFLINE below breaks that plain call: it looks
# for a local "main" ref, finds only the hash-keyed entry, and errors instead of falling
# back to it (verified locally).
ARG WHISPER_MODEL_REVISION=d1d751a5f8271d482d14ca55d9e2deeebbae577f
RUN python3 -c "from faster_whisper import WhisperModel; WhisperModel('small.en', device='cpu', compute_type='int8', revision='${WHISPER_MODEL_REVISION}')" \
 && python3 -c "from faster_whisper import WhisperModel; WhisperModel('small.en', device='cpu', compute_type='int8')"

# Force every later load -- build or trial, however the agent invokes it -- onto that
# pinned local cache with no network resolution. Without this, allow_internet=true means
# a runtime call could still re-resolve "main" over the network, reopening the same
# drift the pin above closes.
ENV HF_HUB_OFFLINE=1

# Bake the full-game broadcast at build time, the same way the v1.0 families do, with a
# pinned URL and a SHA256 verified at build. The file is a pre-existing archive.org
# upload; it is pinned directly (pin, not re-host), matching the gsw-cle worked example.
#
# SHA256 computed by streaming the archive.org file through sha256sum (2026-07-25).
ARG MATERIALS_URL=https://archive.org/download/youtube-noLK78Hgq0A/noLK78Hgq0A.mp4
ARG MATERIALS_SHA256=ba2281d6293b3ee6a180decd508bb871de581841e6ea183ac17455c0344ba998
RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MATERIALS_URL" -o /baked/game.mp4 \
 && echo "${MATERIALS_SHA256}  /baked/game.mp4" | sha256sum -c - \
 && test -s /baked/game.mp4

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
