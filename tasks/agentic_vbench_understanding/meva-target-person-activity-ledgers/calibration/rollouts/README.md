# Raw trajectories

Required-agent trajectories:

- `codex-gpt-5.6-sol.jsonl`: complete native Codex CLI JSONL.
- `claude-opus-4.8.jsonl`: complete VS Code Claude Agent SDK
  AHP stream for the successful parent turn and all ten nested agent channels.
- `antigravity-gemini-3.6-flash-high.jsonl`: complete native Antigravity CLI
  `stream-json` trajectory.

Degraded-input trajectories, one per required ablation, all GitHub Copilot CLI
1.0.79-9 running GPT-5.6 Sol:

- `ablation-no-media.jsonl`: prompt and schema only, no media.
- `ablation-single-frame.jsonl`: one representative frame only.
- `ablation-frame-dump-no-tools.jsonl`: one-frame-per-second dump with the
  inspection tools withheld.

These files are raw auditable streams, not summaries or reconstructed
transcripts. `calibration/scores.md` links each one with its harness, model,
version, score, and tool-call count.

Two defects in the frame-dump run's own prompt are preserved as-is rather than
edited, since these files are evidence: it says "twelve roster references" where
there are ten, and it contains a literal `\n\n` before a heading. Neither
affected the outcome; the run emitted ledgers for all ten references and no
others.

Personal home paths and task-specific calibration workspace roots are
deterministically redacted. Redaction replaces path strings only; no events,
tool inputs, tool results, or model messages are removed.
