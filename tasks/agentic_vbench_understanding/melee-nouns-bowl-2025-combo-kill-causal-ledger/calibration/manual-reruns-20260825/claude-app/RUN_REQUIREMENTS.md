# Claude App Run Requirements

This document is for the human operator. Do not paste it into the model chat:
the model-facing task must remain byte-for-byte identical to `run/instruction.md`.

## Materials and Prompt

- Start a new empty Claude app conversation, with no project knowledge, prior
  chat context, connectors, MCP servers, browser, web search, or computer-use
  capability.
- Upload only `run/materials/match.mp4` to that conversation.
- Paste the complete contents of `run/instruction.md` as the sole user prompt.
- Do not reveal this repository, the judge/scorer, replay IDs, prior outputs,
  VOD URLs, set results, annotations, reference ledger, or any other file.

## Task Summary

The video contains ten concatenated Nouns Bowl 2025 Melee games. The task is to
derive a chronological ledger of every qualifying player conversion: any
conversion with at least four damage-producing contacts, plus every conversion
that kills. The formal task file defines the exact conversion boundary,
hit-count, damage-band, terminal-state, player-tag, and JSON-schema rules.

The expected final artifact is a JSON object with exactly one `events` array.
Every event has `game`, `attacker`, `victim_stock_before`, `hit_count`,
`damage_band`, and `terminal`. No timestamps, explanations, confidence values,
move names, or non-qualifying conversions are allowed.

## Claude App-Specific Handling

Claude app cannot write directly to the prepared workspace. When it finishes,
copy only the returned JSON object into `run/output/solution.json`; do not edit
or repair its substantive answer. Export or screenshot the native conversation
and place it under `run/logs/`.

Before capture, complete `run/logs/network-policy.md` with the actual settings
and retained evidence. Then run the `capture.sh` command in `README.md`, using
the exact Claude model identifier and Claude app version used.
