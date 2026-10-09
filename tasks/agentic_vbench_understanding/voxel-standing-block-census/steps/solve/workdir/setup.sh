#!/bin/bash
# Nothing to prepare: the recording is baked into the image and the agent
# writes its single answer file to /workspace/output.
set -euo pipefail
mkdir -p /workspace/output /workspace/work
