FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg libgl1 libglib2.0-0 ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Numerics and imaging, pinned for reproducibility.
RUN pip install --no-cache-dir \
        numpy==1.26.4 \
        scipy==1.13.1 \
        pandas==2.2.2 \
        scikit-image==0.24.0 \
        opencv-python-headless==4.10.0.84 \
        imageio==2.34.2 \
        imageio-ffmpeg==0.5.1 \
        pillow==10.4.0

# Segmentation and tracking stack. CPU wheels: the task declares no GPU, and
# 800 frames fits inside the agent budget on CPU.
#
# Only the package CODE is preinstalled here, not cellpose's pretrained model
# weights -- cellpose downloads those lazily on first use of a named model
# (e.g. models.CellposeModel(model_type='cyto3')), which fails under this
# task's allow_internet=false: confirmed in a real trace, urlopen raised
# "[Errno -3] Temporary failure in name resolution". An agent can still use
# the package for anything not requiring a pretrained download (custom
# thresholding/segmentation code, trackastra's non-pretrained paths, etc.),
# but cyto3/nuclei/etc. pretrained inference is not available offline as
# shipped. Not fixed in this pass -- see PR #112 for the maintainer
# discussion on whether to bake the weights in (which would require
# rerunning calibration against the changed image) or leave it as-is.
RUN pip install --no-cache-dir \
        torch==2.4.1 torchvision==0.19.1 \
        --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir \
        cellpose==3.1.0 \
        trackastra==0.3.0

RUN mkdir -p /workspace/materials /workspace/output /workspace/work

# The delivered movie is a privately transformed derivative of a public source
# (see task.toml `source` and the PR description), so there is no public URL to
# curl+checksum at build time the way other tasks in this family do -- it is
# committed directly and copied in instead.
COPY data/lineage_movie.mp4 /workspace/materials/lineage_movie.mp4

WORKDIR /workspace
