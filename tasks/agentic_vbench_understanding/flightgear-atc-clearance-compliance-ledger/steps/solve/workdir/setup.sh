#!/bin/bash
set -euo pipefail

mkdir -p /workspace/materials /workspace/output /workspace/work
cp /baked/flight.mp4 /workspace/materials/flight.mp4

rm -- "$0"
