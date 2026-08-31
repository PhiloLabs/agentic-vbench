#!/bin/bash
# One-command calibration launcher.
#   ./calibrate.sh codex
#   ./calibrate.sh gemini            # defaults to gemini-3.5-flash
#   ./calibrate.sh gemini gemini-3.1-pro
# Stages a clean, key-free, hash-verified workspace, then launches the run in
# the background with caffeinate. When it finishes, grade with:
#   ./audit_and_grade.sh <harness> ../rollouts/<trajectory-file>
set -euo pipefail
cd "$(dirname "$0")"
H="${1:?usage: ./calibrate.sh codex | gemini [model]}"
case "$H" in
  codex)  ./stage_workspace.sh codex;  ./run_codex.sh ;;
  gemini) ./stage_workspace.sh gemini; ./run_gemini.sh "${2:-gemini-3.5-flash}" ;;
  *) echo "unknown harness '$H' (use: codex | gemini)"; exit 1 ;;
esac
