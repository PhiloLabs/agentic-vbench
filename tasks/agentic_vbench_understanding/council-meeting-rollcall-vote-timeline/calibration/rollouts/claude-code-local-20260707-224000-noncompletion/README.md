# Claude Code Local Calibration

- Agent: Claude Code 2.1.204
- Model reported by CLI: claude-sonnet-5
- Session id: 286d6f32-09e1-4757-8e6b-3ab1ace57363
- Command mode: `claude -p "$(cat instruction.md)" --permission-mode bypassPermissions --output-format stream-json --verbose --no-session-persistence`
- Result: no `output/solution.json` submitted before cutoff
- Tool-use count at stop: 51
- Scoring input: `harness_missing_solution.json`
- Reward: 0.0

Notes:
- The run was stopped after crossing the 50 tool-use calibration cutoff.
- Claude Code installed `whisper-cpp` via Homebrew and downloaded `ggml-small.en.bin` under `work/whisper_models` during its attempt, then began transcription from the provided video audio.
- This reached outside the working directory for Homebrew inspection/installation, so the rollout should be treated as locally useful calibration evidence rather than a fully sandbox-clean run.
