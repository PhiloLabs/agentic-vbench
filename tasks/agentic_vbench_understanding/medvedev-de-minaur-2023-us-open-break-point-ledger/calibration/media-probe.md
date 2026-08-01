# Media-hosting probe

On 2026-08-01, a default `yt-dlp 2025.10.14` probe exposed only format `18` at
640x360. That was a downloader limitation: the current YouTube player still exposes
720p and 1080p, but the higher formats require a current per-video PO token.

A clean Chrome session was used only to mint the required token for the official
video. It downloaded format `136` (1280x720 H.264 video) plus format `140` (AAC
audio), then losslessly muxed them into the following candidate artifact:

```text
filename: medvedev-de-minaur-2023-us-open-r4-720p.mp4
sha256: d78c9246d5dd36b812c71b5f39bfa43ab86d1a7adf711fb7bbc6ff1d66d618b2
bytes: 804641210
duration_seconds: 7152.651610
video: h264, 1280x720, 30000/1001 fps
audio: aac
```

This is a verified 720p reconstruction from the official US Open page, but it is
not byte-identical to the historical `format 22` calibration file whose documented
checksum is `ab240af0c25ab5e46cd9a9592e3b76d8f5831483849c1608ab569d8e8051c72f`.
Do not retain that old checksum for the new artifact.

The artifact is publicly hosted as a release asset at:

```text
https://github.com/inFaaa/agentic-vbench/releases/download/medvedev-de-minaur-2023-us-open-r4-media-v1/medvedev-de-minaur-2023-us-open-r4-720p.mp4
```

GitHub reports the same SHA-256 and byte length as the local verified artifact. The
sibling `gsw-cle-2018-finals-g4-three-point-timeline` task is the implementation
model: the Docker build uses `curl` to fetch a direct MP4 URL and checks the exact
SHA-256. This task follows that pattern with no `yt-dlp` fallback. The video binary
is not committed to Git.

Before submitting, rerun:

```bash
docker build tasks/agentic_vbench_understanding/medvedev-de-minaur-2023-us-open-break-point-ledger
```

The build must download successfully, verify the checksum, and preserve the 720p
input. Do not lower the task's stated resolution or replace the checksum with a
different, unreviewed video.
