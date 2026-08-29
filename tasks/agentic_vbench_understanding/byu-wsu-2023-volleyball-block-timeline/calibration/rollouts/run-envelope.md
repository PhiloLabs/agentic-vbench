# Execution envelope

What the calibration runs were actually given, so a reader can judge parity between
them and reproduce the conditions. Everything here is checkable in the published raw
streams (URLs and hashes in `../scores.md`).

## Harness and versions

| run | CLI | model / effort | invocation |
|---|---|---|---|
| codex-fresh | codex-cli 0.144.4 | gpt-5.6-sol, `model_reasoning_effort=xhigh` | `codex exec --json -s workspace-write` |
| opus-fresh | Claude Code 2.1.248 | `--model opus` (claude-opus-5), `--effort xhigh` | `claude -p --output-format stream-json --dangerously-skip-permissions` |
| ablations: no_media, single_frame, frame_dump | Claude Code | `--model sonnet`, `--effort high` | as above |
| ablation: all_frames | Claude Code | `--model sonnet`, `--effort high` | as above |

The Opus run is two legs of one session: the first was cut off by a network drop and
resumed in place, which is what the 386-turn figure counts. Both legs are published.

## Tool profile

| run | tools available | tools withheld |
|---|---|---|
| opus-fresh, three shell ablations | Bash, Read, Write, Edit, Glob, Grep | WebFetch, WebSearch, Task |
| all_frames ablation | Read, Write | Bash, WebFetch, WebSearch, Task, Glob, Grep, Edit, NotebookEdit |
| codex-fresh | the CLI's own shell and file tools, workspace-write sandbox | the CLI has no per-tool disable flag |

`workspace-write` confines Codex's writes to its workspace. Unlike the sister USC run,
this transcript contains no MCP calls and no URL strings at all.

## Network envelope

The runs were not network-isolated at the OS level: each CLI needs its own model
backend. Isolation was at the tool layer plus verification after the fact:

- the web tools were withheld where the CLI supports it (above);
- the workspace held only the video and the instruction, with no repository, no
  sibling run and no answer file reachable;
- every transcript was then grepped for judge, ground-truth and search references.
  Both scored runs and all four ablations come back **0** on both counts, which is the
  "key 0, web 0" column in `../scores.md`.

The published streams are what those greps ran on, so the audit can be repeated
independently.

## Workspace

Each run got a fresh directory containing `materials/match.mp4` (the baked media,
SHA256 as pinned in `environment/Dockerfile`), `INSTRUCTION.md`, and an empty
`output/`. The prompt itself is committed here as `instruction-as-run.md` and
referenced by SHA256 from each `*.run-metadata.txt`.
