# Codex Full Baseline r3 Artifact

The complete reviewable Harbor artifact is published as a GitHub Release asset:

<https://github.com/shengjun-zhang/agentic-vbench/releases/download/melee-codex-r3-20260829/melee-codex-full-baseline-r3.tar.gz>

| field | value |
|---|---|
| trial | `melee-normal__VmESmXy` |
| model | `gpt-5.6-sol` |
| Codex | `0.147.0-alpha.6.5` |
| reasoning | `high` |
| Harbor | `0.20.0` |
| exact F1 | `0.0132` |
| ground-truth events | 104 |
| predictions | 47 |
| schema-valid predictions | 47 |
| exact matches | 1 |
| bundle bytes | 17,298,050 |
| bundle SHA256 | `01d30e9a3d3ed40076767b3604a62da64c2597a07949f347abb4034003b7186e` |

The bundle contains the complete `trajectory.json`, `reward.json`,
`reward-details.json`, `result.json`, `config.json`, and Harbor artifact manifest.
Per-file SHA256 values are duplicated in `calibration/scores.md`.
