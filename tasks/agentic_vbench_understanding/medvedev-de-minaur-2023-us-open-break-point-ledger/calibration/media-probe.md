# Media and image probe

## Hosted source

The source is the 2023 US Open Medvedev-De Minaur fourth-round match, reconstructed
from the official 1280x720 H.264 and AAC streams and hosted as a pinned GitHub
release asset:

```text
https://github.com/inFaaa/agentic-vbench/releases/download/medvedev-de-minaur-2023-us-open-r4-media-v1/medvedev-de-minaur-2023-us-open-r4-720p.mp4
sha256: d78c9246d5dd36b812c71b5f39bfa43ab86d1a7adf711fb7bbc6ff1d66d618b2
bytes: 804641210
video: H.264, 1280x720, 30000/1001 fps
audio: AAC in the hosted source only
```

The historical format-22 checksum is not reused; it describes a different binary.

## Observed final artifact

Formal calibration directly observed the final runtime material at
`/workspace/materials/match.mp4`. The full-media input manifest binds the same file
by SHA-256, byte length, stream probe, and decoded-frame count. These are observed
properties of that retained artifact, not values inferred only from the remux
command:

```text
path: /workspace/materials/match.mp4
sha256: d61bee17596a28dbc8f8b607e4fc0dd6542885dbe9cdad18e1953e89363b0860
bytes: 685013111
codec: h264
dimensions: 1280x720
average frame rate: 30000/1001
duration: 7152.578767 seconds
decoded frames: 214363
audio streams: 0
```

The full-media input manifest independently records the same SHA, byte length,
probe, and frame count. Its SHA-256 is
`2e78270f3051ddd902bb13212e4e2adceb80b5f065524e39186211e727d8998e`.

## Docker build and calibrated invariant

The calibrated task [`Dockerfile`](../environment/Dockerfile) retains the
hosted-source SHA check, copies only source video stream `0:v:0`, strips audio with
`-an`, removes source metadata, deletes the downloaded source, and checks that the
result is nonempty, 1280x720, and has no audio stream:

```text
source SHA-256 required before remux:
  d78c9246d5dd36b812c71b5f39bfa43ab86d1a7adf711fb7bbc6ff1d66d618b2

final /baked/match.mp4 checked during build:
  width:   1280
  height:  720
  audio streams: 0
```

The exact final SHA and byte length are observed and independently bound by the
full-media and source-derived input manifests and by the pinned task/calibration
image identities. The deliberate no-media ablation has no media SHA or byte count.
These values are not hard-coded post-remux assertions in the calibrated Dockerfile.
Adding those two commands now would change Docker image config/history, yielding a
new task image and invalidating the exact-image calibration claim. Such a Dockerfile
hardening should therefore be followed by a new image build and complete
recalibration rather than silently paired with the existing `f592...` image
evidence.

## Pinned images

```text
canonical task image id:
  sha256:f592cda4dfc09ca25ae3a19d7e65d17248fb01059f061368eecf14ae1ae9cb28

fixed Codex calibration image reference:
  avb-medvedev-codex@sha256:390fb56051fafb49b5b4b797cb15704469294f816255994e9ee0fd21fe2da06b
fixed Codex calibration image id:
  sha256:390fb56051fafb49b5b4b797cb15704469294f816255994e9ee0fd21fe2da06b
platform: linux/arm64
image size: 1085220502 bytes
Codex CLI: 0.149.1
```

Every retained formal validation record reports the fixed calibration image by
digest and ID. No mutable image tag is used as the evidence identity.

## Bound task artifacts

Strict-v3 generation-time validation binds these exact files in every retained run:

```text
2b025b557a17f2443e9b8f5951ee19562eee570038d092a7757b957555d1cd55  steps/solve/instruction.md
3ece409c4c223c2bf2120fb1ef251d76c88bc6150fb59b4d0b6963bcf69c4b40  steps/solve/tests/judge.py
6b1801277acdc2b73ee13c4a0f51b0ef90a2860edd43d834c872aec623cda5b4  steps/solve/tests/test_judge.py
75c03d3084ebc3670ffbf77ee2ca5b0a46f16f8a4feb6b1d834c80aaa3a4c5c5  steps/solve/solution/solve.sh
```

Those old judge/test hashes are retained provenance, not current official scorer
hashes. The reviewer-requested hierarchical revision currently uses:

```text
a47317a7d9b2095e8131ca4f93dbf500756d75ccaf3a7d47b1991ddfc60b93eb  steps/solve/tests/judge.py
35ed4790595822214ec4777606d5765dc47e3a6290bebf8a72a2090e73bea46e  steps/solve/tests/test_judge.py
3f47680ac144d0aca1c3601335de3ab70c870e1e759bf91e2acdc1e594f1d1e2  calibration/test_regrades.py
```

The current deterministic judge suite passes `32/32` tests, including oracle
`1.0`, empty `0.0`, bottleneck plateaus, resource limits, exact-event diagnostics,
ordering, duplicates, malformed schema, shot insertion/deletion/order, and CLI
regressions. The calibration regrade tests also pass. The task structure checker
passes.

No task commit is supplied because these records predate an immutable submitted
commit. Overlay task checksums and frozen file hashes are used instead; a future
rerun should add the actual task commit without replacing the existing evidence.
