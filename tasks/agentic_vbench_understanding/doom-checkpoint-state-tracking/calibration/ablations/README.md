# Anti-shortcut ablations

These measured runs used Codex CLI 0.146.0 with `gpt-5.6-sol` at xhigh. Each
condition contains the submitted `answer.json` and raw `trajectory.jsonl`;
measured rewards are reported in `../scores.md`.

- `no-media`: task text and schema only.
- `single-frame`: one attached frame sampled at 1100 seconds.
- `frame-dump-no-tools`: 120 attached frames sampled uniformly every 22 seconds;
  the full video and sampling tools were unavailable.

All runs were isolated from the repository, verifier, answer key, and internet.
