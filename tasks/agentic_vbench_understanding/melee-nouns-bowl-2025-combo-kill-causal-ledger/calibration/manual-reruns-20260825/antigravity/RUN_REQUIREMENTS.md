# Antigravity App Run Requirements

This document is for the human operator. Do not paste it into the model task:
the model-facing task must remain byte-for-byte identical to `run/instruction.md`.

## Materials and Prompt

- Start a new empty Antigravity.app task and make `run/` its only local
  workspace. Map that workspace to `/workspace` when the app offers a workspace
  mount setting.
- Give the model exactly the contents of `run/instruction.md` as its user task.
- Permit local video inspection and intermediate output only under
  `run/work/` (equivalently `/workspace/work/` in a mapped runtime).
- Do not give the model repository files, scorer/judge access, replay files,
  VOD URLs, prior run outputs, external set facts, browser/search, connectors,
  MCP servers, or external files beyond the prepared workspace.

## Task Summary

The model must inspect the ten-game Melee video and construct a chronological
conversion ledger. Include every conversion with at least four damaging contacts
and every killing conversion. The formal task prompt provides the authoritative
definitions for conversion continuity, 45-frame reset, trades, reversals,
damage bands, stock values, supported player tags, and the strict JSON schema.

The required final file is `run/output/solution.json` with exactly an `events`
array; each event contains `game`, `attacker`, `victim_stock_before`,
`hit_count`, `damage_band`, and `terminal`. It must not contain timestamps,
move names, explanations, confidence scores, or non-qualifying events.

## Provenance and Capture

Use model `Gemini 3.5 Flash` and harness `Antigravity.app 2.3.1`. Disable
general egress other than unavoidable model-provider traffic, document the
actual policy in `run/logs/network-policy.md`, and retain the native task export
or logs in `run/logs/`. When the task ends, run `./capture.sh` in this directory.
