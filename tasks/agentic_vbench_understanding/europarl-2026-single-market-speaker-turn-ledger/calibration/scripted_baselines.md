# Scripted shortcut diagnostics

These diagnostics are deterministic scripts, not substitutes for the required
strong-model ablations.

## Full-roster face recognition, video only

OpenCV YuNet detected faces at one frame per second. SFace matched each detected
face against all 79 anonymous portraits. Consecutive observations of the same
identity were grouped into predicted turns without using audio or ground truth.

| boundary tolerance | predicted turns | true positives | F1 |
|---:|---:|---:|---:|
| 15 s | 56 | 37 | 0.521 |
| 5 s | 56 | 15 | 0.211 |
| **4 s (final)** | **56** | **7** | **0.099** |
| 3 s | 56 | 5 | 0.070 |

The sharp failure below five seconds is the measured reason the final task uses a
four-second boundary requirement: portrait matching and camera continuity recover
identity and coarse intervals, but floor audio is required for exact boundaries.

## OCR

The official feed has no speaker-name lower thirds. The pilot OCR diagnostic
sampled 276 lower-frame regions and found zero official speaker names.
