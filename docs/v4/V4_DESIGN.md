# v4 verifier — design

## Why v4

Many v3 task baselines (broken-input passthrough) score well above 0:

| Task | v3 broken | v3 golden | Free-credit source |
|---|---|---|---|
| declip | 0.834 | 1.000 | 15% out-window SI-SDR is perfect on untouched samples |
| sr-2x | 0.756 | 0.983 | PSNR base = 25 dB on bicubic; preserve component free |
| voicebank-denoise | 0.713 | 1.000 | STOI on noisy speech is already ~0.85 |
| codec-restore | 0.699 | 1.000 | Codec preserves most of the bandwidth; PESQ stays > 2 |
| deblur-gaussian-mkbhd | 0.695 | 0.832 | Bbox mask: passthrough is 1.0 outside mask, drags up |
| dns-denoise | 0.498 | 1.000 | STOI floor + 15% out-window preservation |
| sr-4x | 0.470 | 0.978 | Lower PSNR-base but preservation still helps |
| deblur-motion-f1 | 0.389 | 0.850 | Out-of-window preservation = +0.15 |
| dereverb | 0.338 | 1.000 | PESQ baseline ~1.8 maps to non-zero score |
| swap | 0.20 | 1.000 | Codec-noise PSNR floor on swapped passthrough |
| color (3 tasks) | 0.150 | 0.927–0.952 | 15% out-window preservation |

Already 0/1 (no v4 work): cut×5, glitch×2.

## Design principles

1. **Universal normalize-improvement form.** Every metric is mapped to [0,1] via the affine ratio against per-task broken/golden anchors:
   - higher-is-better: `score = clip((M_out − M_broken) / (M_golden − M_broken), 0, 1)`
   - lower-is-better: `score = clip((M_broken − M_out) / (M_broken − M_golden), 0, 1)`
   - This guarantees broken≈0 and golden≈1 by construction. Standard in URGENT 2024, NTIRE perceptual tracks, DNS Challenge v3+.

2. **Stricter base metrics.** For each family, pick the paper-canonical metric that has the widest broken→golden spread under the universal formula:
   | Family | Metric | Rationale |
   |---|---|---|
   | dns-denoise | PESQ-WB + DNSMOS-OVRL | DNS Challenge ranking metrics |
   | voicebank-denoise | PESQ-WB | Valentini 2016 standard |
   | dereverb | SRMR (no-reference) | REVERB Challenge primary ranking |
   | declip | **masked SI-SDR** on clip_mask only | URGENT 2024: clipped samples are saturated, so masked-SI-SDR floors at ~ −∞ dB; broken→0 automatic |
   | codec-restore | MCD (mel-cepstral distortion) | Codec-SUPERB SLT 2024 standard |
   | sr-2x / sr-4x | **LPIPS** + Y-PSNR (composite) | NTIRE perceptual track; bicubic-vs-HR LPIPS gap is wide (~0.40→0) |
   | deblur (motion-f1, gaussian-mkbhd) | LPIPS + Y-PSNR (in-mask, in-window only) | GoPro literature; mask localizes scoring |
   | color-shot (3 tasks) | **CIEDE2000** in-window | CIE perceptual color difference; LumiVideo reference |
   | swap | LPIPS on swap window + masked-PSNR outside | No pixel-fidelity for swapped region; use perceptual + preservation |
   | cut, glitch, disfluency | binary range-F1 (unchanged) | already 0/1 |

3. **Drop or shrink out-of-window preservation.**
   - Audio (in-window weight 85→100% — out-window dropped; the universal formula handles preservation implicitly because broken DOES already preserve out-of-window, and we now anchor at it.)
   - Color/deblur/sr: in-window-only scoring; out-of-window preservation enters only as a tiny sanity gate (e.g., reject if PSNR_out < 25 dB).
   - Rationale: preservation freebies are exactly what's making broken score high. The universal formula already accounts for "broken is the floor", so out-of-window equivalence with broken is exactly the broken baseline (score 0), not free credit.

4. **Sanity gates, not score components.** Use binary gates for things like "agent output must be the right duration", "must have video stream", etc. Failure → reward 0. Success → no contribution either way.

5. **Hybrid math + renormalize.** Phase 1 is pure math redesign. If after running the new judges some task still has broken > 0.05 or golden < 0.95, layer an explicit per-task affine renormalize as a fallback. Document each case.

## Score schema

Each task's v4 reward.json:
```json
{
  "task_id": "exp-dns-denoise-task01",
  "family": "audio_inj",
  "metric_used": "pesq_wb",
  "m_broken": 1.873,
  "m_golden": 4.500,
  "m_claude": 2.412,
  "v4_raw_reward": 0.205,
  "v4_calibrated_reward": 0.205,
  "details": { ... full per-metric breakdown ... }
}
```

`v4_raw_reward` is the universal-formula output. `v4_calibrated_reward` is identical in phase 1; in phase 2 it may absorb an explicit per-task affine renormalize if the raw formula didn't quite land at 0/1.

## File layout

- `_framework.py` — shared helpers: `normalize_improvement`, `find_latest_artifact`, audio/video loaders.
- `judge_audio.py` — five audio-task entrypoints.
- `judge_video_color.py` — three color tasks.
- `judge_video_deblur.py` — two deblur tasks.
- `judge_video_sr.py` — two SR tasks.
- `judge_video_swap.py` — two swap tasks.
- `recompute_all.py` — top-level: runs all v4 judges, writes `logs/v4-results.tsv` and `logs/v4-per-task/*.json`.
- `build_site_v4.py` — fork of `build_site.py`, reads v4-results.tsv and emits `site/index-v4.html`.

## Iteration loop

After first pass:
- For every offender task, compute `broken − golden` spread (raw metric).
- If spread < 1 dB / metric-natural-unit, the metric is too noisy → try the secondary metric or a composite.
- If broken > 0.05 still: apply explicit renormalize fallback.
- If golden < 0.95 still: confirm the oracle output equals the GT (passthrough sanity).

Goal: every task hits broken ∈ [0, 0.05] and golden ∈ [0.95, 1.00] within 2 iterations.
