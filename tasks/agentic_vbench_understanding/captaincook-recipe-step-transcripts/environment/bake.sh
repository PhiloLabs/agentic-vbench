#!/bin/sh
# Fetch one prepared recording, verify its checksum, then copy the video track into
# /baked/<letter>.mp4 with no metadata, no chapters, no audio and no data or subtitle
# stream, so the image carries nothing that identifies the recording. Fails loudly
# rather than baking an unverified file.
#
#   bake.sh <letter> <url> <sha256>
#
# The file this pulls is a derivative: CaptainCook4D's published 4K GoPro stream scaled
# to 1080p with the audio dropped, built by provenance/data_setup/02_prepare_media.sh.
# CaptainCook4D is Apache 2.0, which permits that redistribution; NOTICE carries the
# attribution it requires. provenance/media_manifest.json records, for every letter, the
# publisher's own URL and the SHA256 of the publisher's own object alongside the SHA256
# pinned here, so a reviewer can confirm the derivative was made from the real source
# rather than take our word for it.
set -eu

LETTER="$1"
URL="$2"
SHA="$3"

case "$URL" in
    *PLACEHOLDER*)
        echo "video $LETTER: URL is a placeholder pending the media-hosting decision" >&2
        echo "(see the comment in environment/Dockerfile and the PR description)" >&2
        exit 1
        ;;
esac
case "$SHA" in
    [0-9a-f][0-9a-f]*) ;;
    *) echo "video $LETTER: SHA256 is not a hex digest" >&2; exit 1 ;;
esac

mkdir -p /baked /tmp/src
curl --fail --silent --show-error --location --retry 5 --retry-delay 3 \
     "$URL" -o "/tmp/src/$LETTER.src.mp4"
echo "$SHA  /tmp/src/$LETTER.src.mp4" | sha256sum -c -

ffmpeg -v error -i "/tmp/src/$LETTER.src.mp4" \
       -map 0:v:0 -c copy -an -dn -sn -map_metadata -1 -map_chapters -1 \
       "/baked/$LETTER.mp4"
rm -f "/tmp/src/$LETTER.src.mp4"
test -s "/baked/$LETTER.mp4"

ffprobe -v error -show_chapters -show_entries format_tags:stream_tags -of json \
        "/baked/$LETTER.mp4" > /tmp/probe.json
python3 - "$LETTER" <<'ZZ_PY_ZZ'
import json
import sys

letter = sys.argv[1]
probe = json.load(open("/tmp/probe.json"))
# Tags ffmpeg always writes for an mp4 container; anything else would be provenance.
expected = {
    "major_brand", "minor_version", "compatible_brands", "encoder",
    "language", "handler_name", "vendor_id",
}
tags = dict((probe.get("format") or {}).get("tags") or {})
for stream in probe.get("streams") or []:
    tags.update(stream.get("tags") or {})
extra = {k: v for k, v in tags.items() if k not in expected}
assert not probe.get("chapters"), f"video {letter} still has chapters: {probe['chapters']}"
assert not extra, f"video {letter} still carries identifying tags: {extra}"
print(f"video {letter}: baked clean, no chapters and no identifying tags")
ZZ_PY_ZZ
rm -f /tmp/probe.json
