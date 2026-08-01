# Outstanding anti-shortcut measurements

The supplied calibration directory contains full-media runs for Codex CLI, Claude
Code, and a Gemini CLI fallback. It does not contain the required degraded-input
runs. Do not replace these rows with estimates: each must be an actual strong-model
trajectory scored by `steps/solve/tests/judge.py`.

| ablation | required evidence | status |
|---|---|---|
| single representative frame | trajectory and reward JSON | pending |
| no media | trajectory and reward JSON | pending |
| all frames pasted, no tools | trajectory and reward JSON | pending |

Audio is not required by the task, so the video-only and audio-only ablations do not
apply. Final acceptance also requires a native Antigravity run or explicit maintainer
approval of the existing Gemini CLI fallback.
