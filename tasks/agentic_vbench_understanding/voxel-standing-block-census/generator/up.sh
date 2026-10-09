#!/bin/bash
# Bring up the frozen task container the calibration run acts on.
set -euo pipefail
CT=${AVB_CT:-avb_task}
docker rm -f "$CT" >/dev/null 2>&1 || true
docker run -d --name "$CT" --network none --cpus 4 --memory 8g \
  avb-standing-census:v6 sleep infinity >/dev/null
echo "container: $CT"
docker exec "$CT" bash -lc '
  echo "cwd: $(pwd)"
  sha256sum /workspace/materials/session.mp4
  python3 -c "import socket;socket.gethostbyname(\"huggingface.co\")" 2>&1 | tail -1
  ls -d /workspace/output /workspace/work'
