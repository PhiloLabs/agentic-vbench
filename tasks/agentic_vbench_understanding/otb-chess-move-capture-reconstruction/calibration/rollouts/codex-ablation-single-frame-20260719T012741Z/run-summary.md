# Codex Single-Frame Ablation Summary

- Agent: Codex CLI 0.144.0-alpha.4, GPT-5.6 Sol, high reasoning
- Run id: `codex-ablation-single-frame-20260719T012741Z`
- Session: fresh ephemeral local workspace
- Input variant: one representative 1280x720 frame from `00:13:00` of the replacement-source video; no other frames or video were available
- Reward: `0.0058` (`2/343` checks passed; ablation threshold is `<= 0.15`)
- Submission: `unknown` result, 50 predicted plies, and 8 predicted captures
- Passed checks: move identity for `1.e4` and `1...e5`; no timestamp, capture, or result checks passed
- Tool count: 15 completed shell-command records, including 2 failed commands

The model inferred a legal-looking history from the visible middlegame position,
but the still did not reveal the actual timeline. This ablation passes the
anti-shortcut gate.
