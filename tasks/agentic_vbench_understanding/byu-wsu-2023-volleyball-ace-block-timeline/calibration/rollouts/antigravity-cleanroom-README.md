# Antigravity clean-room (3-vector-isolated) run — verified 0.0

Harness (calib-tools/realscore_antigravity.sh):
- Workspace OUTSIDE the repo (no .git, no sibling runs reachable).
- `trustedWorkspaces` narrowed to the workspace only -> `--sandbox` blocks every
  path except the workspace (agentic-vbench, $HOME, /tmp all "Operation not permitted").
- agy persistent memory (conversations/, brain/, conversation_summaries.db) wiped
  beforehand so no earlier-seen answer can be regurgitated.
- All byu-wsu answer files vaulted off-disk during the run; restored after.
- Always-on AGENTS.md: pixels only, no web, no access outside the workspace.
- Integrity gate voids the window on grounding / BypassSandbox-success / answer-copy /
  "perfect-claim with <30 frames"; this run passed (web=0, blocked-escape-attempts=8,
  bypass-success=0, copy=0).

Result across two ~3h windows: genuine OCR pipeline (4-set partition, template score
OCR, LNDS 107-update timeline, fuzzy nameplate matching), 54 frames, 3 event candidates,
1 shipped (wrong) event -> F1 0.0. Not converging (window 2 added 0 events in 3h):
720p broadcast nameplate/jersey OCR defeats it.
