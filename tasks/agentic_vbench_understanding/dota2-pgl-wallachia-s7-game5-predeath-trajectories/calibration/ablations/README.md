# Anti-shortcut ablation artifacts

These are measured GPT-5.6 Sol high-reasoning runs under Harbor 0.20.0, not
simulated submissions.

| artifact | degraded input | retained output |
|---|---|---|
| `single-frame-codex-high.jsonl` | One source frame at the 1557.5-second temporal midpoint; full video removed before the agent step | The model abstained and wrote no solution |
| `frame-dump-no-tools-codex-high.jsonl` | All 93,450 native 30-fps frames in 78 chronological contact sheets; full video removed and every model tool disabled | `frame-dump-no-tools-codex-high.solution.json` |

The single-frame run used the normal Codex Harbor adapter and made nine tool calls.
`single-frame.media-probe.json` confirms that its MP4 contained one decoded frame.
The verifier treated the missing solution as an empty prediction and scored it
`0.0000`.

The frame-dump setup placed 1,200 consecutive frames in each 40-by-30 sheet. Every
64-by-36 cell is labeled with its global source-frame number `F`; its time is
`F / 30` seconds. The final sheet contains frames through `F93449` followed only by
black padding. `frame-dump-no-tools.media-probe.json` records the source-frame and
sheet counts. Shell, unified execution, apps, browser/computer use, plugins,
multi-agent, goals, image generation, and every other model tool were disabled.
The transcript contains zero function calls. The model submitted 30 schema-valid
events and scored `0.0000`.

Image bodies and encrypted reasoning blobs are replaced in both JSONL transcripts
with length-and-SHA256 placeholders. All model messages and event metadata remain
intact. The sanitized transcript SHA256 values are:

- `single-frame-codex-high.jsonl`:
  `d44283c2e884beb51b5835dc5069b96a3ced296409dd86383e5d6067ea6e7e80`
- `frame-dump-no-tools-codex-high.jsonl`:
  `63d54b3698e96fd7800041635d6e55b8a8b6247f67d47e858bfa64d8777fc7de`
