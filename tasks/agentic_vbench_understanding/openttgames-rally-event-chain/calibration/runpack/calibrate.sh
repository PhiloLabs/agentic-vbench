#!/bin/bash
# One-command launcher. Brings the egress gate up, stages a clean container for
# the harness, and starts the run.
#
#   ./calibrate.sh codex
#   ./calibrate.sh claude [model]
#   ./calibrate.sh antigravity [model]
#
# Grade a finished run with:
#   ./audit_and_grade.sh <harness> ../rollouts/<trajectory>
set -euo pipefail
cd "$(dirname "$0")"

H="${1:?usage: ./calibrate.sh codex|claude|antigravity [model]}"
./netgate.sh up
./stage_workspace.sh "$H"

case "$H" in
  codex)       ./run_codex.sh ;;
  claude)      ./run_claude.sh "${2:-opus-4.8}" ;;
  antigravity) ./run_antigravity.sh "${2:-gemini-3.5-flash}" ;;
  *) echo "unknown harness '$H'" >&2; exit 1 ;;
esac
