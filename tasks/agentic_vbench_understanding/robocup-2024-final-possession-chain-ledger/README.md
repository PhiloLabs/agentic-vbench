# RoboCup 2024 Final Possession-Chain Ledger

This task reconstructs multi-kick possession chains from the 2024 RoboCup Small
Size League final between TIGERs Mannheim and ZJUNlict. The answer cannot be read
from the score overlay: it requires finding individual ball launches, maintaining
team possession across the match, assigning field-relative zones, and identifying
how each chain ends.

## Public sources

- Match video: <https://www.youtube.com/watch?v=364zEAsOclU>
- Official logs index: <https://ssl.robocup.org/game-logs/>
- Log filename:
  `2024-07-21_11-00_ELIMINATION_PHASE_ZJUNlict-vs-TIGERs_Mannheim.log.gz`

Pinned artifacts:

| artifact | bytes | SHA256 |
|---|---:|---|
| `match.mp4` (YouTube itag 298) | 173,343,080 | `076bcc59fc48443d24a72a87162021470b9e645b41c858c3ffa5b5b25bae36cd` |
| official log | 244,923,080 | `9ceda35082d8b39049de258efbf35934687c525a92324bf9a23ed61b7a3318d0` |

The video is H.264, 1280x720, 50 fps, 14:40.64, with no audio stream. It covers
both halves through the visible 3:0 score at 0:00 while removing some stopped-clock
dead time. The official log subsequently records a 4:0 result after the last visible
live-play stoppage; that post-live score change is not attributed to a video chain.
The Docker build downloads the exact public YouTube representation and verifies its
digest. `MATERIALS_URL` can override the downloader after the same bytes are
re-hosted at a stable direct URL.

## Ground truth

`tools/build_ground_truth.py` parses referee and tracked-vision messages from the
official SSL log. It uses TIGERs' `kicked_ball` tracker output, merges repeated
tracker frames and short-lived identity jitter, retains live-play kicks after the
first goal, and derives maximal same-team chains. The generated answer key is kept
verifier-side in `steps/solve/tests/ground_truth.json`.

Rebuild it in an isolated environment:

```bash
python3 -m venv /tmp/robocup-gt
/tmp/robocup-gt/bin/pip install -r tools/requirements.txt
/tmp/robocup-gt/bin/python tools/build_ground_truth.py \
  --log /path/to/2024-07-21_11-00_ELIMINATION_PHASE_ZJUNlict-vs-TIGERs_Mannheim.log.gz
```

`tools/ground_truth_audit.json` records the accepted kick times, robot IDs,
positions, speeds, thresholds, and chain derivation for review. It is not copied
into the agent workspace.

## Validation

Run the deterministic scorer tests with:

```bash
python3 tools/test_judge.py
```

Three retained local agent outputs have been scored by the formal verifier:

| harness | reward | tool calls |
|---|---:|---:|
| Codex Desktop (`gpt-5.6-sol`, high) | 0.0 | 163 |
| Claude local agent (`claude-sonnet-5`) | 0.0385 | 46 |
| Antigravity (model metadata unavailable) | 0.0 | 176 |

See `calibration/scores.md` for diagnostics and counting rules. These are the final
results reported by this submission. The runs were outside the shipped Harbor image,
and no measured anti-shortcut ablation results are claimed.
