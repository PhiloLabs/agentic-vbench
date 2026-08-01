FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The agent uses ffmpeg/ffprobe to seek frames and extract audio. The grader is pure
# stdlib, so nothing extra is needed.

# Offline ASR. The commands live in the voice chat, but text+vision harnesses (Claude
# Code, Codex) cannot hear audio at all — without a speech tool they would fail for
# lack of a sensor rather than for lack of reasoning, which is not the difficulty this
# task means to measure. So the environment ships a local speech-to-text tool and the
# agent is told it exists; running it, aligning its timestamps, and cross-referencing
# the video is part of the work. faster-whisper is CPU-only (no torch) and the model is
# baked, so this stays fully offline with allow_internet=false.
RUN pip install --no-cache-dir faster-whisper==1.2.1
ARG ASR_REPO=Systran/faster-whisper-base.en
RUN mkdir -p /baked/asr \
 && for f in model.bin config.json tokenizer.json vocabulary.txt; do \
      curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
        "https://huggingface.co/${ASR_REPO}/resolve/main/$f" -o "/baked/asr/$f" || exit 1; \
    done \
 && test -s /baked/asr/model.bin
COPY transcribe.py /usr/local/bin/transcribe
RUN chmod +x /usr/local/bin/transcribe

# Bake the 228-min window (00:10:00-03:58:00 of YouTube obx7hpd4ZfE, CC-BY, "Baddies
# SMP | Pigs can fly" by Nordic Nio VODs), re-hosted so the bytes are stable. The agent
# gets ONLY this mp4 — the annotated ledger stays verifier-side and never enters this
# image.
ARG MATERIALS_URL=https://huggingface.co/datasets/wenkai-li/agenticvbench/resolve/main/full_task_720p.mp4
# SHA256 of the exact file every calibration run was measured against:
# full_task_720p.mp4, 1280x720, 13686.861 s (228 min), 3.093 GB, faststart layout
# (moov at byte 32) so the URL is probeable without a full download.
ARG MATERIALS_SHA256=1a0ca5aff0536741fe303a69bbdaaf4c2ddb8624d8df6c978b4e17336779aeb0
RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MATERIALS_URL" -o /baked/session.mp4 \
 && echo "${MATERIALS_SHA256}  /baked/session.mp4" | sha256sum -c - \
 && test -s /baked/session.mp4

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
