# Qualifying Rollout Policy

- Start a fresh Antigravity conversation in a fresh replacement-source
  workspace containing no ground truth or earlier rollout artifacts.
- Send the canonical task instruction first, with only `/workspace` rewritten to
  the local workspace path. Do not state a minimum turn count or pacing target.
- Run Antigravity with terminal sandboxing, Python 3.12 without pip, and
  run-local command guards. Use a pre-tool gate to deny sandbox bypass,
  outside-workspace file or command paths, package/network commands, every
  URL/browser/web tool, and MCP.
- Count completed tool calls from the full Antigravity transcript.
- At approximately 45 completed calls, send one content-free soft checkpoint:
  persist the current best valid `solution.json`, then continue the task.
- After the conversation naturally exceeds 50 completed calls, score the latest
  valid checkpoint. If reward is below `0.5`, stop the rollout.
- If no valid checkpoint exists after 50 calls, request immediate serialization
  before stopping.
- Never permit more than 75 completed tool calls.
- Archive every intervention and audit the transcript for workspace, network,
  ground-truth, prior-rollout, and host-package access before calling the result
  qualifying.
