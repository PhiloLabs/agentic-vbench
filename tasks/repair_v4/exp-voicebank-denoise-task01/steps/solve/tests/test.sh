#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier /logs/artifacts
if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi
pip install --quiet --no-cache-dir \
    "numpy<3" "scipy<2" "soundfile==0.13.*" "pesq" \
    "pysepm @ git+https://github.com/schmiph2/pysepm.git"
# Patch pysepm's np.NaN reference for NumPy 2.x compatibility.
python3 - <<'PY'
from pathlib import Path
p = Path("/usr/local/lib/python3.12/site-packages/pysepm/qualityMeasures.py")
if p.exists():
    s = p.read_text()
    if "np.NaN" in s:
        p.write_text(s.replace("np.NaN", "np.nan"))
PY
python3 /tests/judge.py \
        --enhanced /workspace/output/enhanced.wav \
        --clean /tests/clean.wav \
        --window-json /tests/window.json \
        --reward-json /logs/verifier/reward.json \
        --reward-txt /logs/verifier/reward.txt
