FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The agent uses ffmpeg/ffprobe to seek and sample frames and to pull the audio track.
# The grader is pure stdlib (it only compares strings and integers), so it needs
# nothing extra.

# Bake the broadcast at build time from a pinned URL, verified by SHA256, the same
# pattern the v1.0 families and the understanding worked example use.
#
# Source: the TenniSet dataset's own distribution point, video V006 — the full
# broadcast of the London 2012 Olympic women's singles final. Baked byte-for-byte and
# never re-encoded or remuxed, because the task's frame numbers must stay identical to
# the ones the dataset's published event annotation uses.
#
# The URL is Google Drive's direct-download endpoint. `confirm=t` bypasses the
# interactive virus-scan interstitial that Drive serves for files this large; without
# it curl silently writes a 2 KB HTML page and the SHA256 check below fails loudly.
#
# ==> OPEN QUESTION FOR REVIEWERS (see SPEC.md, open item 1) <==
# The family asks for "a stable, downloadable source (archive.org or YouTube)". The URL
# below is the dataset author's authoritative Google Drive share, which is a share link
# rather than a content-addressed archive URL. Decide whether to keep it or re-host the
# file on a public `agentic_vbench_understanding` HF dataset (the pattern the other
# understanding tasks use). The SHA256 pins the exact bytes either way.
ARG MATERIALS_URL="https://drive.usercontent.google.com/download?id=1w1R6R6BAa_9K-he5nqygT5Bvb5CsyKhT&export=download&confirm=t"
ARG MATERIALS_SHA256=76e3fa2d0905555e084b9bfd003add1c855a8fb4e8da49c60d5795f0c2e4e620
RUN mkdir -p /baked \
 && curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
      "$MATERIALS_URL" -o /baked/match.mp4 \
 && echo "${MATERIALS_SHA256}  /baked/match.mp4" | sha256sum -c - \
 && test -s /baked/match.mp4

# Fail the build loudly if the media ever stops matching what the answer key assumes:
# 1280x720, 25.000 fps, exactly 123875 video frames (indices 0-123874, covering the
# final scored stroke at 117170 and final annotated serve at 119936), plus an AAC track
# (the umpire's calls and the ball strikes are part of the evidence).
RUN test "$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of default=nw=1:nk=1 /baked/match.mp4)" = "1280" \
 && test "$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of default=nw=1:nk=1 /baked/match.mp4)" = "720" \
 && test "$(ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=nw=1:nk=1 /baked/match.mp4)" = "25/1" \
 && test "$(ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of default=nw=1:nk=1 /baked/match.mp4)" = "123875" \
 && test "$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of default=nw=1:nk=1 /baked/match.mp4)" = "aac"

# The closed label space the agent answers in, and the only copy of it in the repo:
# generated from the published annotation by calibration/build_ground_truth.py. The
# judge derives the same vocabulary from its own answer key, so the two cannot drift.
COPY vocabulary.json /baked/vocabulary.json

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
