# Raw calibration trajectories

Keep one complete raw trajectory per calibrated agent, including every tool call and
the final answer — summaries cannot be audited.

Expected filenames, matching the table in `../scores.md`:

- `codex-gpt-5.6-sol.jsonl` — Harbor ATIF trajectory serialized as one JSON record per
  line (session metadata, 82 trajectory steps, and final metrics)
- `claude-opus-4.8.jsonl.gz.part-aa` and `.part-ab` — lossless split gzip of the
  Claude Code CLI stream-json; reconstruct with
  `cat claude-opus-4.8.jsonl.gz.part-* | gzip -dc > /tmp/claude-opus-4.8.jsonl`

Redact personal home paths deterministically, replacing path strings only; do not
drop events, tool inputs, tool results, or model messages. Keep the submitted solution
and verifier reward beside each trajectory so the recorded score is reproducible.
Split compressed trajectories only when the unsplit artifact exceeds GitHub's per-file
size limit.
