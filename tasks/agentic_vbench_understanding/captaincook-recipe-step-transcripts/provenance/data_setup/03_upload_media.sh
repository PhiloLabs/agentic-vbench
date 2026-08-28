#!/bin/sh
# Publish the prepared 1080p derivatives so the image can bake from a pinned URL, then
# rewrite the Dockerfile to point at them.
#
#   sh provenance/data_setup/03_upload_media.sh <media out dir> <hf dataset repo>
#
# This is the one step that cannot run unattended: it writes to an account. Log in first
# with `hf auth login` (or `huggingface-cli login`) in your own shell; this script never
# takes a token as an argument and never writes one to disk.
#
# ONE FILE PER COMMIT, ON PURPOSE. The obvious form of this script is a single
# `hf upload <repo> <dir> .`, which is one commit for the whole folder. That ran for
# fourteen hours over a VPN that reassigned the client address mid-transfer, showed nine
# of twenty-two progress bars at 100 percent, and committed nothing at all: the repo held
# only .gitattributes afterwards. A progress bar is not evidence that a file landed. So
# each file is uploaded on its own, with retries, and at the end the repo is listed and
# compared against what is on disk, because the listing is the artifact that can answer
# the question and the progress bar is not.
#
# Re-running is safe and is the way to resume: files already in the repo are skipped.
set -eu
OUT="$1"
REPO="$2"
TASK="$(cd "$(dirname "$0")/../.." && pwd)"
RETRIES=${RETRIES:-4}

test -d "$OUT" || { echo "no such directory: $OUT" >&2; exit 1; }
N=$(find "$OUT" -name '*.mp4' | wc -l | tr -d ' ')
WANT=$(python3 -c "import json,sys;print(len(json.load(open(sys.argv[1]))['videos']))" \
       "$TASK/provenance/step-derived.json")
test "$N" -eq "$WANT" || { echo "expected $WANT mp4 files in $OUT, found $N" >&2; exit 1; }

have_remote() {
    python3 - "$REPO" <<'PY'
import sys
from huggingface_hub import HfApi
try:
    for f in HfApi().list_repo_files(sys.argv[1], repo_type="dataset"):
        print(f)
except Exception as e:
    print(f"could not list {sys.argv[1]}: {type(e).__name__}: {e}", file=sys.stderr)
    sys.exit(1)
PY
}

REMOTE=$(have_remote)
for f in $(find "$OUT" -name '*.mp4' | sort); do
    b=$(basename "$f")
    if printf '%s\n' "$REMOTE" | grep -qx "$b"; then
        echo "  already there  $b"
        continue
    fi
    i=1
    while [ "$i" -le "$RETRIES" ]; do
        echo "  uploading      $b (attempt $i/$RETRIES)"
        if hf upload "$REPO" "$f" "$b" --repo-type dataset; then
            break
        fi
        i=$((i + 1))
        sleep $((i * 20))
    done
    test "$i" -le "$RETRIES" || { echo "gave up on $b after $RETRIES attempts" >&2; exit 1; }
done

# NOTICE must reach the dataset repo, because Apache 2.0 requires the attribution to
# travel with the redistributed material. It must NOT be written into $OUT: that
# directory is what the calibration runs symlink as the agent's `materials/`, and a file
# there naming the source dataset is exactly the leak the family README warns about.
# Upload it from a staging directory of its own instead.
STAGE="$(mktemp -d)"
cp "$TASK/NOTICE" "$STAGE/NOTICE"
hf upload "$REPO" "$STAGE/NOTICE" NOTICE --repo-type dataset
rm -rf "$STAGE"

# The listing, not the progress bars, decides whether this worked.
MISSING=""
REMOTE=$(have_remote)
for f in $(find "$OUT" -name '*.mp4' | sort); do
    b=$(basename "$f")
    printf '%s\n' "$REMOTE" | grep -qx "$b" || MISSING="$MISSING $b"
done
printf '%s\n' "$REMOTE" | grep -qx NOTICE || MISSING="$MISSING NOTICE"
if [ -n "$MISSING" ]; then
    echo "the repo listing is missing:$MISSING" >&2
    echo "rerun this script to resume; it skips what is already there" >&2
    exit 1
fi
echo "verified against the repo listing: $WANT mp4 files and NOTICE are present"

python3 "$TASK/provenance/make_dockerfile.py" \
    --derived "$TASK/provenance/step-derived.json" \
    --media "$TASK/provenance/media_manifest.json" \
    --base "https://huggingface.co/datasets/$REPO/resolve/main" \
    --out "$TASK/environment/Dockerfile"
echo
echo "Dockerfile now points at https://huggingface.co/datasets/$REPO/resolve/main"
echo "Verify one file end to end before opening the PR:"
echo "  sh $TASK/environment/bake.sh A \\"
echo "     https://huggingface.co/datasets/$REPO/resolve/main/A.mp4 \\"
echo "     \$(python3 -c \"import json;print(json.load(open('$TASK/provenance/media_manifest.json'))['A']['derivative_sha256'])\")"
