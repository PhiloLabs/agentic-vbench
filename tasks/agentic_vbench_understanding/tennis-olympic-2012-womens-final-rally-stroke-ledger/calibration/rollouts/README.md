# Rollouts

One raw agent transcript per calibrated harness, kept so a reviewer can audit the run
rather than trust a summary. See `../scores.md` for results and remaining runs.

Expected files once calibration runs:

| file | harness |
|---|---|
| `codex-gpt-5.6-sol.jsonl` | Codex CLI |
| `claude-opus-4.8.jsonl` | Claude Code CLI |
| `antigravity-gemini-3.5-flash.log` | Antigravity |

Alongside each transcript, keep the graded `.solution.json` and `.reward.json` the trial
produced. Audit each trajectory for web lookups and for recall of the match before
trusting its score: the instruction forbids both.

The Codex transcript was copied byte-for-byte from the CLI session rollout. It contains
no web lookup, and a credential-pattern scan found no credential value. Its paired
solution and reward files are the artifacts graded by the same Harbor trial.
