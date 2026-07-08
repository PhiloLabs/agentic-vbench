# Antigravity Local Calibration

- Agent: Antigravity CLI
- Language server version reported by CLI: 1.1.0
- Model reported by CLI log: Gemini 3.5 Flash (Medium)
- Conversation id: fd49a004-8d8d-4619-afc5-e7b35b523b3a
- Command mode: `agy --print "$(cat instruction.md)" --print-timeout 4h --mode accept-edits --sandbox --dangerously-skip-permissions --add-dir ... --log-file ...`
- Result: no `output/solution.json` submitted before cutoff
- Printed action-step count at stop: 60
- Scoring input: `harness_missing_solution.json`
- Reward: 0.0

Notes:
- The run was stopped after crossing the 50 action-step calibration cutoff.
- `antigravity-cli-log.txt` contains the detailed CLI log.
- Antigravity used the globally installed `whisper-cli` and downloaded `ggml-base.en.bin` into `work`.
- The run inspected Homebrew/system paths and used network for model download, so it should be treated as locally useful calibration evidence rather than a fully sandbox-clean run.
