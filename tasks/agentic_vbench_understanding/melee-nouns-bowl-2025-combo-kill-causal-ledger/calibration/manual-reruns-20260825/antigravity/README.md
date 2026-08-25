# Antigravity Manual Baseline

This template records the supplied harness provenance:

- Model: `Gemini 3.5 Flash`
- Harness: `Antigravity.app 2.3.1`

## Prepare

```sh
./prepare.sh /Users/zsj/Documents/agentvbench/materials/source/melee-nouns-bowl-2025/match.mp4
```

Create a new empty Antigravity.app task and select the prepared `run/` directory
as its only local workspace. Submit exactly `run/instruction.md`. The agent may
use local video-analysis tools and may write only under `run/work`. Require final
JSON at `run/output/solution.json`.

Do not provide replays, source clips, benchmark source files, previous runs,
browser/search tools, connectors, MCP servers, or external set information.
Restrict general egress for the task execution and write the actual enforcement
method plus any model API exception to `run/logs/network-policy.md`.

## Capture

Place the native Antigravity export or run log in `run/logs/`, then run:

```sh
./capture.sh
```

It verifies the media and instruction hashes, validates the output, and writes
the fixed model/harness metadata to `run/logs/run-manifest.json`.
