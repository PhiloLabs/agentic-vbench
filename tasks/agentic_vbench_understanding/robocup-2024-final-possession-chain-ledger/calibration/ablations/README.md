---
title: RoboCup calibration ablation protocol
summary: Exact degraded-input conditions required for the clean Codex calibration pass.
read_when: Running or reviewing anti-shortcut calibration for this task.
---

# Ablation protocol

All ablations must use the final checked-in instruction, verifier, pinned image, and
GPT-5.6 Sol with the same reasoning setting as the clean end-to-end Codex run. They
are model runs, not hand-built submissions. Record the image ID, task commit, Harbor
version, harness version, model identifier, whole-file trajectory SHA256, output,
and verifier details for every condition.

| condition | exact degraded input | tools |
|---|---|---|
| no media | Remove both `/workspace/materials/match.mp4` and `/baked/match.mp4`; retain the unchanged instruction and schema. | Normal Codex tools. |
| single frame | Replace `match.mp4` with a one-frame 1280-by-720 video containing temporal-midpoint frame F22016 (440.32 s); remove the full video everywhere. | Normal Codex tools. |
| OCR only | Supply UTF-8 text from OCR over every fifth-second frame, ordered by timestamp; remove all pixels and the full video. The OCR engine may emit only text and bounding boxes, not object detections. | Normal Codex tools over the text artifact only. |
| all native frames, no tools | Remove the MP4 and paste all 44,032 native frames chronologically into labeled contact sheets. Each cell is labeled with global frame `F`, whose PTS is `F / 50` seconds. | Disable every model tool and subagent capability. |

The source is silent, so video-only is the full task rather than a degraded
condition, and audio-only is not applicable. Each measured reward must be at most
`0.15`; null and high-volume spam probes remain scorer regression tests and should
stay near zero.

For the all-frame condition, use enough sheets to include every frame without
temporal subsampling. Record the decoded frame count and sheet geometry alongside
the trajectory. Do not describe a uniformly sampled frame set as the all-frame
ablation.
