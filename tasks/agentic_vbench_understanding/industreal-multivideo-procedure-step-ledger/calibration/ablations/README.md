# Anti-shortcut ablation artifacts

These are measured strong-model runs, not simulated submissions.

| artifact | degraded input | retained output |
|---|---|---|
| `no-media-codex-high.jsonl` | Zero-byte placeholders for all task media | No solution file was produced |
| `single-frame-codex-high.jsonl` | One temporal-midpoint frame per A--G MP4; reference PDF retained | `single-frame-codex-high.solution.json` |
| `frame-dump-no-tools-codex-high.jsonl` | Every native 10 fps frame in chronological 20-second contact sheets; reference pages attached | `frame-dump-no-tools-codex-high.solution.json` |

The first two runs used the normal Codex Harbor adapter. The frame-dump run disabled
shell, unified execution, apps, browser/computer use, plugins, multi-agent, goals,
image generation, and every other model tool. The transcript contains zero tool-call
events.

As with the end-to-end rollout, image bodies and encrypted reasoning blobs are elided
from the JSONL with length-and-SHA256 placeholders. All model messages and tool-event
metadata remain intact.
