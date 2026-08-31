#!/bin/bash
set -euo pipefail

expected_sha256='02f18fd7f4796800eece0400b1b1f315a36778b57b9ef4a64d1b30aa3b539749'
root=$(cd "$(dirname "$0")" && pwd)
source_media=${1:?usage: ./prepare.sh /absolute/path/to/match.mp4}
run_dir="$root/run"
ffprobe_bin=${FFPROBE_BIN:-ffprobe}

test -f "$source_media" || { echo "media file not found: $source_media" >&2; exit 1; }
test ! -e "$run_dir" || { echo "refusing to overwrite existing $run_dir" >&2; exit 1; }
command -v "$ffprobe_bin" >/dev/null || {
    echo "ffprobe is required; install FFmpeg or set FFPROBE_BIN" >&2
    exit 1
}
actual_sha256=$(shasum -a 256 "$source_media" | awk '{print $1}')
test "$actual_sha256" = "$expected_sha256" || {
    echo "unexpected media SHA256: $actual_sha256" >&2
    exit 1
}

mkdir -p "$run_dir/materials" "$run_dir/output" "$run_dir/work" "$run_dir/logs"
cp "$root/instruction.md" "$run_dir/instruction.md"
cp "$source_media" "$run_dir/materials/match.mp4"
cp "$root/network-policy.template.md" "$run_dir/logs/network-policy.md"
shasum -a 256 "$run_dir/instruction.md" > "$run_dir/logs/instruction.sha256"
shasum -a 256 "$run_dir/materials/match.mp4" > "$run_dir/logs/match.sha256"
"$ffprobe_bin" -v error -select_streams v:0 \
    -show_entries stream=width,height,r_frame_rate,nb_frames \
    -show_entries format=duration,size \
    -of default=noprint_wrappers=1 "$run_dir/materials/match.mp4" \
    > "$run_dir/logs/match.ffprobe.txt"

cat <<'EOF'
Prepared a clean Claude app baseline workspace. Add the native transcript and a
description of the enforced network policy to run/logs/ after the app response.
EOF
