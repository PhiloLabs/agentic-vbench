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
- An agent that returns the broken input unmodified scores at most the
  preservation reservation (≤ 0.10 — see below).
- The oracle solution (the bundled golden reference) scores **1**.
- Any monotonic improvement on the chosen metric moves the score linearly
  between those anchors, clipped at the endpoints.

This form is the convention in URGENT 2024, the NTIRE perceptual tracks,
and DNS Challenge v3+.

## Per-family base metrics

The metric for each family tracks the paper-canonical metric for that
task type and is mapped to `[0, 1]` with per-task LO/HI anchors picked
so a broken passthrough lands at 0 and the golden identity lands at 1.

| Family | Restoration metric | Source |
|---|---|---|
| `dns-denoise` | DNSMOS-OVL + STOI + SI-SDR (PESQ-WB + STOI + SI-SDR fallback) | DNS Challenge 2020 |
| `voicebank-denoise` | CSIG + CBAK + COVL composite | Valentini-Botinhao 2016 |
| `dereverb` | PESQ-WB + STOI + CD | REVERB Challenge |
| `declip` | Masked SI-SDR + ESTOI + PESQ-WB | URGENT 2024 |
| `codec-restore` | DNSMOS-OVL + STOI + LSD_4-8kHz (PESQ-WB + LSD fallback) | Codec-SUPERB |
| `color-shot` | CIEDE2000 in-window | CIE perceptual standard |
| `deblur` | PSNR-Y + SSIM-Y (in-mask × in-window) | NTIRE perceptual track |
| `sr` | PSNR-Y + SSIM-Y in-shot + localisation IoU | NTIRE 2022+ composite |
| `swap` | Whole-video PSNR + length penalty | — |
| `cut`, `glitch`, `disfluency` | Binary range-F1 + SSIM honesty gate | — |

## Preservation reservation

Every video / audio judge with a localised corruption window also runs a
preservation check on the untouched region (SSIM ≥ 0.95 outside the
window). That check contributes **10% of the total reward**:

```
reward = 0.90 * restoration_score + 0.10 * preservation_pass
```

Why a reservation rather than a strict gate: a broken passthrough
trivially passes preservation (it didn't change anything), so the 10%
mass is technically free credit on the floor. We keep it as a
reservation because it still meaningfully penalises agents that
*degrade* the untouched region (SSIM < 0.95 → 0 there). A strict gate
would collapse those to reward 0, which we found over-punishes
near-miss agents.

The honest range-F1 families (`cut`, `glitch`, `disfluency`) do not have
a preservation reservation — their metric naturally floors at 0 for
empty submissions and the SSIM gate catches honesty violations.

`swap` also has no preservation reservation: the whole-video PSNR
already drops sharply when the swapped shots aren't restored, so
broken passthrough lands at 0 directly.

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
    "reason": "ok",
    "in_window": {"pesq_wb": 2.957, "stoi": 0.91, "...": "..."},
    "out_window": {"out_si_sdr_db": 158.6, "out_n_samples": 320000},
    "weights": {"in": 0.90, "out": 0.10},
    "...": "..."
  }
}
```

`reward` is the final composite, clipped to `[0, 1]`. `details` carries
the per-family metric breakdown, the in-window vs out-window split, and
the 0.90 / 0.10 mass weights (where applicable).
