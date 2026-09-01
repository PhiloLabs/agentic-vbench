#!/bin/sh
# Fetch the CaptainCook4D annotation files this task derives its key from, plus the
# official download-link table the media URLs are read out of. All of them are public:
# no login, no data-use agreement, no gate. That is the whole reason this source was
# chosen over a gated egocentric corpus.
#
# Both repositories are pinned to a commit rather than to a branch, so re-running this
# a year from now rebuilds the same key rather than a silently updated one.
#
#   sh provenance/data_setup/01_download_annotations.sh <outdir>
set -eu
OUT="${1:-./cc4d}"
ANN_COMMIT=a8a920a3293c4db27099a20ddbe3a3a9be1283e3
DL_COMMIT=c1a1fd06f9f97abc8d176e0d910f90d4920b7158
mkdir -p "$OUT"
A="https://raw.githubusercontent.com/CaptainCook4D/annotations/$ANN_COMMIT"
D="https://raw.githubusercontent.com/CaptainCook4D/downloader/$DL_COMMIT"
for f in annotation_json/complete_step_annotations.json \
         annotation_json/step_idx_description.json \
         annotation_json/activity_idx_step_idx.json \
         annotation_json/error_annotations.json \
         metadata/video_information.csv; do
    curl --fail --silent --show-error --location -o "$OUT/$(basename "$f")" "$A/$f"
done
curl --fail --silent --show-error --location -o "$OUT/download_links.json" \
     "$D/metadata/download_links.json"
cd "$OUT" && shasum -a 256 *.json *.csv > SHA256SUMS
cat SHA256SUMS
