FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a
# libglib2.0-0 is the one shared lib opencv-python-headless still needs on slim.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
# Documented TOOL PROFILE for this task: the standard CV/array stack, pinned for reproducibility, in
# addition to ffmpeg + the Python stdlib. This is the tool surface the agent is expected to have and
# the calibration must run under (see SPEC.md "Tool profile"). Frame decode is via ffmpeg; NumPy/
# Pillow/OpenCV are available for pixel analysis. No network at solve time (task.toml
# allow_internet=false), so nothing else can be pip-installed at run time.
RUN pip install --no-cache-dir --root-user-action=ignore \
        numpy==2.1.3 Pillow==11.0.0 opencv-python-headless==4.10.0.84 \
 && python -c "import numpy, PIL, cv2; print('tool profile:', numpy.__version__, PIL.__version__, cv2.__version__)"
ARG MATERIALS_URL=https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/39f1b933102acb3e52348752eb736b31c4c9d50b/kart-race-telemetry-ledger-s1/race.mp4
# MEDIA REPIN PENDING. The checksum below is the CURRENT media (mask box derived and verified,
# drift measured on the video clock); the URL above still resolves to the PREVIOUS render, so
# this build FAILS the checksum on purpose until the new media is uploaded and the URL is
# repinned to its revision. Do not "fix" it by restoring the old checksum.
ARG MATERIALS_SHA256=ee7d966e2f47f63c01d347b8994324bb1f1e645d27084bc562c69cb4cf8dafc8
RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 "$MATERIALS_URL" -o /baked/race.mp4 \
 && echo "${MATERIALS_SHA256}  /baked/race.mp4" | sha256sum -c - && test -s /baked/race.mp4
WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
