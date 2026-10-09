# Cross-harness attempts with no score

These records disclose requested calibration attempts that did not produce a valid
terminal trajectory. They are not model results and must not appear as numeric rows
in the scored performance table. `score` and `turns` are deliberately `null`.

Claude Code could not begin inference because the installed client was not
authenticated. The latest native Antigravity attempts began inference but failed
the frozen transport/trajectory validator before a scoreable terminal submission
was established. Only compact, privacy-safe provenance is committed here. The
sanitized A/B packages remain local, were independently compared byte for byte, and
are bound by the hashes below; raw runtime logs, terminal reports, credentials, and
machine-local paths are excluded.

| harness | requested model | status | inference started | failure stage | record |
|---|---|---|---:|---|---|
| Claude Code 2.1.209 | Fable 5 and Opus 4.8 | `NO_SCORE` | no | authentication | `claude-code.no-score.json` |
| Antigravity CLI 1.1.22 | Gemini 3.5 Flash | `NO_SCORE` | yes | phase 1 segment 0 classification | `antigravity-flash.no-score.json` |
| Antigravity CLI 1.1.22 | Gemini 3.1 Pro | `NO_SCORE` | yes | phase 2 attempt 1 classification | `antigravity-pro.no-score.json` |

These attempts leave authenticated native Claude and terminal-valid native
Antigravity calibration open. A future successful run should be added under
`../rollouts/` with its full trajectory, submitted solution, verifier details, and
tool-call count; it must not overwrite these failure records.
