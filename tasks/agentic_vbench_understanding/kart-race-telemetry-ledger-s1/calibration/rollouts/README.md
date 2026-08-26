# Calibration trajectories — POL-1 raw archives

The **audit record** for each strong-agent row in `../scores.md` is the agent's **full raw session
transcript** — every tool call, tool output, turn, and frame kept intact. Only credentials and
home-directory prefixes were redacted (`sanitize_raw.py`: masks API keys / tokens / `Bearer` /
private keys / `/home/<user>`; re-scanned to 0 residual secrets). The archives are on HF (this repo
has no git-LFS), each pinned to an immutable revision, with whole-file SHA256:

**Codex — gpt-5.6-sol (xhigh), run 1 of n=3** (turns 242/120/237 across the three runs)
- https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/4a1142050c59375a7a833d7253549eb6205a7119/kart-race-telemetry-ledger-s1/calibration/raw/kart_codex_gpt-5.6-sol_raw.jsonl
- sha256 `ad3127d1424482713ae78ef1b98c41640454ba4577d8e45844a5709633930fd0`

**Claude Code — claude-opus-4-8** (108 turns)
- https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/4a1142050c59375a7a833d7253549eb6205a7119/kart-race-telemetry-ledger-s1/calibration/raw/kart_claude_opus-4.8_raw.jsonl
- sha256 `9ee2ce6c916bc49122711fdab91899950761f8abdfce9401e57e3c46d94f02e1`

**Gemini CLI — gemini-3.5-flash** (134 turns)
- https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/7709db721254eab4a80b7187b21392a6f18d1c4f/kart-race-telemetry-ledger-s1/calibration/raw/kart_gemini_3.5-flash_raw.jsonl
- sha256 `83687361fcdd6584c47e693f430376945620f2f91e09c9b08a5c88e861f11753`

The reward/solution JSON dumps for the Codex/Claude runs are alongside the Codex/Claude archives at
`.../resolve/4a1142050c59375a7a833d7253549eb6205a7119/kart-race-telemetry-ledger-s1/calibration/`.
