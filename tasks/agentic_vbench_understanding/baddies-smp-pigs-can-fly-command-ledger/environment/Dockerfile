# Pinned by digest: the `3.12-slim` tag is mutable and would let the base image drift
# under a calibration that is supposed to be reproducible.
FROM python:3.12-slim@sha256:2fe5997d249a808b8eeea52c58a1dbffbba28754dc11699ef5c029f2d818ce79

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
# ctranslate2 is the inference engine underneath faster-whisper and is only bounded
# `<5,>=4.0` by it; pin it too, or the transcripts drift with whatever pip resolves.
RUN pip install --no-cache-dir faster-whisper==1.2.1 ctranslate2==4.8.1
ARG ASR_REPO=Systran/faster-whisper-base.en
# Pinned to an immutable revision, not `main`, and every file is sha256-checked: the
# ASR output is the task's core input, so a silently updated model would make the
# calibration numbers unreproducible. Hashes computed from the files at this revision.
ARG ASR_REV=3d3d5dee26484f91867d81cb899cfcf72b96be6c
RUN mkdir -p /baked/asr \
 && for f in model.bin config.json tokenizer.json vocabulary.txt; do \
      curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
        "https://huggingface.co/${ASR_REPO}/resolve/${ASR_REV}/$f" -o "/baked/asr/$f" || exit 1; \
    done \
 && printf '%s  %s\n' \
      2a166925539a16005f14ff328359f9b9adb9dc4fb631bb3b227526862e93e2ef /baked/asr/model.bin \
      f3bc3821e9fc76a27bae538e11ae5b677dcdd352b4600429ce7951d398569aeb /baked/asr/config.json \
      929c5252409436dce1b38a75d1abbcb5e132d170d8e324e4e04ed915fa2d22df /baked/asr/tokenizer.json \
      ff77588746d3a2595d32ab5b69ffd7b95ce2441ac57533cb66fc3eb575a115cf /baked/asr/vocabulary.txt \
    | sha256sum -c -
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
