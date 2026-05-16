---
title: v2 19-task repair suite — locked spec
summary: Per-task contract (source video, clip range, corruption recipe, judge, oracle) for the 19-task v2 repair benchmark grounded in `video_100/` source corpus.
read_when: Building any new task in the v2 19, dispatching a multi-agent build job, deciding which existing v1 task can be retired, evaluating whether a new request fits inside the v2 scope or is out-of-scope.
---

# v2 19-task repair suite

Locked 2026-05-12. Source corpus: `/Users/zonghengcao/Downloads/vlm_benchmark/video_100/` (ignore `ai_films/`, use `films/` + `ads/` + `others/`). Existing v1 tasks (`dns-denoise-task*`, `voicebank-demand-task*`, `disfluency-clean-task*`, `div4k-50-task*`, `davis-vos-task*`, `gopro-deblur-task*`, `video-edit-bench-*`) remain alongside as the v1 baseline.

## Conventions

All v2 task IDs prefix with `v2-` to keep them clearly separated from v1: `v2-dereverb-task01`, `v2-glitch-dup-short-task01`, etc.

Source video referenced by `video_100/<slot>/<NN_<id>>/video.mp4`. Generators clip with `ffmpeg -ss <start> -t <duration>`. Binary outputs gitignored; regenerable from upstream YouTube IDs in `manifest.csv`.

CPU vs GPU split:
- **CPU judges (groups A–C, 11 tasks)**: audio + cut-based + glitch + mask color/deblur (deblur uses PSNR/SSIM only, no LPIPS). Run on Docker locally, Modal cheaply.
- **GPU judges (group D, 4 tasks)**: SR (LPIPS) + swap (SAM2 + CLIP). Plan separate judge image with CUDA.

## Group A — Audio synthetic injection (5 tasks, CPU)

Pattern: extract 30–60 s clean speech segment via `ffmpeg -i source.mp4 -vn -ac 1 -ar 16000 clean.wav`, apply paper-recipe corruption, judge against `clean.wav`. Agent receives only the corrupted WAV.

### `v2-dns-denoise-task01`

- **Source**: `films/18_qIige41_h1Q/video.mp4` (Omeleto "THE SHABBOS GOY" — 7-min indie dialog, low room noise).
- **Clip**: 60 s starting at ~0:30 (first scene with two-speaker dialog).
- **Corruption**: Overlay one noise file from DNS-Challenge 2020 noise pool (`microsoft/DNS-Challenge` GitHub, `datasets/test_set/noise/`) mixed at uniform random SNR ∈ [−5, +20] dB. Use `numpy.random.default_rng(42)` for reproducibility.
- **Judge**: `reward = 0.4·clip01((PESQ-1)/3.5) + 0.3·STOI + 0.3·clip01((SI-SDR+10)/30)`. Libs: `pesq`, `pystoi`, custom SI-SDR.
- **Oracle**: `noisereduce` spectral gating. Expected reward ~0.35–0.45.

### `v2-voicebank-denoise-task01`

- **Source**: `others/02_news/02_5zV2hlI56MM/video.mp4` (Reuters "Trump victory" — anchor read, studio mic).
- **Clip**: 60 s from ~0:10 anchor segment.
- **Corruption**: Mix in DEMAND-style noise from 1 of 5 fixed environments (kitchen/cafe/office/car/restaurant) at fixed SNR ∈ {0, 5, 10, 15} dB. Use `JacobLinCool/VoiceBank-DEMAND-16k` noise as the pool.
- **Judge**: Same composite as dns-denoise.
- **Oracle**: `noisereduce`. Expected reward ~0.60–0.75 (cleaner SNR floor).

### `v2-dereverb-task01`

- **Source**: `others/06_entertainment/03_CUpOMSJ1MdU/video.mp4` (SNL Elon Musk cold open — studio audio, low room reflection) OR `others/02_news` anchor.
- **Clip**: 60 s of clean cold-open monologue.
- **Corruption**: Convolve with synthetic RIR via `pyroomacoustics` (10 m × 8 m × 3 m shoebox, RT60 ∈ [0.2, 1.5] s drawn uniformly with seed 42, source/mic placed asymmetrically). Save the RIR alongside for sanity.
- **Judge**: `reward = 0.5·clip01(SRMR/8) + 0.5·clip01((PESQ-1)/3.5)`. Libs: `SRMRpy`, `pesq`.
- **Oracle**: `scipy.signal.wiener` adaptive Wiener deconv with default params. Expected ~0.30–0.45.

### `v2-declip-task01`

- **Source**: `others/09_vlogs/04_iFJyCs708a0/video.mp4` (Casey Neistat marathon — naturally loud / high-modulation vlog speech).
- **Clip**: 30 s of dialog peaks.
- **Corruption**: URGENT-2024 quantile-clip: `np.clip(x, -q, q)` where `q = quantile(|x|, 0.5)` (50 % of samples saturated). Save mask of clipped samples for masked-SDR.
- **Judge**: `reward = 0.5·masked-SDR-on-clipped-regions + 0.5·STOI-full`. masked-SDR = SDR computed only on samples that were clipped (where signal information was lost).
- **Oracle**: `scipy.interpolate.CubicSpline` between unclipped peaks. Expected ~0.40–0.55.

### `v2-codec-restore-task01`

- **Source**: `others/08_travel_events/01_tXaTZBSeho4/video.mp4` (Visit Korea Year — already YouTube re-encoded, realistic for "audio that's been through multiple re-uploads").
- **Clip**: 60 s of dialog/voiceover segment.
- **Corruption**: Re-encode to Opus 12 kbps via `ffmpeg -i clean.wav -c:a libopus -b:a 12k corrupted.opus` then decode back to WAV.
- **Judge**: `reward = 0.5·clip01((PESQ-1)/3.5) + 0.5·clip01(1 - LSD-on-4-8kHz / 5)`. LSD = log-spectral distance, with band-limit 4-8 kHz (the band Opus 12 k attenuates most). Lib: `librosa` for spectrogram.
- **Oracle**: passthrough (decoded WAV without restoration). Expected ~0.45–0.55.

## Group B — Cut-based JSON (4 tasks, CPU)

Pattern: agent reads `instruction.md` + `source.mp4`, emits `{cuts: [{start_ms, end_ms, reason}]}` JSON + `output.mp4` with those segments removed (re-encoded with `ffmpeg -i source.mp4 -filter_complex select+atrim concat`). Judge verifies each ground-truth cut is reflected in the output. Per-cut binary (full credit if absent in output, null if still present); aggregate = mean over cuts.

### `v2-disfluency-meeting-task01`

- **Source**: `hhoangphuoc/ami-disfluency` (HF gated, Apache 2.0). Pick one clip with ≥5 annotated disfluencies and ≤60 s duration.
- **GT cuts**: from the dataset's annotation columns (disfluency events with start/end timestamps).
- **Judge**: For each GT cut `(s, e)`: (a) run `whisper-timestamped` on agent's output, (b) check no transcript token overlaps `(s, e)` time window. Visual check via frame extraction at boundaries (no abrupt jumps without smoothing).
- **Oracle**: copy GT cuts verbatim → write `output.mp4` with those segments cut. Expected ~0.95.

### `v2-disfluency-comedy-task01`

- **Source**: `others/12_comedy/04_qZyLWgoEqZk/video.mp4` (Pitch Meeting "The Crow 2024" — Ryan George uses "you know", "super easy, barely an inconvenience" as recurring filler-style phrases in character).
- **Clip**: 60 s from a Pitch Meeting "bit" with 4–6 natural fillers.
- **GT cuts**: Generated offline by running `whisper-timestamped --detect_disfluencies=True` on the clean clip and **manually spot-checking** the resulting filler timestamps before committing them as GT. Vendor the GT JSON in `tests/cuts.json`.
- **Judge**: Same as ami task above.
- **Oracle**: GT cuts verbatim. Expected ~0.95.

### `v2-content-cut-explainer-task01`

- **Source**: `others/02_news/03_tRVVXDyg3RY/video.mp4` (WSJ "How China's 100B+ Shipbuilding Empire" — multi-segment explainer).
- **Clip**: 90 s spanning ≥3 chapter-like segments.
- **Instruction**: prompt-driven, e.g. "Remove the segment about US Navy procurement (keep China shipbuilding focus only)."
- **GT cuts**: hand-annotated time windows for the off-topic segments.
- **Judge**: (a) per-cut binary as above; (b) optional VLM-as-judge sanity: re-prompt Claude-Sonnet on the output asking "does this video still contain content about X?" — should be "no" for off-topic, "yes" for on-topic.
- **Oracle**: GT verbatim. Expected ~0.90–1.00.

### `v2-content-cut-review-task01`

- **Source**: `others/05_science_tech/03_9Yg1RjQAdu8/video.mp4` (Pixel 9 Pro camera hands-on — intro / walkaround / verdict structure).
- **Clip**: 90 s spanning intro + walkaround.
- **Instruction**: "Remove the intro segment (keep only the walkaround and verdict)."
- **GT / Judge / Oracle**: same pattern.

## Group C — Visual glitch & mask region (6 tasks, CPU)

### Glitch — duplicated shot ×2

Pattern: inject N-frame duplicate into one or two spots in a clip. Agent identifies them and emits `{glitches: [{type:"duplicated", start_frame, end_frame}]}` + cleaned output. Judge verifies each GT injection is absent in output by frame-similarity check (consecutive frames should now have normal motion delta, not zero).

#### `v2-glitch-dup-short-task01`

- **Source**: `others/01_sports/01_yPvoKz6tyJs/video.mp4` (F1 2024 British GP highlights — fast cuts, easy to hide a 5-frame dup).
- **Clip**: 60 s.
- **Corruption**: Inject 5-frame dup at 2 random positions (seed 42). Save GT JSON.
- **Judge**: For each GT injection `(start, end)`: compute mean abs frame-diff in agent's output across that window — should be >> 0 (no longer frozen). Binary credit per GT.

#### `v2-glitch-dup-long-task01`

- **Source**: `others/13_music/04_b1kbLwvqugk/video.mp4` (Taylor Swift Anti-Hero MV — fast music-video cuts).
- **Clip**: 60 s.
- **Corruption**: Inject 30-frame dup at 2 positions.
- Same judge.

### Color & deblur — mask region ×4

Pattern: agent reads `source.mp4` + `mask.png` (binary mask indicating the region to repair). Judge computes metrics IN-mask (vs clean reference) AND OUT-of-mask (vs source — should be near-perfect, agent didn't damage what wasn't broken). `reward = 0.7·in_mask + 0.3·out_mask_preserve`.

#### `v2-color-grade-A-task01`

- **Source**: `others/08_travel_events/01_tXaTZBSeho4/video.mp4` (Visit Korea — strong color palette).
- **Clip**: 30 s.
- **Mask**: foreground person (generated once via SAM2 offline, vendored as PNG).
- **Corruption**: Apply a "cool/desaturated" LUT to the mask region (shift hue −10°, sat ×0.5). Clean is the original.
- **Judge**: in-mask ΔE2000 (`colormath` or `skimage.color`) vs clean; out-mask PSNR vs source.

#### `v2-color-grade-B-task01`

- **Source**: `others/07_animation/03_23Mz2j2VQtw/video.mp4` (GOBELINS "DARE TO BE FABULOUS" — stylized color).
- **Clip**: 30 s.
- **Mask**: stylized character.
- **Corruption**: Apply a "warm/orange" LUT to mask region (hue +15°, +10 saturation).
- Same judge.

#### `v2-deblur-gaussian-task01`

- **Source**: `others/05_science_tech/03_9Yg1RjQAdu8/video.mp4` (Pixel 9 camera close-ups).
- **Clip**: 30 s.
- **Mask**: phone/product foreground.
- **Corruption**: Gaussian blur σ=3 (kernel 15×15) on mask region only.
- **Judge**: in-mask PSNR-Y + SSIM-Y vs clean; out-mask PSNR vs source.

#### `v2-deblur-motion-task01`

- **Source**: `others/01_sports/03_NGSPg5ns2-0/video.mp4` (F1 Qatar GP — fast-moving car).
- **Clip**: 30 s with a car traversing frame.
- **Mask**: car object.
- **Corruption**: Linear motion-blur kernel (length 15 px, angle matched to car motion) on mask region.
- Same judge as Gaussian.

## Group D — SR + swap (4 tasks, GPU judges)

### Super-resolution ×2

Pattern: agent receives downsampled LR clip, must produce HR upscale matching original. Pair-construction: take 10-s clip from HR source, `ffmpeg -vf scale=W/2:H/2` (or /4), agent restores to original resolution.

#### `v2-sr-2x-task01`

- **Source**: `others/05_science_tech/03_9Yg1RjQAdu8/video.mp4` (MKBHD Pixel 9 Pro — fine textures, small text).
- **Clip**: 10 s.
- **Corruption**: 2× downsample via `scale=iw/2:ih/2:flags=bicubic`.
- **Judge**: per-frame PSNR + SSIM on Y-channel + LPIPS (alex). Composite: `0.4·clip01((PSNR-15)/25) + 0.3·SSIM + 0.3·clip01(1-LPIPS)`.
- **Oracle**: Pillow LANCZOS upscale. Expected ~0.55–0.70.

#### `v2-sr-4x-task01`

- **Source**: `others/07_animation/03_23Mz2j2VQtw/video.mp4` (GOBELINS — sharp linework, SR-quality-revealing).
- **Clip**: 10 s.
- **Corruption**: 4× downsample.
- Same judge. Oracle expected ~0.40–0.55 (4× is harder).

### Swap ×2

Pattern: agent receives source + instruction ("swap the X for a Y"). Emits `{swaps: [{target_object, replacement, start_frame, end_frame, mask_path}]}` + `output.mp4`. Judge:
1. Run SAM2+CLIP on source — confirm target was detected in input.
2. Run SAM2+CLIP on agent's output — confirm replacement is detected, target is not.
3. Out-of-mask PSNR vs source — preservation check.

`reward = 0.4·target_replaced + 0.3·replacement_present + 0.3·out_mask_preserve`.

#### `v2-swap-car-task01`

- **Source**: `others/10_autos/03_ZImYRu7hli4/video.mp4` (Lamborghini Revuelto v Ferrari SF90 v Porsche 918 drag race).
- **Clip**: 30 s of one car prominently visible.
- **Instruction**: "Swap the red Ferrari for a blue Lamborghini."
- Judge as above. Oracle: a hand-edited reference output for sanity.

#### `v2-swap-product-task01`

- **Source**: `others/05_science_tech/02_9GP43vKQq9I/video.mp4` (LG soundbars CES 2024) OR `04_DJ5OwotluV4` (Pixel 9 Pro Fold) — discrete product on display.
- **Clip**: 30 s.
- **Instruction**: "Swap the soundbar for a guitar amplifier."
- Same judge.

## Dispatch (4 parallel agents)

| Agent | Group | Tasks | Reference scripts (already in repo) |
|---|---|---|---|
| A | Audio inj | 5 | `scripts/generate_dns_denoise.py`, `scripts/generate_voicebank_demand.py` |
| B | Cut-based | 4 | `scripts/generate_disfluency_speech.py` (pattern), `scripts/generate_task5_4.py` (Harbor multi-step) |
| C | Glitch + mask | 6 | `scripts/generate_davis_vos.py` (mask pattern), `scripts/generate_gopro_deblur.py` (paired frames) |
| D | SR + swap | 4 | `scripts/generate_div4k_50.py` (SR pattern), `scripts/generate_davis_vos.py` (mask) |

Each agent:
1. Reads this doc + the indicated reference scripts.
2. Writes `scripts/generate_v2_<task>.py` per task. Generator: download source clip from `video_100/`, apply corruption, write `tasks/v2-<task>/steps/solve/{instruction.md, workdir/setup.sh, tests/test.sh, tests/judge.py, solution/solve.sh}`, ensure binaries gitignored.
3. Smoke-tests each task: `harbor run -p ./tasks -i v2-<task> -a oracle -e docker -y` — confirms oracle reward in the expected range.
4. Reports per-task status in markdown table.

Smoke target: oracle reward in expected range. Skip claude-code rollout in build phase (separate $$ run later).

## Out of scope

- `claude-code` rollouts on all 19 (separate `harbor run -e modal --n-concurrent 19` once builds pass).
- License sanitization for public release (deprioritized; regenerate-from-upstream pattern already handles lineage).
- Retiring v1 tasks (decide after v2 ships).
- Aggregation/dashboard for v2-specific results.
