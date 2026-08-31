#!/bin/bash
# Oracle: emit the verified reference mesh for each clip's target object as clip_XX.obj.
#
# The reference meshes are the scanned 3D models of the interacted objects. They ship
# verifier-side and are copied to /solution only for this oracle step, so the agent never
# sees them. Exporting them in an arbitrary pose is the answer key: the scorer aligns
# shape scale-free, so any pose/scale of the correct shape scores 1.0.
set -euo pipefail

mkdir -p /workspace/output

python3 - <<'PY'
import json
from pathlib import Path
import trimesh

objs = json.loads(Path("/solution/objects.json").read_text())
for cid in objs:
    m = trimesh.load(f"/solution/ref_{cid}.glb", force="mesh")
    m.export(f"/workspace/output/{cid}.obj")
    print(f"oracle: wrote /workspace/output/{cid}.obj ({len(m.vertices)} verts)")
PY
