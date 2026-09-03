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

The scorer first aligns predictions to ground truth in chronological order. A pair
can earn credit only after `half` and `team` agree. An exact remaining tuple earns
`1.0`; otherwise exact/off-by-one `kick_count` earns `0.25`/`0.125`, and an
exact/edit-distance-one `zone_path` earns `0.25`/`0.125`. Partial credit is capped
at `0.5`; `terminal`, `team`, and `half` have no standalone partial value. The final
reward is weighted event-level F1, and invalid or duplicate submitted entries remain
in the prediction denominator.

Four deterministic panels under `calibration/contact-evidence/` show consecutive
native 720p50 frames around three first-half contacts and one second-half launch.
They establish that ball approach, contact/occlusion, reversal, and free-flight
separation resolve in the supplied pixels.

The earlier local runs were removed as superseded diagnostics. They predate the
final scorer and were not executed in the pinned isolated environment, so they do
not qualify the task. The required clean pass is:

1. GPT-5.6 Sol end to end, plus no-media, single-frame, OCR-only, and every-native-frame/no-tools ablations.
2. Fable 5 or Opus 4.8 end to end on the unchanged task.
3. Gemini 3.1 Pro or 3.5 Flash end to end on the unchanged task.

See `calibration/scores.md` for the qualification table and
`calibration/ablations/README.md` for exact degraded-input definitions. Raw final
trajectories are published as fork release assets; their whole-file SHA256 values,
harness versions, image ID, task commit, and tool-call record types are recorded in
the score table. `tools/scrub_trajectory.py` makes any required path/payload
redactions reproducible. `calibration/RUNBOOK.md` contains the exact Harbor commands
for all three end-to-end agents.
