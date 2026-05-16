# Oracle audit + fix — 2026-05-15

## What was found

Audited all 21 oracle `solve.sh` files. Three categories emerged:

### Category A — already ceiling-proof (9 tasks)
Submits a hardcoded GT cut-list + uses ffmpeg to materialize the answer.
Under v3 and v4, scores ≈1.0.

| Task | What solve.sh does |
|---|---|
| exp-content-cut-mkbhd-task01 | hardcoded {start_ms: 29143, end_ms: 34328}; ffmpeg cut |
| exp-content-cut-wsj-task01 | hardcoded; ffmpeg cut |
| exp-disfluency-interview-3-task01 | hardcoded; ffmpeg cut |
| exp-disfluency-interview-4-task01 | hardcoded; ffmpeg cut |
| exp-disfluency-pitch-meeting-task01 | hardcoded; ffmpeg cut |
| exp-glitch-dup-short-task01 | hardcoded GT glitches; ffmpeg splice |
| exp-glitch-dup-long-task01 | same |
| exp-swap-car-task01 | python uses gt_swap.json to re-stitch from corrupted |
| exp-swap-product-task01 | same |

Note: swap oracle scores 0.92 / 0.96 under v4 (not exactly 1.0) because of
a timeline-offset between corrupted_start and original_start for shot B —
a verifier-side quirk, not an oracle defect. The cut/glitch oracles do
hit 1.0.

### Category B — passthrough oracle (7 tasks)
solve.sh literally does `cp <broken-input> <output>` — never even tried.

| Task | solve.sh body |
|---|---|
| exp-codec-restore-task01 | `cp materials/noisy.wav output/enhanced.wav` |
| exp-dereverb-task01 | `cp materials/noisy.wav output/enhanced.wav` |
| exp-color-shot-visit-korea-task01 | `cp materials/source.mp4 output/output.mp4` |
| exp-color-shot-gobelins-task01 | same |
| exp-color-shot-v3-s1-task01 | same |
| exp-deblur-motion-f1-task01 | `cp materials/corrupted.mp4 output/output.mp4` |
| exp-deblur-gaussian-mkbhd-task01 | same |

Under v4 these score 0 (broken anchor). Under v3 they inherit the broken
baseline (0.15–0.83 depending on family freebies).

### Category C — best-effort algorithm oracle (5 tasks)
solve.sh runs a real algorithm but isn't guaranteed to hit 1.0.

| Task | What solve.sh does | v4 oracle (pre-fix) |
|---|---|---|
| exp-dns-denoise-task01 | `noisereduce` library (real denoise) | 0.000 |
| exp-voicebank-denoise-task01 | `noisereduce` | 0.000 (made worse!) |
| exp-declip-task01 | scipy cubic-spline interpolation | 0.000 (the existing smoke artifact predates the cubic-spline code) |
| exp-sr-2x-shot-task01 | Lanczos downsample+upsample sharpening | 0.000 |
| exp-sr-4x-shot-task01 | same | 0.000 |

Notably:
- voicebank `noisereduce` made the audio WORSE (PESQ 2.28 → 1.08).
- The SR oracles' inline comment admits the design isn't reaching 1.0:
  `"Calibrated target: ~0.40-0.60"`.

## What was fixed

`scripts/v4/fix_oracle_solve_sh.py` rewrote all 12 solve.sh files (Category
B and C) to the standard ceiling-proof pattern:

```bash
#!/bin/bash
set -euo pipefail
mkdir -p /workspace/output
HERE="$(cd "$(dirname "$0")" && pwd)"
cp "$HERE/<golden_file>" /workspace/output/<artifact>
echo "oracle: copied bundled golden ..."
```

The golden reference (`clean.wav` / `clean.mp4` / `original.mp4` depending
on family) was also copied from `tests/<golden>` into `solution/<golden>`
so it ships with the oracle's mount context. Total disk cost: **~135 MB
across the 12 tasks** (mostly v3-s1 at 54 MB and sr-2x at 36 MB).

For SR tasks an additional `cat > output.json` was added because the
verifier expects the agent's submitted GT shot range JSON.

## Files changed

- 12 × `tasks/<id>/steps/solve/solution/solve.sh` — rewritten
- 12 × `tasks/<id>/steps/solve/solution/<golden_file>` — newly copied

## Next steps for the user

1. **Re-roll oracle smoke runs** — Harbor needs to execute the new
   solve.sh files to produce fresh oracle artifacts in `jobs/smoke-*`.
   Approx command:
   ```bash
   .venv/bin/python scripts/parallel_rollout.py --mode oracle --env modal --max-parallel 12
   ```
2. **Re-score with v4**:
   ```bash
   .venv/bin/python scripts/v4/recompute_oracle.py
   ```
3. **Rebuild dashboard**:
   ```bash
   .venv/bin/python scripts/build_site_v4.py
   ```

After step 3, the v4 dashboard should show oracle=1.000 for every
non-swap task. (Swap will stay at ~0.92–0.96 due to the timeline-offset
verifier quirk noted above; not an oracle bug.)

## Why this matters

Per terminal-bench's `oracle_agent.py` contract: **oracle is the floor
of task validity, not the ceiling of agent capability**. If oracle
doesn't hit 1.0, you can't tell whether claude scoring low means
"claude failed" or "the verifier is wrong". The pre-fix state had 12
tasks where this distinction was ambiguous; the post-fix state has 0.
