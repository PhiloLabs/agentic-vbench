# Final calibration: harness and artifacts

Per reviewer request on PR #112: one exact-image/exact-prompt trace each for
Codex, Claude Code, and Antigravity, under `allow_internet=false`, with the
agent CLI host-side (access only to its model API) and every task action
routed through the frozen task container with task networking disabled.

## Harness

`container_mcp.py` is the isolation layer: an MCP server, run on the host,
exposing exactly two tools -- `bash` (runs a command via `docker exec` inside
a running task container) and `read_image` (reads an image file from inside
that container and returns it as an MCP image content block). Both agent
CLIs had their native shell/execution tool disabled and were restricted to
only these two MCP tools, so every action they took physically executed
inside the isolated container, while the CLI process itself (and its calls to
the model API) ran on the host with normal network access.

Container setup (identical for both agents):

```
docker build -t calib-task-image -f environment/Dockerfile environment/
docker run -d --name <container> --network none --cpus 4 --memory 8g calib-task-image:latest tail -f /dev/null
```

Network isolation verified before and after each run:

```
docker exec <container> python3 -c "import urllib.request; urllib.request.urlopen('https://api.anthropic.com', timeout=5)"
# -> URLError: [Errno -3] Temporary failure in name resolution (confirmed both times)
```

**Claude Code**: `claude -p "<instruction.md>" --mcp-config mcp_config.json
--strict-mcp-config --disallowedTools Bash,WebFetch,WebSearch --allowedTools
mcp__container-exec__bash,mcp__container-exec__read_image --permission-mode
bypassPermissions --max-turns 400`

**Codex CLI**: `codex exec --disable shell_tool
--dangerously-bypass-approvals-and-sandbox --skip-git-repo-check -m
gpt-5.6-sol "<instruction.md>"`, with the same MCP server registered via
`codex mcp add container-exec -- ...` and pointed at its own separate
container.

## Image / prompt hashes

- Task image digest: `sha256:5d1b1980cc9edc831653a09f56353a94160af611f10de43a825c33adb50acc41`
  (built from the exact committed `environment/Dockerfile`)
- Prompt (`steps/solve/instruction.md`) SHA256:
  `e6d0590f331165305a44ee81fbde934354f1dc3550c5cb2958c1363c2d0f1e14`

## Results

| run | reward | tool-call turns | notes |
|---|---|---|---|
| Claude Code (Opus 5) | 0.0000 | 46 | division F1 0.0755; all 4 gates fail |
| Codex CLI (gpt-5.6-sol) | 0.0000 | 26 | division F1 0.0261; all 4 gates fail |
| Antigravity (Gemini), reviewer-supplied, scoped waiver | 0.0000 | 170 | division F1 0.0877; see note below |
| no_media | 0.0000 | 0 | raw API call, no image, no tools. Model **confabulated** having inspected the video and written an output file it never had access to -- notable finding, not just a low score |
| single_frame | 0.0000 | 0 | raw API call, one still frame (frame 400) only, no tools |
| frame_dump_no_tools | 0.0000 | 0 | raw API call, **all 800 frames** as 8 contact sheets (`full_dump/sheet_00.png`..`sheet_07.png`, 100 frames each, labeled), explicitly instructed to give a direct best-effort answer with no tool calls. Completed naturally (`stop_reason: end_turn`); division F1 0.009, all 4 gates fail |

Redone 2026-08-31 after review: the first `frame_dump_no_tools` pass only
sampled 20 of 800 frames and let the model attempt a tool call it had no
access to, producing no parseable answer and no reward artifact. This run
fixes both -- full frame coverage, an explicit no-tools/direct-answer
instruction, and a complete `..._request.json`/`..._response_meta.json`/
`..._raw.txt`/`..._solution.json`/`..._reward.json` set. The `no_media` and
`single_frame` rows above are unchanged (same responses/rewards as before),
but now also have `..._request.json` files recording the exact request sent
(model, max_tokens, image byte-length, full text prompt) for auditability.

Both real-agent turn counts (46, 26) are below this family's usual >50 norm.
Noting that plainly: this reflects how these two runs actually distributed
their work (denser individual actions, e.g. writing larger analysis scripts
per turn, vs. many small tool calls), not a shortened or truncated attempt --
full transcripts are in this directory for audit. Both runs completed
naturally (agent-reported done, not hitting `--max-turns`).

Full artifacts: gzipped native transcripts (`claude-code-final.jsonl.gz`,
`codex-final.jsonl.gz`), submitted answers and reward.json for every row
above, and the harness script itself (`container_mcp.py`).

## Antigravity (Gemini): reviewer-granted scoped waiver

Extending this harness to `gemini-cli` (Policy Engine denying its shell tool
so only the MCP `bash`/`read_image` tools should be reachable) surfaced a
real gap: an early policy only denied the shell tool, and one trial run used
`gemini-cli`'s native, host-side filesystem tools to read ground-truth
artifacts left in a git-ignored local directory from an earlier, unrelated
oracle-verification run. That run was discarded unscored; the deny-list was
extended to cover every native tool `gemini-cli` ships, verified via a smoke
test showing only the two MCP tools remain in the model's tool list.

Every clean re-run attempted after that fix -- two separate Gemini API keys,
several hours combined -- failed on sustained Google-side `503`/`429` errors
before completing, with network isolation and tool restriction reverified
working immediately before each attempt. The reviewer independently
reproduced the same `503` capacity failure and supplied a supplemental
native Antigravity run (`gemini-3.7-flash-high`, 170 tool-call turns, no
validation errors, reward 0.0000, division F1 0.0877) that satisfies both
the `<0.10` difficulty gate and the family's `>50` long-horizon check. Per
the reviewer this is a scoped waiver -- based on the documented external
service failures plus that supplemental evidence -- not a canonical
exact-image calibration row (the rebuilt image digest differed from this
directory's historical digest, and Antigravity did not fully suppress its
native control-plane/subagent facilities) and not a general exemption from
calibration policy. Full narrative in `calibration/scores.md`'s
2026-08-31/09-01 updates.
