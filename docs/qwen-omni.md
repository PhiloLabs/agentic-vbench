---
title: Qwen-omni on agentic-vbench
summary: Per-agent compatibility status for Qwen models on DashScope, verified working commands, and blockers.
read_when: Setting up a Qwen evaluation, debugging DashScope auth in a Harbor agent, picking which agent harness to run Qwen on.
---

# Qwen-omni on agentic-vbench

## Quick reference

| Agent | Qwen + DashScope | Env shape | Notes |
|---|---|---|---|
| `openhands-sdk` | ✅ Works | `LLM_API_KEY` + `LLM_BASE_URL` | Cleanest. 755K input tokens / 11K output on a 4-slot task7_3. |
| `qwen-coder` | ✅ Works | `OPENAI_API_KEY` + `OPENAI_BASE_URL` | Higher token usage (~7× openhands-sdk). |
| `claude-code` | ⚠ Untested for Qwen | `ANTHROPIC_BASE_URL` override exists, but DashScope speaks OpenAI protocol, not Anthropic's. Would need OpenRouter / LiteLLM Proxy as a sidecar. |
| `opencode` | ❌ Blocked | Harbor wrapper writes `~/.config/opencode/opencode.json` without `baseURL`; opencode silently routes to `api.openai.com` with the DashScope key and 401s. |
| `openhands` (full) | ❌ Blocked | `uv pip install openhands-ai` (352 packages) fails mid-install on both Modal and local Docker. Use `openhands-sdk` instead. |

DashScope endpoint + model are independently verified:
```bash
curl -s "https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions" \
  -H "Authorization: Bearer $DASHSCOPE_SG_API_KEY" \
  -d '{"model":"qwen3.5-omni-plus","messages":[{"role":"user","content":"hi"}],"max_tokens":10}'
# → HTTP 200, ~1.7s
```

Model IDs per `~/Downloads/models.md`: `qwen3.5-omni-plus` (quality), `qwen3.5-omni-flash` (faster).

## Working invocations

**openhands-sdk** — cleanest, smaller token footprint:
```bash
HF_TOKEN=$HF_TOKEN harbor run \
  -p ./tasks \
  -i <task-name> \
  -a openhands-sdk \
  -m openai/qwen3.5-omni-plus \
  -e modal \
  --ae LLM_API_KEY=$DASHSCOPE_SG_API_KEY \
  --ae LLM_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1 \
  --ae HF_TOKEN=$HF_TOKEN \
  --job-name <name> -y
```

**qwen-coder** — purpose-built CLI, more verbose strategy:
```bash
HF_TOKEN=$HF_TOKEN harbor run \
  -p ./tasks \
  -i <task-name> \
  -a qwen-coder \
  -m qwen3.5-omni-plus \
  -e modal \
  --ae OPENAI_API_KEY=$DASHSCOPE_SG_API_KEY \
  --ae OPENAI_BASE_URL=https://dashscope-intl.aliyuncs.com/compatible-mode/v1 \
  --ae HF_TOKEN=$HF_TOKEN \
  --job-name <name> -y
```

Both also need `MODAL_TOKEN_ID` / `MODAL_TOKEN_SECRET` set (philo-labs keys live in `~/.zshrc` but may be shadowed by stale shell snapshots — set inline when in doubt).

## Vision pathway caveat

DashScope's `compatible-mode/v1` is OpenAI-style. It accepts text + base64-encoded images, **not raw video files**. Qwen's omni multimodal capabilities (native video + audio) require the DashScope-native API, not the OpenAI-compatible endpoint. So on agentic-vbench:

- Agents that ship clip frames as images get useful vision.
- Agents that try to send raw `mp4` paths get text-only model behavior.
- openhands-sdk's smoke run on task7_3 task1 picked `[1,2,3,11]` — likely no vision was actually used. Quality benchmarks should be interpreted in this light until we verify the vision path per-agent.

## Known blockers (revisit when needed)

### opencode
Harbor's `opencode.py` writes an incomplete config (no `baseURL`). Three fix options:

1. **Upstream Harbor PR** (recommended, ~10 min): add `"options": {"baseURL": "..."}` to the JSON written at `harbor/src/harbor/agents/installed/opencode.py:131-141`.
2. **Workaround via `OPENCODE_CONFIG`** env var pointing at our own config file written by `workdir/setup.sh`. Unverified that opencode at the version Harbor installs respects this env var.
3. **Workaround via overwriting** `~/.config/opencode/opencode.json` in `workdir/setup.sh` (runs after Harbor's config write, before the agent run). Brittle — depends on Harbor's internal step ordering.

### openhands (full)
Pip install of `openhands-ai` (352 packages, ~5+ GB) fails mid-stream on both Modal and local Docker. Output is truncated by Harbor's exec capture so the exact failing package isn't visible. Possible mitigations:

- Pin a known-good version via `--ak version=X.Y.Z`.
- Replicate the install manually in a docker shell to see the real error.
- Skip — `openhands-sdk` covers the same use case with a much smaller dep tree and works today.

## What was verified

- DashScope SG endpoint + key + `qwen3.5-omni-plus` model: works via direct curl (HTTP 200, 1.7s).
- openhands-sdk + Qwen: smoke on task7_3 task1, 5m 57s, reward 0.0 (picks `[1,2,3,11]`), 755K/11K tokens, no exceptions.
- qwen-coder + Qwen: smoke on task7_3 task1, 18m 18s, reward 0.0 (picks `[5,8,3,4]`), 5.4M/32K tokens, no exceptions.

## Pricing note

LiteLLM (and therefore Harbor) does not currently have Qwen-DashScope prices in its pricing table — both runs reported `cost_usd: None / 0.0`. Token counts are accurate; USD cost has to be computed manually if needed. DashScope's price card is on the Alibaba Cloud console.
