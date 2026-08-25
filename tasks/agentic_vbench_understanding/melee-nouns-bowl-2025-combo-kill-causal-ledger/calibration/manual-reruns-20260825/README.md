# Manual Rerun Templates

These are clean full-baseline workspaces for manually rerunning the Claude app
and Antigravity.app. They do not reuse the historical folders in
`/Users/zsj/Documents/melee-nouns-bowl-claude` or
`/Users/zsj/Documents/melee-nouns-bowl-antigravity`.

Both templates contain the unmodified solve instruction, SHA256
`911e5db8cefdff943ba7e411e1e3ee74253abf132e3e4fa78af57c4c0c863caf`.
Their `prepare.sh` scripts verify the only allowed video input before copying it
into a fresh, ignored `run/` directory.

Use the documented source media path when available:

```sh
/Users/zsj/Documents/agentvbench/materials/source/melee-nouns-bowl-2025/match.mp4
```

It must have SHA256
`02f18fd7f4796800eece0400b1b1f315a36778b57b9ef4a64d1b30aa3b539749`.

The run directory intentionally contains only `instruction.md`,
`materials/match.mp4`, `work/`, `output/`, and `logs/`. Do not place replay
files, web exports, source VOD segments, prior solutions, or ground truth there.

After each manual run, execute that template's `capture.sh`. It validates the
solution with the task scorer and writes an input/runner manifest. Record a
short explanation of the harness's actual egress policy in
`run/logs/network-policy.md` before capture; it is required evidence for a
reproducible claim.

## Full-Baseline Handoffs

For an orchestration agent that should research infrastructure and then execute one
isolated, single-agent full-baseline attempt, use one of these complete handoffs.
They prohibit video-analysis subagents and model delegation during the formal run:

- `claude-code/APP_HANDOFF.md` for Claude Code;
- `antigravity/APP_HANDOFF.md` for Antigravity.app.

For the Claude app, the app itself does not write into this directory. Attach
only `run/materials/match.mp4` to a new, empty chat; paste the exact contents of
`run/instruction.md`; then save the JSON object from its final response as
`run/output/solution.json`. For Antigravity.app, give the app only the prepared
`run/` directory as its local workspace.
