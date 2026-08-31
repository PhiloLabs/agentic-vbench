# Calibration — dota2-pgl-wallachia-s7-game5-predeath-trajectories

These results use the exact checked-in prompt and verifier.

## End-to-end agents

| harness | harness version | model | reasoning | score | predicted | tool calls | runtime | trajectory |
|---|---|---|---|---:|---:|---:|---:|---|
| Oracle | Harbor 0.20.0 | answer key | n/a | 1.0000 | 39 | n/a | 00:18 total | n/a |
| Empty output | Harbor 0.20.0 | n/a | n/a | 0.0000 | 0 | n/a | 00:17 total | n/a |
| Codex | Harbor 0.20.0 | GPT-5.6 Sol | high | 0.0000 | 38 | 195 | 37:00 agent | `rollouts/codex.jsonl` |
| Claude Code | Harbor 0.20.0 / Claude Code 2.1.219 | Claude Opus 4.8 | xhigh | 0.0256 | 39 | 762 | 3:58:26 total | `rollouts/claude-code-opus-4.8-xhigh.jsonl` |
| Antigravity | Harbor 0.20.0 / Antigravity CLI 1.1.8 | Gemini 3.5 Flash | high | 0.0000 | 18 | 137 | 17:39 total | `rollouts/antigravity-gemini-3.5-flash-high.jsonl` |

The verifier also has an identity-only regression probe: all 39 public
clock/victim/killer tuples are correct, while all three schema-valid cells are
deliberately wrong. Killer attribution is `1.0000`, but exact-trajectory reward is
`0.0000`. Public identity fields therefore cannot earn partial reward above the
null baseline.

The oracle and empty-output anchors were rerun after finalizing the three-tick
position sampling. The Codex row is a fresh clean exact-prompt run on 2026-07-24.
It submitted 38 schema-valid events. Thirty-three matched a GT clock within two
seconds with the correct victim and killer; five corresponding identity tuples
were outside the clock tolerance, and one GT death was omitted. It did not recover
any complete three-point trajectory exactly.

The Claude row is the subsequent clean exact-prompt run on 2026-07-24. It completed
without an exception and passed the output gate. All 39 submitted events were
schema-valid and matched the GT clock, victim, and killer, while one complete
three-cell trajectory was exact. The normalized ATIF recorded 762 tool calls across
the main session and 11 Claude-created subagents. The total runtime includes a
rate-limit wait that Claude Code's retry watchdog handled within the same session;
the transcript records zero web searches or fetches.

The Antigravity row is the clean exact-prompt run on 2026-07-28. It completed
without a Harbor exception, passed the output and raw-trajectory gates, and retained
the full native transcript. All 18 submitted events were schema-valid. Four matched
a GT clock within two seconds, but none matched the corresponding victim, killer,
or complete three-cell trajectory.

| diagnostic | Codex matches | Codex F1 | Claude matches | Claude F1 | Gemini matches | Gemini F1 |
|---|---:|---:|---:|---:|---:|---:|
| Event localization | 33 | 0.8571 | 39 | 1.0000 | 4 | 0.1404 |
| Victim attribution | 33 | 0.8571 | 39 | 1.0000 | 0 | 0.0000 |
| Killer attribution | 33 | 0.8571 | 39 | 1.0000 | 0 | 0.0000 |
| Cell at death minus 10 seconds | 3 | 0.0779 | 1 | 0.0256 | 0 | 0.0000 |
| Cell at death minus 5 seconds | 5 | 0.1299 | 4 | 0.1026 | 0 | 0.0000 |
| Cell at death | 8 | 0.2078 | 6 | 0.1538 | 0 | 0.0000 |
| Three cells each within one grid step | 19 | 0.4935 | 15 | 0.3846 | 0 | 0.0000 |
| Exact three-cell trajectory, scored reward | 0 | 0.0000 | 1 | 0.0256 | 0 | 0.0000 |

This leaves a concrete margin below the `0.10` difficulty gate. With the observed
38 predictions against 39 expected events, three exact trajectories would score
`0.0779`; at least four would be required to exceed `0.10`. A local verifier stress
probe that copied each predicted death cell into both earlier time points scored
only `0.0519`, so treating every trajectory as stationary is not an effective
shortcut.

The raw trajectory shows the primary spatial failure. Codex inferred a
`192x192` minimap crop beginning at `(0, 528)` instead of isolating the audited
`182x182` square at `(6, 537)`, then quantized markers against that shifted frame.
For m1CKe at `05:26`, it reported `D11 -> E11 -> E10` while GT is
`D11 -> D10 -> D10`. For Nisha at `10:38`, it reported
`G7 -> H5 -> I4` while GT is `I4 -> I4 -> I5`. These are evaluated as model
outputs, not corrected during scoring.

Claude solved the event-indexing layer but remained imprecise on the minimap. For
Boxi at `11:34`, it reported `F7 -> E7 -> F8` while GT is
`G6 -> F6 -> F7`. For Malady at `22:57`, it reported
`I5 -> I4 -> I3` while GT is the stationary trajectory
`I3 -> I3 -> I3`.

Gemini struggled earlier in the pipeline: it recovered only 18 of 39 expected
events, and most reported clocks were outside the two-second tolerance. At its
predicted `05:24`, it reported Boxi killed by watson with
`E8 -> E8 -> F8`; the nearby GT event at `05:26` is m1CKe killed by DM with
`D11 -> D10 -> D10`.

The predecessor death-map run is excluded: its GT used the wrong replay-coordinate
transform, so its `0.1282` score is invalid and is not a calibration result for this
task.

## Anti-shortcut ablations

All measured ablations use Harbor 0.20.0 and GPT-5.6 Sol with high reasoning.

| condition | score | predicted | model tool calls | runtime | trajectory |
|---|---:|---:|---:|---:|---|
| Prompt/schema, no media | 0.0000 | 0 | 6 | 00:34 agent | `rollouts/codex-no-media.jsonl` |
| One temporal-midpoint frame | 0.0000 | 0 | 9 | 01:34 total | `ablations/single-frame-codex-high.jsonl` |
| Every native 30-fps frame pasted, no tools | 0.0000 | 30 | 0 | 10:31 total | `ablations/frame-dump-no-tools-codex-high.jsonl` |

For the no-media run, both the workspace copy and `/baked/final.mp4` were absent.
Codex searched the workspace and common media locations, then abstained rather than
inventing events. The single-frame run retained only the source frame at 1557.5
seconds and removed the full video before the agent step; Codex independently
confirmed that the MP4 contained one decoded frame and abstained.

For the frame-dump run, all 93,450 source frames were placed chronologically in 78
contact sheets, with each cell labeled by a global frame number. The full video was
removed, and all model tools were disabled. The model produced 30 schema-valid
events, but only five matched a ground-truth clock and none matched the victim,
killer, or any complete trajectory. All three measured rewards pass the ablation
ceiling of at most `0.15`. Audio-only and video-only separation is not applicable
because the task input is a silent video. Exact artifact and sanitization conventions
are documented in `ablations/README.md`.
