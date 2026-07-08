# Calibration - council-meeting-rollcall-vote-timeline

Deterministic JSON scorer (`steps/solve/tests/judge.py`). A task clears the bar when
oracle scores 1.0, an empty/null attempt scores no more than 0.10, every real strong
agent scores below 0.10, and real attempts take more than 50 tool-call turns.

| run | score | rollout (tool-call turns) |
|---|---:|---:|
| oracle, Harbor Modal job `avb-council-meeting-rollcall-vote-timeline-1783484291` | 1.0 | - |
| empty / null, Harbor Modal `nop` job `avb-council-meeting-rollcall-vote-timeline-1783484440` | 0.0 | - |
| Antigravity CLI local, conversation `fd49a004-8d8d-4619-afc5-e7b35b523b3a` | 0.0 | 60 |
| Codex CLI local, session `019f402a-96d5-73a3-90d3-2940e60e5852` | 0.0 | 52 |
| Claude Code CLI local, session `286d6f32-09e1-4757-8e6b-3ab1ace57363` | 0.0 | 51 |

Raw transcripts should be added under `rollouts/` before submission review.

Oracle and empty/null scores above were measured with Harbor on Modal. Local
strong-agent calibration has been run for Codex CLI, Claude Code CLI, and
Antigravity CLI.

Input validation passed with the 720p Archive.org original:
`Issaquah_City_Council_Regular_Meeting_-_December_6_2021.HD.mov?download=1`.

Local shortcut smoke checks against the verifier:

| synthetic shortcut | score |
|---|---:|
| agenda IDs only, no vote times or motion types | 0.0 |
| all votes guessed unanimous, no vote times or motion types | 0.0 |
