# Native Claude harness record

The Opus 4.8 row is a native `claude -p` rollout. This file records exactly how
it was launched, because the round it replaces was rejected for harness parity:
that one ran through a VS Code Copilot agent-host whose wrapper prompt added
solving guidance — "validate the closed vocabularies", "ensure all expected
chronological clearances are represented" — that no other harness saw.

## Prompt

The prompt is the contents of `steps/solve/instruction.md`, byte for byte, and
nothing else — sha256 `a970d16d…11e4`, 7407 bytes, the same file this PR ships.
No `--append-system-prompt`, no wrapper preamble, no tool coaching,
no scoring hints. The file is bind-mounted read-only and the entrypoint passes
it through unmodified:

```bash
prompt="$(cat /workspace/instruction.md)"
claude --print "$prompt" --model claude-opus-4-8 \
  --output-format stream-json --include-partial-messages --verbose \
  --permission-mode bypassPermissions \
  --disallowedTools "WebFetch,WebSearch" \
  --add-dir /workspace
```

`MAX_THINKING_TOKENS=31999` sets high reasoning effort, matching the `high`
setting used for the Codex and Antigravity rows.

## Isolation

The container is started with `--network none`, so it has no network interface
at all — stricter than the `iptables`-based posture the repository's other
native runners use, where an interface exists and egress is filtered by uid. The
model endpoint is reachable only through a single bind-mounted unix socket,
re-exposed inside the container on `127.0.0.1:8787` by a byte-forwarding bridge.
Nothing else crosses the boundary; there is no path to the public internet, to
the ground truth, or to the calibration workspace.

```bash
docker run --rm --name fg-native-claude \
  --user 0 --cpus 8 --memory 8g --network none \
  -e ANTHROPIC_AUTH_TOKEN \
  -v .../instruction.md:/workspace/instruction.md:ro \
  -v .../materials:/workspace/materials:ro \
  -v .../output:/workspace/output \
  -v .../work:/workspace/work \
  -v <claude 2.1.226 binary>:/usr/local/bin/claude:ro \
  -v /tmp/fg-native-model:/run/model \
  --entrypoint /usr/local/bin/run-native-claude \
  agenticvbench-native-flightgear:20260811 claude-opus-4-8 high
```

The image is the same frozen `agenticvbench-native-flightgear:20260811` used for
the other rows. The agent itself runs as uid 1000 with a scrubbed environment
(`env -i`), so it never sees the operator's credentials beyond the API token or
the operator's home directory.

`/workspace` contains only `instruction.md` and `materials/flight.mp4`. Telemetry,
command schedules, controller traces, and ground truth are not mounted.

### What the bridge does and does not guarantee

Stated precisely, so the claim is not stronger than the mechanism. The bridge is
a blind byte pump: it copies bytes between the in-container socket and the
outside unix socket and does not parse, filter, or inspect HTTP. It therefore
does **not** enforce that only the model API is reachable. What bounds the run is
that `--network none` leaves exactly one path out of the container, and the far
end of that path is a model endpoint and nothing else — so the no-web property
rests on the upstream host being model-only, not on the bridge policing traffic.

`WebFetch` and `WebSearch` are additionally disallowed at the harness level, and
the trajectory records every tool call, so any attempt to reach the network is
visible in the retained trajectory rather than merely assumed absent.

## Outcome

`claude` exited 0 after 147 tool calls. The run scores **0.0000**.

Two independent reasons, both worth recording. The submitted
`/workspace/output/solution.json` is a bare JSON array of 65 objects rather than
`{"clearances": [...]}`, so the judge rejects it outright with `ValueError:
top-level object must contain clearances`. That is the row's score. Wrapping the
array by hand — a diagnostic, explicitly *not* this row's reported number —
still gives 0.0000, with 8 of 260 instrument-snapshot units, the first target
misheard ("two niner three" → 93), and altitude readings roughly 1000 ft off.

`ledgers/claude-opus-4.8-native.json` holds the submitted bytes verbatim,
including the bare-array shape, so both facts are checkable.

The raw trajectory is 13,395 lines / 15,343,222 bytes, because
`--include-partial-messages` records every streaming delta. It is published as a
hash-pinned release asset, and `claude-opus-4.8-native.jsonl` in this directory
is the condensed copy (660 lines / 1,232,159 bytes) that
`condense_trajectory.py` regenerates from it byte for byte. All 147 tool calls,
147 tool results, 102 thinking blocks, and 79 text blocks survive; only the
re-serialised deltas and 84 base64 image payloads do not. Hashes and the
verification command are in `README.md`.
