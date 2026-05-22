FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg tesseract-ocr libgl1 libglib2.0-0 \
        git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Verifier deps. Modal pins typing_extensions==4.12.2 in a post-build step
# (its control-plane stack) and we cannot override that. pydantic_core>=2.30
# imports `Sentinel` (added in typing_extensions 4.13) and would break, so
# we pin pydantic-core<2.30 and pydantic<2.11 — a known-good combo with the
# typing_extensions 4.12.2 that Modal will leave us with.
RUN python3 -m pip install --no-cache-dir \
        "pydantic-core<2.30" \
        "pydantic<2.11" \
        "anthropic>=0.40.0,<0.45" \
        "google-genai>=0.3.0" \
        "openai-whisper>=20231117" \
        "librosa>=0.10.1" \
        "Pillow>=10.0.0" \
        "numpy>=1.24,<2" \
        "pyyaml>=6.0" \
        "scenedetect>=0.6.4" \
        "ImageHash>=4.3.1" \
        "pytesseract>=0.3.10"

# Pre-cache whisper "base" model so the sealed container doesn't need
# network access at trial time.
RUN python3 -c "import whisper; whisper.load_model('base', device='cpu')"

# Bake task materials.
ARG MATERIALS_URL=https://huggingface.co/datasets/ameddserM/agentic_vbench_video_repurpose/resolve/main/materials/film_2001_space_odyssey_trailer.mp4
RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MATERIALS_URL" -o /baked/source.mp4 \
 && test -s /baked/source.mp4 \
 && ls -lh /baked/source.mp4

COPY brief.md     /baked/brief.md
COPY rubric.json  /baked/rubric.json
COPY config.yaml  /baked/config.yaml

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
