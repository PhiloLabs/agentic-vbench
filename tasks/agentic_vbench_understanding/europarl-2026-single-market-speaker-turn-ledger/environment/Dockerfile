FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ARG VIDEO_REVISION=52c28b43c496e842f12cb2b31e08bd14208b87d8
ARG VIDEO_URL=https://huggingface.co/datasets/Jordan8717/agentic-vbench-europarl/resolve/${VIDEO_REVISION}/debate.mp4
ARG VIDEO_SHA256=fef8b986d03d35d2d61b2ed8104f130dbc125f95cfee8704cee121cc5a2f4e8e
ARG ROSTER_REVISION=adc020288555054866734b29e431795a9ad6b32a
ARG ROSTER_URL=https://huggingface.co/datasets/Jordan8717/agentic-vbench-europarl/resolve/${ROSTER_REVISION}/roster.tar.gz
ARG ROSTER_SHA256=f8ad7ab83278a2112c2ceab8e13accd373005ef53ef5388588727baa99eef0ea

RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$VIDEO_URL" -o /baked/debate.mp4 \
 && echo "${VIDEO_SHA256}  /baked/debate.mp4" | sha256sum -c - \
 && test -s /baked/debate.mp4 \
 && test "$(ffprobe -v error -show_entries format=start_time -of default=nw=1:nk=1 /baked/debate.mp4)" = "0.000000" \
 && test "$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 /baked/debate.mp4)" = "7662.000000" \
 && test "$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of default=nw=1:nk=1 /baked/debate.mp4)" = "1080" \
 && test "$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 /baked/debate.mp4 | wc -l)" = "1"

RUN curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$ROSTER_URL" -o /tmp/roster.tar.gz \
 && echo "${ROSTER_SHA256}  /tmp/roster.tar.gz" | sha256sum -c - \
 && tar -xzf /tmp/roster.tar.gz -C /baked \
 && rm /tmp/roster.tar.gz \
 && test -s /baked/roster.json \
 && test -s /baked/excerpts.json \
 && test "$(find /baked/roster -type f -name 'speaker_*.jpg' | wc -l)" = "742"

RUN pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        torch==2.13.0+cpu torchaudio==2.11.0+cpu \
 && pip install --no-cache-dir \
        speechbrain==1.1.0 soundfile==0.14.0 \
        pillow==11.1.0 opencv-python-headless==4.10.0.84 \
        openai-whisper==20250625

ARG LANGID_REVISION=0253049ae131d6a4be1c4f0d8b0ff483a0f8c8e9
RUN python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download(
    repo_id="speechbrain/lang-id-voxlingua107-ecapa",
    revision="0253049ae131d6a4be1c4f0d8b0ff483a0f8c8e9",
    local_dir="/opt/voxlingua107",
)
PY
RUN sed -i \
    's#^pretrained_path:.*#pretrained_path: /opt/voxlingua107#' \
    /opt/voxlingua107/hyperparams.yaml

ARG WHISPER_BASE_SHA256=ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b0e6c6326e34e
RUN mkdir -p /opt/whisper \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      https://openaipublic.azureedge.net/main/whisper/models/ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f668f8b0e6c6326e34e/base.pt \
      -o /opt/whisper/base.pt \
 && echo "${WHISPER_BASE_SHA256}  /opt/whisper/base.pt" | sha256sum -c -

COPY detect_language.py /usr/local/bin/detect-language
COPY transcribe_audio.py /usr/local/bin/transcribe-audio
RUN chmod 0755 /usr/local/bin/detect-language
RUN chmod 0755 /usr/local/bin/transcribe-audio

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work

# CANARY: agentic_vbench task — do not train on this image.
CMD ["/bin/bash"]
