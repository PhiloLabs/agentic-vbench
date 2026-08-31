# Infrastructure Validation (2026-08-30)

This record validates the current task HEAD without starting a model trial.

| item | value |
|---|---|
| task commit | `76cf9ab870b55d59d7625551805c3f3c55b280ab` |
| Docker base | `python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a` |
| built image | `agentic-vbench-melee:infra-verify-hf-20260831` |
| task-image digest | `sha256:47c3749a206c1cd51f857e8617962c3a18c9716351c97fdcd338061a59618603` |
| Docker daemon | `29.5.2 linux/arm64` (Colima) |
| Harbor | `0.20.0` |

## Build and media check

The current `environment/Dockerfile` now defaults to the immutable Hugging Face
Dataset revision `358a0871ba6cd5331f329dafee07564710257bd8`. The ordinary
no-override build therefore downloads an evaluator-accessible artifact and runs
the Dockerfile's final digest and ffprobe checks. The empty-override YouTube
fallback was separately observed to return HTTP 403; it is retained only as an
explicit fallback and is not the evaluator default.

The successful ordinary build command is:

```bash
docker build --pull \
  --tag agentic-vbench-melee:infra-verify-hf-20260831 \
  tasks/agentic_vbench_understanding/melee-nouns-bowl-2025-combo-kill-causal-ledger/environment
```

The final baked media is:

```text
SHA256:     02f18fd7f4796800eece0400b1b1f315a36778b57b9ef4a64d1b30aa3b539749
bytes:      610171132
codec:      h264
dimensions: 1280x720
frame rate: 60/1
frames:     90551
duration:   1509.183333 seconds
```

The complete command output is represented by the checked-in artifacts:

- `artifacts/baked-match.sha256`
- `artifacts/baked-match.ffprobe.txt`

## Setup smoke

Harbor install-only was run against the image digest above with one trial, zero
retries, verification disabled, and no agent/model execution:

```text
job: melee-infra-smoke-hf-20260831T124500Z
trials: 1
exceptions: 0
agent: codex 0.147.0-alpha.6.5
model: gpt-5.6-sol
```

The task setup script was then executed in the same image. It moved
`/baked/match.mp4` to `/workspace/materials/match.mp4`, verified the destination
SHA256, and confirmed that `/baked/match.mp4` no longer exists. The resulting
hash, ffprobe, and materials listing are retained in `artifacts/`.

## Tool profile and rerun decision

The image contains `ffmpeg/ffprobe 7.1.5`, `curl`, `node v20.19.2`, `npm 9.2.0`,
`ripgrep 14.1.1`, and Codex `0.147.0-alpha.6.5`. The Harbor/Docker profile and
the media fingerprint match the retained Codex r3 calibration profile. No model
row or ablation requires rerunning on this basis.
