# Overnight experiment plan — 19-task repair benchmark

Started: 2026-05-13 02:50 PST. Coordinator: Claude (Opus 4.7). User asleep.

## Goal

Deliver a self-contained `experiment/` folder with:
- per-task generators that clip + corrupt + write Harbor task dirs
- oracle smoke results
- claude-code rollout results (where feasible)
- a final `REPORT.md` the user reads in the morning

## Scope strategy (per user)

> "Q3: depends on you, can you focus on several tasks first, and iterate on it, and run agents, and later expand to all tasks"

Depth-first: lock 5 audio tasks end-to-end (build → oracle smoke → claude-code rollout → reward) before expanding to cut-based / glitch / mask / SR / swap.

## Source video → task mapping

19 tasks, 16 unique source files copied into `experiment/sources/`. Source picks resolved during yesterday's design phase (see prior session in `docs/v2-task-suite.md`).

| # | Task | Source file in `experiment/sources/` |
|---|---|---|
| 1 | dns-denoise | `01-dns-denoise-veritasium-blue-roses.mp4` (Veritasium "Blue Roses") |
| 2 | voicebank-denoise | `02-voicebank-reuters-trump-victory.mp4` (Reuters anchor) |
| 3 | dereverb | `03-dereverb-snl-elon-musk-cold-open.mp4` (SNL studio mic) |
| 4 | declip | `04-declip-casey-neistat-marathon.mp4` (vlog over-mod) |
| 5 | codec-restore | `05-codec-restore-visit-korea.mp4` (already-encoded travel) |
| 6 | disfluency-meeting | `06-disfluency-airrack-nyc-marathon.mp4` (Airrack vlog — ami-disfluency was micro-clips, fallback per user OK) |
| 7 | disfluency-comedy | `07-disfluency-pitch-meeting-crow.mp4` (Ryan George fillers) |
| 8 | content-cut-explainer | `08-content-cut-wsj-china-shipbuilding.mp4` (chaptered explainer) |
| 9 | content-cut-review | `09-mkbhd-pixel9pro-camera.mp4` (intro/walkaround/verdict) |
| 10 | glitch-dup-short | `10-glitch-dup-short-f1-british-gp.mp4` (fast cuts) |
| 11 | glitch-dup-long | `11-glitch-dup-long-anti-hero.mp4` (music-video pace) |
| 12 | color-grade-A | `05-codec-restore-visit-korea.mp4` (reuse — strong palette) |
| 13 | color-grade-B | `13-gobelins-dare-to-be-fabulous.mp4` (animation linework) |
| 14 | deblur-Gaussian | `09-mkbhd-pixel9pro-camera.mp4` (reuse — fine detail) |
| 15 | deblur-motion | `15-deblur-motion-f1-qatar-gp.mp4` (car motion) |
| 16 | SR-2× | `09-mkbhd-pixel9pro-camera.mp4` (reuse) |
| 17 | SR-4× | `13-gobelins-dare-to-be-fabulous.mp4` (reuse) |
| 18 | swap-car | `18-swap-car-lambo-ferrari-porsche.mp4` |
| 19 | swap-product | `19-swap-product-lg-soundbars.mp4` |

## Phases

| Phase | Goal | ETA | Status |
|---|---|---|---|
| 0 | Setup `experiment/`, copy videos, env checks | 30 min | in_progress |
| 1 | Build 5 audio task generators (parallel agent) | 90 min | pending |
| 2 | Oracle smoke audio tasks on local Docker | 30 min | pending |
| 3 | claude-code rollout on audio tasks | 90 min | pending |
| 4 | Expand: glitch + disfluency + content-cut (6 more) | 180 min | pending |
| 5 | Smoke + rollout next batch | 90 min | pending |
| 6 | Write `REPORT.md` | 20 min | pending |

After phase 5, if time, continue to mask color/deblur (4 more). Skip SR/swap unless time is generous (they need LPIPS/SAM2 — extra deps).

## Corruption recipe one-liners (from updated supplement)

| # | Task | One-line corruption |
|---|---|---|
| 1 | dns-denoise | additive overlay: `speech + DNS_noise_scaled_to_SNR`; SNR ~ Uniform(−5, +20) dB |
| 2 | voicebank-denoise | same shape, noise ∈ DEMAND 5-env, SNR ∈ {0,5,10,15} dB |
| 3 | dereverb | convolve with pyroomacoustics shoebox RIR; absorption via `pra.inverse_sabine(RT60, dims)` for RT60 ~ Uniform(0.2, 1.5) s |
| 4 | declip | normalize then `np.clip(x, ±q)` at q∈{0.5, 0.7, 0.9} quantile; save `clip_mask` for masked-SDR |
| 5 | codec-restore | ffmpeg roundtrip through opus_12k (fixed tier) |
| 6 | disfluency-meeting | no inject — whisper-timestamped GT, manually frozen |
| 7 | disfluency-comedy | same as #6 |
| 8 | content-cut-explainer | no inject — prompt-driven, hand-annotated GT windows |
| 9 | content-cut-review | same as #8 |
| 10 | glitch-dup-short | inject 5-frame dup × 2 spots via `tpad=stop_mode=clone:stop_duration=5/fps` (seed 42) |
| 11 | glitch-dup-long | same recipe, 30-frame dup × 2 |
| 12 | color-grade-A | SAM2 mask offline; wrong LUT (hue −10°, sat ×0.5) in mask only |
| 13 | color-grade-B | SAM2 mask offline; wrong LUT (hue +15°, sat ×1.2) in mask only |
| 14 | deblur-Gaussian | SAM2 mask offline; Gaussian σ=3, kernel 15×15 in mask |
| 15 | deblur-motion | SAM2 mask offline; linear motion-blur kernel (15 px, motion-aligned angle) in mask |
| 16 | SR-2× | `ffmpeg -vf scale=iw/2:ih/2:flags=bicubic` |
| 17 | SR-4× | `ffmpeg -vf scale=iw/4:ih/4:flags=bicubic` |
| 18 | swap-car | no inject — prompt "swap red Ferrari for blue Lamborghini" |
| 19 | swap-product | no inject — prompt "swap soundbar for guitar amplifier" |

## Constraints (per user)

- No cost ceiling — run as much as needed.
- Local Docker only (no Modal).
- Everything scoped to `experiment/`. **No changes to repo-root `tasks/`, `scripts/`, `docs/`.**
- Don't ask questions. Push forward.

## Iteration policy

For each task:
1. Build generator → run it → confirm task dir is well-formed.
2. Oracle smoke → expect known reward range. If outside range, iterate generator/judge.
3. claude-code rollout → record reward, runtime, cost.
4. Move on to next task. Don't dwell.

If a task type fails 2 times after fixes, mark FAILED in REPORT, move on.
