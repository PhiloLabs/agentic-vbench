FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The agent has no native hearing and the trial runs with allow_internet=false, so a
# transcription path must be baked in or the audio channel is simply unreachable (not
# hard, impossible). faster-whisper (CTranslate2, CPU-friendly) + a pre-fetched model
# gives the agent a real (if imperfect) way to turn ATC audio into text with ffmpeg +
# a short Python snippet, the same way it uses ffmpeg/ffprobe to sample video frames.
# `requests` is imported by faster_whisper.utils but is NOT pulled in by the
# faster-whisper wheel's own dependencies -- without it the image build fails at the
# model-prefetch step below (verified on python:3.12-slim, 2026-07-30).
RUN pip install --no-cache-dir faster-whisper==1.0.3 requests
# small.en garbles ATC callsigns badly on real recordings (verified against this
# task's own audio); medium.en recovers real repeated callsigns cleanly enough to
# be workable, at the cost of a slower transcribe pass -- still CPU-feasible.
ARG WHISPER_MODEL=medium.en
# Prefetch into a scratch cache, then flatten the snapshot into a directory that
# WhisperModel() can be handed directly. Without the flatten, download_root leaves a
# HuggingFace cache tree (models--Systran--faster-whisper-medium.en/snapshots/<sha>/)
# and WhisperModel('/opt/whisper-model') dies with "Unable to open file 'model.bin'" --
# which is exactly what instruction.md tells the agent to do, so the whole audio channel
# would be unreachable through the documented path. Verified broken, then fixed, by
# running the built image (2026-08-01). cp -L because the snapshot entries are symlinks
# into blobs/.
RUN python3 -c "from faster_whisper import WhisperModel; WhisperModel('${WHISPER_MODEL}', download_root='/opt/whisper-cache')" \
 && SNAP="$(dirname "$(find /opt/whisper-cache -name model.bin | head -1)")" \
 && test -n "$SNAP" \
 && mkdir -p /opt/whisper-model \
 && cp -L "$SNAP"/* /opt/whisper-model/ \
 && rm -rf /opt/whisper-cache \
 && python3 -c "from faster_whisper import WhisperModel; WhisperModel('/opt/whisper-model', device='cpu', compute_type='int8', local_files_only=True)"
ENV WHISPER_MODEL=${WHISPER_MODEL}
ENV WHISPER_MODEL_DIR=/opt/whisper-model

# Bake the video (silent) and the audio track as two separate files with an
# intentionally unknown relative offset -- see steps/solve/workdir/setup.sh for how
# they're placed into the agent's workspace. Both come from one continuous capture:
# runway.mp4 starts 105 s in (the opening shows the recording window being set up) and
# tower.mp3 starts at 0, so the files share content but no clock. Recovering that
# offset is what makes the audio<->video pairing a genuine agentic task rather than a
# free lookup, and it is why nothing here may carry a creation timestamp.
#
# The video also has two overlay regions painted black before upload: the camera's own
# on-screen tracking panel names the aircraft and states its type, which would hand the
# agent both scored fields for free. That masking is baked into the uploaded file, not
# applied here, so the digests below cover the already-masked media.
#
# Self-hosted on Hugging Face, the way the v1.0 families do it, rather than pinned on
# archive.org like the worked example: this media does not exist anywhere upstream --
# it was cut, masked and metadata-stripped for this task, so there is no third-party URL
# to pin. Digests below were verified by streaming both files back down from the public
# URLs after upload.
ARG MATERIALS_VIDEO_URL=https://huggingface.co/datasets/xuanmiao-31/dualrunway-ops-ledger/resolve/main/runway.mp4
ARG MATERIALS_VIDEO_SHA256=fc873ab0777d823f7d1c4b5356df21eebca083f66803db4861b414d360111304
ARG MATERIALS_AUDIO_URL=https://huggingface.co/datasets/xuanmiao-31/dualrunway-ops-ledger/resolve/main/tower.mp3
ARG MATERIALS_AUDIO_SHA256=8501a0c8debd0ca7afe9723173493bd07e442a1bd28914dc5f68fec381f6c7bc
RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MATERIALS_VIDEO_URL" -o /baked/runway.mp4 \
 && echo "${MATERIALS_VIDEO_SHA256}  /baked/runway.mp4" | sha256sum -c - \
 && test -s /baked/runway.mp4 \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MATERIALS_AUDIO_URL" -o /baked/tower.mp3 \
 && echo "${MATERIALS_AUDIO_SHA256}  /baked/tower.mp3" | sha256sum -c - \
 && test -s /baked/tower.mp3

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
