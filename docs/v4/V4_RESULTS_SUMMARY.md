# v4 verifier — final results & summary

## What changed vs v3

**v4 design goal:** make broken=0 and golden=1 by construction, expand the
middle range. Removed all "free-credit" components (out-of-window preservation,
IoU bonuses, lenient base-metric mappings) and replaced family metrics with
paper-canonical primaries that have wider broken→golden spreads.

**Universal scoring formula:**
- higher-is-better: `score = clip((M_out − M_broken) / (M_golden − M_broken), 0, 1)`
- lower-is-better: `score = clip((M_broken − M_out) / (M_broken − M_golden), 0, 1)`

**Per-family metric changes:**

| Family | v3 metric | v4 metric | Why |
|---|---|---|---|
| dns-denoise | composite (PESQ+STOI+LSD+SI-SDR, 85/15 windows) | PESQ-WB in-window only | Drops 15% out-window freebie; PESQ-WB is DNS Challenge standard |
| voicebank-denoise | same composite | PESQ-WB in-window only | Valentini 2016 standard |
| dereverb | composite | SRMR in-window + PESQ-WB sanity gate | REVERB Challenge primary ranking metric; PESQ-gate catches artifactual SRMR boosts |
| declip | composite (full-signal PESQ + 15% out-window) | **masked SI-SDR** on clip_mask samples only | URGENT 2024 protocol; clipped samples are saturated → broken→0 automatic |
| codec-restore | composite | LSD in-window only | Codec-SUPERB standard; better numerical range than MCD |
| color-shot (3) | ΔE76 + IoU + out-window | CIEDE2000 (ΔE2000) in-window only | CIE perceptual standard; in-window only kills 15% freebie |
| deblur (2) | PSNR/SSIM + out-mask preserve + out-window | LPIPS in-mask × in-window only | NTIRE perceptual track; mask-localised |
| sr (2) | PSNR/SSIM + IoU + out-window | 0.7×LPIPS + 0.3×Y-PSNR in-shot only | NTIRE 2022+ composite; no preservation bonus |
| swap (2) | whole-video PSNR | LPIPS on swap-window only | Discriminative for swapped content |
| cut, glitch, disfluency (7) | binary range-F1 + honesty gate | unchanged | Already pin broken=0, golden=1 |

## Final v4 scores (21 tasks)

| Family | Task | v3 broken | v3 claude | v4 claude (broken→0, golden→1) |
|---|---|---|---|---|
| audio | dns-denoise | 0.498 | 0.260 | **0.000** |
| audio | voicebank-denoise | 0.713 | 0.587 | **0.000** |
| audio | dereverb | 0.338 | 0.000 | **0.000** |
| audio | declip | 0.834 | 0.851 | **0.016** |
| audio | codec-restore | 0.699 | 0.539 | **0.000** |
| color | visit-korea | 0.150 | 0.203 | **0.679** ⬆⬆ |
| color | gobelins | 0.150 | 0.017 | **0.524** ⬆⬆ |
| color | v3-s1 | 0.150 | 0.000 | **0.000** |
| deblur | motion-f1 | 0.389 | 0.632 | **0.059** |
| deblur | gaussian-mkbhd | 0.695 | 0.399 | **0.000** |
| sr | sr-2x | 0.756 | 0.807 | **0.000** |
| sr | sr-4x | 0.470 | 0.622 | **0.184** |
| swap | swap-car | 0.209 | 0.124 | **0.000** |
| swap | swap-product | 0.202 | 0.043 | **0.039** |
| glitch | dup-short | 0.000 | 1.000 | 1.000 |
| glitch | dup-long | 0.000 | 1.000 | 1.000 |
| cut | mkbhd | 0.000 | 1.000 | 1.000 |
| cut | wsj | 0.000 | 0.000 | 0.000 |
| cut | disfluency×3 | 0.000 | 0.000 | 0.000 |

**Per-family v4 averages:** color_shot 0.401 · sr_shot 0.092 · deblur 0.030 · swap 0.020 · audio 0.003 · glitch 1.000 · cut 0.200. **Overall claude:** 0.214 (v3 was 0.621).

## Key takeaways

1. **broken=0, golden=1 — achieved for all 21 tasks** by construction, verified
   by `scripts/v4/validate_anchors.py` running each judge with broken→broken
   and golden→golden as the "claude" input.

2. **Color tasks expanded dramatically** — visit-korea (0.20→0.68), gobelins
   (0.02→0.52). v3 was UNDER-rewarding claude because of out-window preservation
   weighting; v4's in-window-only ΔE2000 correctly credits claude for HALVING
   the colour distortion in window.

3. **Audio tasks honestly score ~0** — Claude's enhanced.wav files have
   in-window SNR of −20 dB or worse on dns-denoise (i.e., output is louder
   than clean and noise-like). v3 was hiding this with 15% out-window freebies
   + lenient PESQ mapping. v4's in-window-only PESQ correctly says "claude
   destroyed the audio".

4. **SR/deblur claude scores are low** — claude's actual perceptual quality
   (LPIPS) is at or worse than the bicubic-broken baseline in most cases.
   v3's PSNR-only metric overcounted because PSNR is generous to the bicubic
   floor + claude's slight smoothing. LPIPS sees the perceptual reality.

5. **One concern worth noting** — sr-2x has a very narrow broken→golden spread
   (LPIPS 0.045 → 0.000) because bicubic 2× SR is already near-perfect on the
   chosen test clip. The task itself may be too easy to discriminate. Could be
   re-built with heavier corruption in a future round, but the v4 math is
   honest given the current task.

## Files

**v4 verifier code:**
- `experiment/scripts/v4/V4_DESIGN.md` — design rationale
- `experiment/scripts/v4/V4_RESULTS_SUMMARY.md` — this file
- `experiment/scripts/v4/_framework.py` — universal helpers
- `experiment/scripts/v4/judge_audio.py` — 5 audio judges (PESQ-WB / SRMR / masked SI-SDR / LSD)
- `experiment/scripts/v4/judge_video.py` — 9 video judges (ΔE2000 / LPIPS / composite)
- `experiment/scripts/v4/judge_passthrough.py` — 7 cut+glitch (v3 reward passthrough)
- `experiment/scripts/v4/recompute_all.py` — top-level driver
- `experiment/scripts/v4/validate_anchors.py` — broken=0, golden=1 sanity check

**v4 outputs:**
- `experiment/logs/v4-results.tsv` — final 21-task TSV
- `experiment/logs/v4-per-task/<task>.json` — per-task details (raw metric values, sub-scores, sanity flags)
- `experiment/site/index-v4.html` — v4 dashboard
- `experiment/site/index-v3.html` and `experiment/site/index.html` — v3 archived for comparison

**v3 archive:**
- `logs/v4-archive/rollout-results-v3.tsv` — v3 final rollout TSV (gitignored — local only)
- `logs/v4-archive/baselines-v3.tsv` — v3 baseline TSV (gitignored — local only)

## How to re-run

```bash
.venv/bin/python scripts/v4/recompute_all.py        # ~4 min, scores all tasks
.venv/bin/python scripts/v4/validate_anchors.py     # ~10 min, sanity-checks broken=0/golden=1
.venv/bin/python scripts/build_site_v4.py           # ~30s, rebuilds index-v4.html
open site/index-v4.html
```

## How to compare v3 vs v4

Open `site/index.html` (v3) and `site/index-v4.html` (v4) side by side in two
browser tabs. Both dashboards share the same media assets (`site/assets/`),
so the underlying videos / waveforms are identical; only the score formulas
and sub-score lines differ.
