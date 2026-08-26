# Calibration trajectories — POL-1 raw archives

The **audit record** for each strong-agent row in `../scores.md` is the agent's **full raw session
transcript** — every tool call, tool output, turn, and frame kept intact. Only credentials and
home-directory prefixes were redacted (`sanitize_raw.py`: masks API keys / tokens / `Bearer` /
private keys / `/home/<user>`; re-scanned to 0 residual secrets). The archives are tens of MB of
base64 frames, so they are hosted immutably on HF (this repo has no git-LFS) and pinned by revision,
with whole-file SHA256 recorded here:

```
REV=4a1142050c59375a7a833d7253549eb6205a7119
base=https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/$REV/kart-race-telemetry-ledger-s1/calibration/raw
```
| row | raw archive (`$base/…`) | sha256 |
|---|---|---|
| Codex CLI · gpt-5.6-sol (xhigh), run 1 of n=3 | `kart_codex_gpt-5.6-sol_raw.jsonl` | `ad3127d1424482713ae78ef1b98c41640454ba4577d8e45844a5709633930fd0` |
| Claude Code CLI · claude-opus-4-8 | `kart_claude_opus-4.8_raw.jsonl` | `9ee2ce6c916bc49122711fdab91899950761f8abdfce9401e57e3c46d94f02e1` |

The reward/solution JSON dumps are alongside at `.../calibration/` (same pinned revision).

The Gemini row's raw archive is on a later revision (added after the Codex/Claude ones):
```
REV=7709db721254eab4a80b7187b21392a6f18d1c4f
```
| row | raw archive (`.../resolve/$REV/kart-race-telemetry-ledger-s1/calibration/raw/…`) | sha256 |
|---|---|---|
| Gemini CLI · gemini-3.5-flash | `kart_gemini_3.5-flash_raw.jsonl` | `83687361fcdd6584c47e693f430376945620f2f91e09c9b08a5c88e861f11753` |
