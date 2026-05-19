---
title: Repair-task benchmarks — feasibility map
summary: Which video/audio repair benchmarks from the playbook fit our Harbor + Modal + claude-code setup, plus what was actually verified locally and what's blocked.
read_when: Adding a new "repair" task family, deciding whether to port task6 next, picking a deterministic CPU judge for a paired-data benchmark.
---

# Repair-task benchmarks — feasibility map

Goal: which "repair" benchmarks can land in our existing Harbor pattern
(CPU sandbox, deterministic judge, materials curl/vendor) with claude-code
+ sonnet as the rollout agent. The active v4 suite (`docs/v4/V4_DESIGN.md`)
is the shipped subset; this file tracks candidates considered along the
way.

## Verified working today

**Six repair families** integrated and smoke-tested locally on Docker with claude-code + claude-sonnet-4-6. New in this latest round: **GoPro deblur** (motion-blur restoration on paired video frames).

### `dns-denoise` (signal-level audio denoising)

`scripts/generate_dns_denoise.py`. Mirror: `nkdem/DNS-Challenge-2020-DevTest-16k` (CC-BY-4.0). 300 synthetic instances. Judge: PESQ-wb + STOI + SI-SDR composite.

`task001` (fileid 268):

| Run | Reward | PESQ-wb | STOI | SI-SDR (dB) | Wall |
|---|---:|---:|---:|---:|---|
| solve.sh reference (`noisereduce`) | 0.384 | 1.04 | 0.67 | −0.6 | ~90s |
| claude-code + claude-sonnet-4-6 | **0.461** | 1.73 | 0.72 | −1.5 | 4m 26s |

Agent path: tried `deepfilternet` (Rust build), `demucs` (too heavy), settled on `noisereduce + librosa`. Reward signal differentiates real denoising from baselines.

### `voicebank-demand` (signal-level audio denoising, second-axis validation)

`scripts/generate_voicebank_demand.py`. Mirror: `JacobLinCool/VoiceBank-DEMAND-16k` — **CC-BY-4.0** (playbook claim of "Edinburgh EUL research-only" was wrong for this mirror). 824 paired test rows. Same judge as DNS (drop-in).

`task001` (id p232_001):

| Run | Reward | PESQ-wb | STOI | SI-SDR (dB) | Wall |
|---|---:|---:|---:|---:|---|
| solve.sh reference (`noisereduce`) | 0.710 | 2.88 | 0.89 | 11.0 | ~50s |
| claude-code + claude-sonnet-4-6 | **0.855** | — | — | — | 4m 19s |

Baseline much higher than DNS because VoiceBank speech is studio-clean VCTK. Dynamic range above baseline is compressed (0.71 → 0.86 vs 0.38 → 0.46 on DNS) but still differentiates.

### `disfluency-clean` (transcript-level repair — new modality)

`scripts/generate_disfluency_speech.py`. Mirror: `amaai-lab/DisfluencySpeech` (Apache-2.0). 250 test rows. Agent input: `utterance.wav` + `disfluent.txt` (= `transcript_a`). Output: `solution.json` with `cleaned_transcript`. Judge: WER vs held-out `transcript_b` reference, converted to `[0, 1]` via relative improvement over the passthrough baseline:

```
baseline_wer = WER(target=b, hyp=disfluent_a)
agent_wer    = WER(target=b, hyp=agent_output)
reward       = clip01((baseline_wer - agent_wer) / max(baseline_wer, 0.02))
```

`task001` (row 0, trivial — just "Well," removal):

| Run | reward | agent_wer | baseline_wer |
|---|---:|---:|---:|
| solve.sh reference (regex filler strip) | 1.0 | 0.0 | 0.056 |
| claude-code + claude-sonnet-4-6 | 1.0 | 0.0 | 0.056 |

`task002` (row 1, harder — false-start repair `[Neil-,+]`):

| Run | reward | agent_wer | baseline_wer | notes |
|---|---:|---:|---:|---|
| solve.sh reference (regex filler strip) | **0.5** | 0.077 | 0.154 | regex misses the false start |
| claude-code + claude-sonnet-4-6 | **0.0** | 0.462 | 0.154 | over-cleaned: ran `faster-whisper` ASR then trimmed "I guess he's leaving" past the medium-target |

The judge correctly punishes over-removal — claude-code's aggressive cleaning dropped it below passthrough. Real benchmark signal: different agents trade off "remove all fillers" vs "preserve content."

### `div4k-50` (4K image super-resolution — new category: image restoration)

`scripts/generate_div4k_50.py`. Mirror: `YSZuo/DIV4K-50` (Apache-2.0). 50 paired LQ(256²)↔HQ(4096²) PNGs. 16× upscale combined with deblur + denoise + dejpeg. Judge: PSNR + SSIM at 4K via `scikit-image`.

  reward = 0.5 · clip01((PSNR_db - 15)/25) + 0.5 · clip01(SSIM)

`task001` (image_id 0001):

| Run | Reward | PSNR (dB) | SSIM | Wall |
|---|---:|---:|---:|---|
| solve.sh reference (Pillow LANCZOS bicubic) | **0.439** | 22.3 | 0.585 | 26s |
| claude-code + claude-sonnet-4-6 | **0.000** | — | — | 40m 48s (agent timeout) |

claude-code path: pip-installed `realesrgan + basicsr + torch + opencv-python`, downloaded the `RealESRGAN_x4plus.pth` weights (64 MB), ran pass 1 (256→1024 — succeeded, ~15 min on 2 vCPUs), then hit OOM-style memory pressure at pass 2 (1024→4096). Pivoted to tiled inference and was actively computing the second pass when the 40-min agent timeout fired. Reward 0.0 because no `sr.png` was written.

**Real finding**: 4K SR via Real-ESRGAN is fundamentally GPU-class on the agent side under CPU constraints. The `div4k-50` benchmark is wired correctly — the bicubic baseline (0.44) is the realistic CPU floor; reaching the Real-ESRGAN ceiling needs either a longer agent timeout (~90 min for tiled CPU inference at 4K) or a GPU sandbox. Possible follow-ups: bump `[steps.agent] timeout_sec` from 1800 to 5400 for this family; or pre-bake the Real-ESRGAN model into the Docker image so download time isn't wasted.

### `davis-vos` (semi-supervised video object segmentation — new category: video segmentation)

`scripts/generate_davis_vos.py`. Source: `DAVIS-2017-trainval-480p.zip` (BSD, direct HTTP from ETH). 30 val sequences, sliced to first 50 frames each (~9 MB/task). Judge: J&F (mean of Jaccard mIoU + boundary F-measure) via `davis2017-evaluation` (git-pip).

  reward = clip01((J + F) / 2)

`task01` (`bike-packing`):

| Run | Reward | J | F | n_frames | n_instances | Wall |
|---|---:|---:|---:|---:|---:|---|
| solve.sh reference (copy first_mask to all frames) | 0.485 | 0.433 | 0.538 | 50 | 2 | 1m 31s |
| claude-code + claude-sonnet-4-6 | **0.466** | 0.483 | 0.450 | 50 | 2 | 16m 43s |

Interesting tradeoff: claude-code improved Jaccard (0.43 → 0.48 — better region overlap) but lost boundary precision (F 0.54 → 0.45), netting roughly the same composite. Real signal for the GPU-vs-CPU gap on this task.

Without SAM 2 / XMem (GPU-class), agents must propagate masks via optical flow or template matching — modest performance.

### `gopro-deblur` (motion deblur — paired video frames)

`scripts/generate_gopro_deblur.py`. Source: `snah/GOPRO_Large` HF mirror (CC-BY-4.0, 9.5 GB direct ZIP download — the HF dataset viewer is broken, but file-resolve works). 11 test sequences sliced to first 30 frames each. Judge: per-frame PSNR + SSIM on the Y-channel (BT.601), averaged across the sequence.

  reward = 0.5 · clip01((PSNR_db - 15)/25) + 0.5 · clip01(SSIM)

`task01` (`GOPR0384_11_00`):

| Run | Reward | PSNR (dB) | SSIM | n_frames | Wall |
|---|---:|---:|---:|---:|---|
| solve.sh reference (passthrough — copy blur frames) | 0.627 | 26.2 | 0.805 | 30 | 36s |
| claude-code + claude-sonnet-4-6 | **0.482** | 22.1 | 0.681 | 30 | 41m 39s |

claude-code path: pip-installed `opencv-python + scikit-image`, then iteratively built 4 versions of a `deblur.py` script implementing **blind PSF estimation via grid search + Richardson-Lucy deconvolution** from `skimage.restoration`. It produced 30 deblurred frames but the deconvolution introduced **ringing artifacts** that hurt PSNR (-4 dB vs passthrough) and SSIM (-0.12) — net reward dropped below the passthrough baseline.

**Real benchmark signal** — same failure mode as `disfluency-clean` row 2 (over-aggressive cleaning). The 0.63 passthrough is genuinely hard to beat without an ML deblurrer; classical CPU-only deconvolution typically introduces more error than it removes. Real ML deblurrers (MIMO-UNet, EDVR) reach ~0.85+ but need GPU.

**Path correction from the playbook:** the zip actually extracts to `train/<SEQ>/{blur,blur_gamma,sharp}/` and `test/<SEQ>/{blur,blur_gamma,sharp}/` — no top-level `GOPRO_Large/` directory. Confirmed by direct inspection.

## Open finding — DisfluencySpeech judge could be more lenient

Current judge scores only against `transcript_b` (medium clean). The dataset provides three levels (a / b / c). A model matching `transcript_c` (heavily cleaned) gets penalized for "over-removal." Future v2: score against `min(WER(a), WER(b), WER(c))` to give partial credit for any reasonable cleaning level.

## Audio repair benchmarks (Tier 1 candidates)

| Benchmark | HF mirror | Per-instance | Metric | Difficulty | Notes |
|---|---|---|---|---|---|
| **DNS Challenge 2020 (synthetic)** | `nkdem/DNS-Challenge-2020-DevTest-16k` (CC-BY-4.0) | ~600 KB paired WAVs | PESQ-wb + STOI + SI-SDR | **EASY ✓ done** | 300 paired instances. pesq needs gcc in image (no manylinux wheel). |
| VoiceBank-DEMAND | `JacobLinCool/VoiceBank-DEMAND-16k` (CC-BY-4.0) | ~80 KB | PESQ + STOI + CSIG/CBAK/COVL + SI-SDR | EASY | Second axis if we want another denoise dataset. 824 test rows. |
| PodcastFillers (filler detection) | `ylacombe/podcast_fillers_processed` (audio CC-BY) | varies | event-based F1 via `sed_eval` | MED | **Annotations are CC-BY-NC** — license blocker for productized use. |
| DNS Challenge real_recordings | same dataset, real_recordings split | similar | none (no clean ref) | SKIP | 300 rows but no GT — useless for our deterministic judge. |
| URGENT Challenge 2024/2025 | none on HF, Google Drive only | unknown | composite (DNSMOS+NISQA+PESQ+STOI+SDR+MCD+SpkSim+WAcc) | HARD | Multi-condition + neural metrics. Heavy. |
| SEP-28K | none; audio per-clip from SoundCloud | 3s/clip + URL rot | per-class F1 | HARD | Audio fetch is fragile. |

## Video repair benchmarks (paired-data candidates)

| Benchmark | HF mirror | Per-instance | Metric | Difficulty | Notes |
|---|---|---|---|---|---|
| **DAVIS 2017 (val)** | none on HF; ETH zip | ~10 MB (sliced per-seq) | J&F via `davis2017-evaluation` (pure NumPy) | EASY (judge) / HARD (agent) | 30 seqs, BSD. Agent needs SAM 2 (GPU) for a real attempt — bad fit for CPU sandbox. |
| GoPro (motion blur) | `snah/GOPRO_Large` (CC-BY-4.0) | ~30 MB/clip | PSNR/SSIM via scikit-image | EASY | 3214 paired sharp/blur. Frame-level CPU judge fine. |
| Vimeo-90K triplets | `danjacobellis/vimeo90k_triplet` | ~200 KB | PSNR/SSIM | EASY | Frame interpolation. Tiny per-instance. |
| REDS | `snah/REDS` | 100–300 MB/seq | PSNR/SSIM | MED | Per-seq slice is borderline 200 MB cap. |
| MIT-Adobe FiveK | none on HF | ~10 MB DNG | PSNR/SSIM/Delta-E | MED | Image (not video). Dual Adobe+MIT license, per-image. |
| DIV4K-50 | `YSZuo/DIV4K-50` (Apache-2.0) | 4K HQ ~10–20 MB | PSNR/SSIM at 4K | MED | Heavier I/O; 4K SSIM ~5s. |
| VPBench | `TencentARC/VPBench` | manifest + clip refs | masked-region PSNR/SSIM + CLIP/FVD | MED | FVD needs GPU; masked PSNR is fine on CPU. |
| YouTube-VOS | none clean | GB-scale | J&F | HARD | Google Drive only; eval portal moved. |

## Existing video-agent-runner task6 — port assessment

Port path is real but heavier than task5_4 (~3–4×). Specifics in the live agent report; load-bearing points:

- **Materials small**: 22 instances × ~30 MB broken.mp4 each. Well under 200 MB cap.
- **Judge is pure-Python deterministic** (no LLM, no GPU): scipy + scikit-image + opencv + ffmpeg, ~2.5k LOC of vendored kit (`verifiers/video_repair_v3/lib/`) + per-cell `profile.json` GT.
- **Convention break**: oracle can't hit ≈ 1.0 because the rollout sandbox lacks access to the clean reference. Same convention break we now have in DNS.
- **Verifier timeout**: 45 min for 1080p whole-video SSIM+xcorr — bump `[steps.verifier] timeout_sec` from 600 to 2700.
- **Privacy invariant**: `verifier_reference_urls` must not leak into the agent's view. Plumb through env var the agent can't see, fetch in `test.sh` only.

Recommendation: port task6 *after* settling on a hosting strategy for per-instance binaries (see "Open question" below), since task6's broken.mp4 are ~10× the size of DNS WAVs and we'd otherwise repeat the gitignore-vs-LFS choice.

## Repair-tool local install smoke (macOS arm64, Python 3.12)

What we'd consider baking into a future Dockerfile vs. invoking from solve.sh:

| Tool | Install OK locally | CPU-runnable | Notes |
|---|---|---|---|
| `silero-vad` | ✓ | ✓ | Pulls torch 2.11 (~400 MB). Pin torchaudio<2.9 or add torchcodec. |
| `openai-whisper` | ✓ | ✓ | `tiny` model = 72 MB; works for filler-detection adjuncts. |
| `whisper-timestamped` | ✓ | ✓ | AGPL — flag for license review. |
| `opencolorio` (`PyOpenColorIO`) | ✓ | ✓ | 20 MB wheel, no torch dep. Drop-in. |
| `noisereduce` | ✓ (in this DNS task) | ✓ | Spectral gating. Real reference solver for DNS, ~10 MB pure-Python. |
| `deepfilternet` | ✗ on macOS arm (no wheel + no cargo) | ✓ in Linux Docker | manylinux wheel exists for `deepfilterlib==0.5.6`. Try inside container, not on host. |
| `ProPainter` / SAM 2 / LatentSync | ✗ practical | needs GPU | Skip until we wire GPU sandboxes. |
| `pesq` | ✓ on Mac (clang) | ✓ in Linux Docker | **sdist-only on PyPI** — needs gcc + python3-dev in image. Baked into `dns-denoise` Dockerfile. |

## Architectural pointers (4KAgent / AgenticIR)

The playbook recommends forking 4KAgent's Profile Module pattern (per-tool JSON registry) and AgenticIR's offline tool-sequence search + distilled heuristics. Both are nice-to-haves once we have ≥2 repair families running — defer until DNS scales and task6 lands.

## Open question — per-instance hosting strategy

For DNS, materials are tiny (~600 KB) so vendoring 300 × ~600 KB = ~180 MB into git is borderline. Options as we scale:

1. **Gitignore + regen** (current default for DNS): `.gitignore` excludes `tasks/dns-denoise-task*/steps/solve/workdir/noisy.wav` + `tests/clean.wav`. Users run `python scripts/generate_dns_denoise.py --overwrite` to rebuild. Pros: zero binary in git, clean diffs. Cons: requires the upstream HF dataset to stay live.
2. **HF dataset under our namespace**: push extracted per-instance zips to `PhiloLabs/agentic-vbench-dns-materials`, then `setup.sh` curls per-instance like task5_4. Pros: portable, no regen step. Cons: requires HF write token + ongoing hosting.
3. **Git LFS**: track WAVs as LFS. Pros: clone-and-run. Cons: LFS bandwidth costs + LFS gotchas.

Current default is (1). Switch to (2) once we're sure DNS is the keeper and want clone-and-run UX.

## What to integrate next (priority order, updated)

After v2 sweep — DNS + VoiceBank + DisfluencySpeech all integrated and smoke-green:

1. **Scale the three integrated families to Modal** — pick the cheapest one (`disfluency-clean` test split is 250 rows) and run a `--n-concurrent 30` sweep to get baseline reward distributions across instances. Budget ~$5–15 total.
2. **GoPro deblur** — flagged as NEEDS-WORK after research: the playbook's `snah/GOPRO_Large` HF mirror is broken (dataset viewer 500, parquet job failed). Working alternative is `HanzhouLiu/GoPro_Deblur` (webdataset, 5.1 GB, no license tag). A=blur/B=sharp convention is an assumption that needs visual verification on one frame. Sliced 30-frame sub-sequences (~30 MB/task × ~33 tasks).
3. **MS-SNSD** — Microsoft Scalable Noisy Speech, MIT code + CC/ODbL data. On-demand synthesis (one Python script generates the corpus at configurable SNR). Reuses DNS judge exactly. Adds controlled-SNR sweeps the other two families don't have.
4. **AMI-Disfluency** — Apache 2.0 by tag, but the HF dataset card is **gated** (401 even on dataset_structure). Defer pending HF auth + access request.
5. **Port task6** — closes the four-family loop with the upstream video benchmark. ~3-4× task5_4 effort; scipy/cv2/skimage in judge image; 45-min verifier timeout.

DAVIS inpainting / SR / lip-sync / 4K are all GPU-gated — punt until GPU sandbox config is wired.

## Playbook corrections from this round

- VoiceBank-DEMAND mirror license: playbook said "Edinburgh EUL (research-only)" → actually **CC-BY-4.0** on `JacobLinCool/VoiceBank-DEMAND-16k`. The original Edinburgh DataShare ZIP is EUL, but the HF redistribution is CC-BY-4.0.
- VoiceBank-DEMAND noise-type metadata: playbook implied per-row subset tags (cafeteria/bus/etc.) → **not present** in this mirror; the 5 noise types × 4 SNRs are baked into the 824 utterances but not exposed as a column.
- GoPro HF mirror: playbook said `snah/GOPRO_Large` → that dataset is **broken** on HF (viewer 500, parquet failed). Working alternative: `HanzhouLiu/GoPro_Deblur`.
- LPIPS auto-download: playbook said "AlexNet ~85 MB" → actual download is **233 MB**.
- DisfluencySpeech judge: playbook recommended `seqeval` for token F1 → not applicable; GT is strings, not BIO tags. Switched to `jiwer.wer` with relative-improvement reward.

## Judge dep readiness (all verified install + CPU smoke on Mac arm64)

| Library | Pin | Notes |
|---|---|---|
| `pesq==0.0.4` | source-only; need `gcc + python3-dev` in image | DNS + VoiceBank |
| `pystoi==0.4.*` | pure-Python | DNS + VoiceBank |
| `jiwer==4.0.0` | pure-Python, pulls `rapidfuzz` | DisfluencySpeech |
| `noisereduce` | pure-Python, ~10 MB | DNS + VoiceBank reference solvers |
| `torchmetrics[image,audio]==1.9.0` | anchor; brings torch (~1 GB venv) | future image-restoration families |
| `pytorch-msssim==1.0.0` | free with torch | future deblur/SR |
| `lpips==0.1.4` | 233 MB AlexNet auto-download | future perceptual judges |
| `seqeval==1.2.2`, `scikit-learn` | both pure-Python | future BIO-tag F1 judges |
| `davis2017-evaluation` | not on PyPI; `pip install git+...` | future segmentation J&F |
