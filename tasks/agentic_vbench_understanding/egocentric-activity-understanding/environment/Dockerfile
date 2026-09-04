FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The agent uses ffmpeg/ffprobe to seek and sample frames. The grader is pure stdlib
# (it only compares strings and integers), so it needs nothing extra.

# Bake the egocentric session at build time from a pinned URL, verified by SHA256, the
# same pattern the v1.0 families and the understanding worked example use.
#
# Source: Georgia Tech Egocentric Activity Datasets, GTEA Gaze+, subject Ahmad,
# "American breakfast" session, taken from the dataset's own distribution point.
#
# The published file is named Ahmad_American.avi but is NOT an AVI: it is a Matroska
# container (muxed by Lavf53.4.0) holding a single H.264 track and no audio. It is baked
# byte-for-byte under a truthful .mkv name and never re-encoded or remuxed, because the
# task's frame numbers must stay identical to the ones the dataset's published action
# annotation uses. ffmpeg demuxes it by content, not by extension.
#
# ==> OPEN QUESTION FOR REVIEWERS (see SPEC.md, open item 1) <==
# The family asks for "a stable, downloadable source (archive.org or YouTube)". The URL
# below is the dataset's authoritative Dropbox distribution point, which is a share link
# rather than a content-addressed archive URL. Decide whether to keep it or re-host the
# file on a public `agentic_vbench_understanding` HF dataset (the pattern used by the
# other egocentric tasks). The SHA256 pins the exact bytes either way.
ARG MATERIALS_URL="https://www.dropbox.com/scl/fi/0sfkl9r59qchz71183s19/Ahmad_American.avi?rlkey=zlywl5mhpv3ycwgurbitq1fn2&dl=1"
ARG MATERIALS_SHA256=f78b9f2c34bdb74eaf125bbb200fece6fd9d285f50b02905c91157f935a1ee24
RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MATERIALS_URL" -o /baked/session.mkv \
 && echo "${MATERIALS_SHA256}  /baked/session.mkv" | sha256sum -c - \
 && test -s /baked/session.mkv

# Fail the build loudly if the media ever stops matching what the answer key assumes:
# 1280x960, 24.000 fps, exactly 25692 video frames (indices 0-25691, covering the
# annotation's last frame 24905), and no audio track.
RUN test "$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of default=nw=1:nk=1 /baked/session.mkv)" = "1280" \
 && test "$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of default=nw=1:nk=1 /baked/session.mkv)" = "960" \
 && test "$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=nw=1:nk=1 /baked/session.mkv)" = "24/1" \
 && test "$(ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of default=nw=1:nk=1 /baked/session.mkv)" = "25692" \
 && test -z "$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 /baked/session.mkv)"

# The closed label space the agent answers in, and the only copy of it in the repo:
# generated from the published annotation by calibration/build_ground_truth.py. The
# judge derives the same vocabulary from its own answer key, so the two cannot drift.
COPY vocabulary.json /baked/vocabulary.json

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
