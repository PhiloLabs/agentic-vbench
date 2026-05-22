#!/bin/bash
# Smoke-test passthrough "oracle": copies the source video verbatim
# as the repurposed cut submission. This is NOT a real solve — CutBench is
# open-ended editing with no oracle reward. It exists only to drive
# the verifier end-to-end during local pipeline shake-out.
set -euo pipefail

cp /workspace/materials/source.mp4 /workspace/output/repurpose.mp4
