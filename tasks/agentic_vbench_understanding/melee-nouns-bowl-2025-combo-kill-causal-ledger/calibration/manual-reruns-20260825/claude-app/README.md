# Claude App Manual Baseline

## Prepare

```sh
./prepare.sh /Users/zsj/Documents/agentvbench/materials/source/melee-nouns-bowl-2025/match.mp4
```

Create a new empty Claude app chat after preparation. Do not attach this
repository or open it as a project. Attach **only** `run/materials/match.mp4`,
then submit the exact contents of `run/instruction.md` as the user prompt.

Disable web search, connectors, MCP servers, artifacts/projects with preloaded
context, and any browser or computer-use capability. Do not supply any other
files, replay IDs, scorer, historical outputs, VOD URLs, or set information.

When the Claude app returns its answer, copy only the JSON object into
`run/output/solution.json` locally. Save the native chat export or screenshots
in `run/logs/`, then complete `run/logs/network-policy.md` with the actual app
settings used. The app has no access to `run/work/`; that directory is reserved
for any local inspection records that you create yourself.

Do not give the agent this repository, the replay IDs, the scorer, any prior
rollout, the public VOD URLs, or a browser/search tool. Configure the harness
so that task execution has no general internet access; document any unavoidable
model-provider egress in `run/logs/network-policy.md`.

## Capture

After the agent exits:

```sh
RUNNER='Claude app' \
MODEL_NAME='your exact Claude model identifier' \
HARNESS_VERSION='your exact Claude app version' \
./capture.sh
```

The capture script rejects missing metadata, validates `solution.json`, and
writes `run/logs/run-manifest.json`, `reward.json`, and `reward-details.json`.
Retain the native Claude transcript in `run/logs/` before capture.
