# Scorer-number readability evidence (review comment #2)

Goal-moment frames pulled from the **shipped masked video**
(`materials/game.mp4`, SHA-256 `7e53fe…`) at the exact baked **1280×720**
resolution — no upscaling. Each shows the scorer's jersey number reading
cleanly **above the mask line** (the black band is the masked lower third),
and each matches the graded scorer in `steps/solve/tests/ground_truth.json`.

| file | goal | team | scorer # | video time | what reads |
|---|---|---|---:|---:|---|
| `goal14_WHITE_34.png` | 14 | WHITE (Johns Hopkins) | 34 | ~2812.5 s | back number **34** |
| `goal19_WHITE_09.png` | 19 | WHITE (Johns Hopkins) | 9  | ~4355 s   | back number **9** |
| `goal24_NAVY_19.png`  | 24 | NAVY (Michigan)       | 19 | ~5456.75 s| **MICHIGAN 19** (goalie 40 also visible) |
| `goal26_NAVY_40.png`  | 26 | NAVY (Michigan)       | 40 | ~5461 s   | **MICHIGAN 40** (goalie; TIERNAN nameplate) |

These four are the second-half direct reads. The full oracle audit
(`calibration/scores.md`) certified **26/26** scorers readable on this masked
encode: 24 direct reads plus the two coast-to-coast goalie goals (15, 26) via a
documented identity chain. Numbers sit above the masked band throughout, so the
masking that removes the score anchors does not clip the numbers the oracle
needs.
