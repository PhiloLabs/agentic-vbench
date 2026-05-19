# Verifier design — universal normalize-improvement

This doc describes how `agentic_vbench_repair` tasks are scored. The
verifier code is baked into each task's `tests/judge.py` and runs at trial
end. Sequencing + assembly tasks score deterministically off the agent's
reported ordering and don't need this framework.

## Universal score form

Every per-task metric is mapped into `[0, 1]` by an affine ratio against
two per-task anchors: the broken input (the corrupted clip the agent
receives) and the golden reference (the original, uncorrupted clip).

- higher-is-better:
  `score = clip((M_out − M_broken) / (M_golden − M_broken), 0, 1)`
- lower-is-better:
  `score = clip((M_broken − M_out) / (M_broken − M_golden), 0, 1)`

By construction:
- An agent that returns the broken input unmodified scores **0**.
- The oracle solution (the bundled golden reference) scores **1**.
- Any monotonic improvement on the chosen metric moves the score linearly
  between those anchors, clipped at the endpoints.

This form is the convention in URGENT 2024, the NTIRE perceptual tracks,
and DNS Challenge v3+.

## Per-family base metrics

The metric for each family is chosen to maximise the broken→golden spread
under the universal formula and to track the paper-canonical metric for
that task type.

| Family | Metric | Source |
|---|---|---|
| `dns-denoise`, `voicebank-denoise` | PESQ-WB in-window | DNS Challenge, Valentini 2016 |
| `dereverb` | SRMR (no-reference) + PESQ-WB sanity gate | REVERB Challenge |
| `declip` | Masked SI-SDR on `clip_mask` only | URGENT 2024 |
| `codec-restore` | LSD in-window | Codec-SUPERB |
| `color-shot` | CIEDE2000 in-window | CIE perceptual standard |
| `deblur` | LPIPS (in-mask × in-window) | NTIRE perceptual track |
| `sr` | 0.7·LPIPS + 0.3·Y-PSNR in-shot | NTIRE 2022+ composite |
| `swap` | LPIPS on swap-window, ±5-frame tolerance | — |
| `cut`, `glitch`, `disfluency` | Binary range-F1 + SSIM honesty gate | — |

## Design choices

1. **In-window-only scoring.** For tasks with a localised corruption, the
   metric is computed only on the corrupted span (a time window, a mask,
   or both). Out-of-window content is not part of the score — preserving
   the untouched part of the clip is the broken baseline (score 0), not
   free credit toward 1.
2. **Sanity gates, not score components.** Things like "must have the
   right duration", "must have a video stream", "out-of-window PSNR
   reasonable" are binary gates. Failure → reward 0. Success → no
   contribution either way.
3. **Per-task anchors, not global anchors.** `M_broken` and `M_golden` are
   measured per task at build time using that task's specific broken
   input and golden reference, so the same metric can have different
   spread on different clips.

## Reward output

Each judge writes `/logs/verifier/reward.json`:

```json
{
  "reward": 0.412,
  "details": {
    "metric_used": "pesq_wb",
    "m_broken": 1.873,
    "m_golden": 4.500,
    "m_out":   2.957,
    "...": "..."
  }
}
```

`reward` is the universal-formula output, clipped to `[0, 1]`. `details`
carries the per-task breakdown (which metric was used, the three anchor
values, plus any family-specific diagnostic fields).
