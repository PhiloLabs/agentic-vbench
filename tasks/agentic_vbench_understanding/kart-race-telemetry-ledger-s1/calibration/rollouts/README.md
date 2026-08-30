# Calibration trajectories — POL-1 raw archives (image-parity)

The **audit record** for each strong-agent row in `../scores.md` is the agent's **full raw session
transcript** — every tool call, tool output, turn, and frame kept intact. Only credentials and
local-path prefixes were redacted (`sanitize_raw.py`: masks API keys / tokens / `Bearer` / private
keys, and maps `/home/<user>` and the SSD working dir → `/workspace`; a FORBID re-scan aborts on any
residual secret **or** local path/username). Each row was produced under the **shipped image's tool
surface** (stdlib-only `python3` — no `numpy`/`opencv`/`PIL`/`scipy`, as in `python:3.12-slim` — plus
`ffmpeg`/`ffprobe`) with the **final agent prompt**. All three are pinned to one immutable revision
`b49ffb9b8d83405dba6ab8dee30126bd1d53f196`, with whole-file SHA256 (verified byte-identical from that
revision):

**Codex — gpt-5.6-sol (xhigh)** — reward **0.0101**, ~163 tool-call turns
- https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/b49ffb9b8d83405dba6ab8dee30126bd1d53f196/kart-race-telemetry-ledger-s1/calibration/raw/kart_codex_gpt-5.6-sol_imgparity_raw.jsonl
- sha256 `dfce5011579cf6ab15925455f27beb76ec74463e7a06db04333bd287d9f340ee`

**Claude Code — claude-opus-4-8** — reward **0.0436** (lineup max, < 0.10), 104 tool-call turns
- https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/b49ffb9b8d83405dba6ab8dee30126bd1d53f196/kart-race-telemetry-ledger-s1/calibration/raw/kart_claude_opus-4.8_imgparity_raw.jsonl
- sha256 `3a1663516727d5b3dbb0da4e95f6438c33aea87026e50ee1fc71da1edf48dbd5`

**Gemini CLI — gemini-3.5-flash** — reward **0.0082**, 189 tool-call turns (two checkpointed
sub-sessions concatenated in order)
- https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/b49ffb9b8d83405dba6ab8dee30126bd1d53f196/kart-race-telemetry-ledger-s1/calibration/raw/kart_gemini_3.5-flash_imgparity_raw.jsonl
- sha256 `2eff4eb96e04a54008b3f33bdca7dc1b597860c3a36b6f341a2750c8bc1c63a6`

Each run's `solution.json` (the agent's answer) and `reward.json` (the shipped `judge.py` output that
produced the reward above) are alongside the raw archives at the same revision, as
`kart_<agent>_imgparity_solution.json` / `kart_<agent>_imgparity_reward.json`:
`.../resolve/b49ffb9b8d83405dba6ab8dee30126bd1d53f196/kart-race-telemetry-ledger-s1/calibration/`.

The earlier host-tool runs (Codex n=3, Gemini 0.0885, etc.) remain on HF at their prior revisions for
history, but the shipped calibration is the image-parity lineup above.
