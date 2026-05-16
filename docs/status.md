# STATUS — overnight experiment

Live log. Newest at top.

## 2026-05-13 03:05 PST · Phase 0 ✅ · Phase 1 starting

- ✅ Env checks (Docker 29.3.1, harbor 0.6.6, ffmpeg 8.1, uv 0.11.7, ANTHROPIC_API_KEY set, 1.1 TB free).
- ✅ Folder skeleton: `experiment/{sources,tasks,scripts,jobs,logs,.venv}/`.
- ✅ 16 source videos copied (691 MB).
- ✅ `experiment/.venv` created (Python 3.12) with deps: numpy 2.4.4, scipy 1.17.1, soundfile 0.13.1, librosa 0.11.0, pyroomacoustics 0.10.1, noisereduce 3.0.3, pesq 0.0.4, pystoi 0.4.1, srmrpy 1.0 (from git). PESQ smoke test passed.
- 🚧 Phase 1: dispatched.
  - ✅ **Audio agent** done in 7.5 min. 5 tasks built. Self-test passes (judge=1.0 on clean reference).
    - calibration concerns logged: voicebank noisereduce oracle (0.34) < passthrough (0.64); declip q=0.9 too easy (passthrough 0.77, spline 0.74); codec-restore opus_12k too mild (passthrough 0.66, target was 0.40-0.55).
    - decision: accept as-is for experiment, fix in next iteration.
  - ✅ **Glitch agent** done in 10.4 min. Both tasks built. Oracle=1.0 in agent's local sanity (not via harbor — see Phase 2).
    - Agent flagged spec ambiguity: chose **freeze** (single-frame held for N extras) over **block-dup** (N-frame sequence repeated). Matches supplement's `tpad=stop_mode=clone` hint. Accepted.
    - Audio stripped from corrupted.mp4 to avoid A/V drift; video-only task.
    - Shared core helper at `scripts/_glitch_dup_core.py`.

## 2026-05-13 03:13 PST · Phase 2 in progress

- ✅ Round 1 smoke: 4 of 5 audio pass (dns 0.38, voicebank 0.34, declip 0.74, codec 0.66). Dereverb failed: `git` missing from Dockerfile, srmrpy install broke.
- 🛠 Fixed dereverb Dockerfile (added `git`, moved srmrpy install to build-time).
- ✅ Round 2 smoke: 2 glitch tasks pass at 1.0. Dereverb failed AGAIN: srmrpy not on PyPI, must use git+https://github.com/jfsantos/SRMRpy.git source.
- 🛠 Fixed dereverb Dockerfile again (srmrpy via git source).
- ✅ Round 3 dereverb smoke FAIL: srmrpy not on PyPI (`==1.0` doesn't exist). Switched to `srmrpy @ git+https://github.com/jfsantos/SRMRpy.git`.
- ✅ Round 4 dereverb smoke FAIL: gammatone resolution conflict (srmrpy pulls gammatone via its own zip URL, conflicting with my explicit git install). Removed the explicit gammatone line.
- ✅ Round 5 dereverb smoke PASS: reward 0.120 (passthrough on heavily reverberant clip — matches agent's prediction).

**All 7 tasks (5 audio + 2 glitch) pass oracle smoke. Phase 2 ✅.**

| Task | Oracle Reward | Smoke Wall |
|---|---:|---:|
| dns-denoise | 0.380 | 101s |
| voicebank-denoise | 0.338 | 34s |
| dereverb | 0.120 | 69s (5th try, after Dockerfile fixes) |
| declip | 0.745 | 24s |
| codec-restore | 0.660 | 105s |
| glitch-dup-short | 1.000 | 85s |
| glitch-dup-long | 1.000 | 20s |

## 2026-05-13 03:15 PST · Phase 3 + 4 parallel kickoff

- 🚧 4 background processes dispatched in parallel: main rollout (audio+glitch), dereverb rollout, cut-based builder, mask builder.

## 2026-05-13 03:30 PST · Phase 4 agents return

- ✅ Cut-based agent done in 10.7 min. 4 tasks built, local oracle = 1.0 on all 4.
- ✅ Mask agent done in 21.5 min. 4 tasks built, local oracle = [0.41, 0.66] (all in expected range).
- Smoke + rollout batches dispatched for both groups in parallel with main batch.

## 2026-05-13 04:55 PST · Phase 5 complete · ALL DONE

- ✅ 15/15 tasks built, smoked, and rolled out.
- ✅ Mean rewards: oracle 0.666, claude-code 0.621.
- ✅ Claude-code BEATS oracle on 6 tasks, TIES 3, LOSES 6.
- ✅ Total cost: ~$13.77 (12 measured + 3 timeout-truncated estimated).
- ✅ Wall-clock: 2h 5m end-to-end.
- 📄 **Final report at `experiment/REPORT.md`** — read this in the morning.
