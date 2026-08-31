# Strong-agent trajectories

The annotation gate in `../../annotations/status.json` is complete, and the
current scored contract has seven fields. All three fresh final-contract runs
pass the score and tool-call gates. Earlier flat files and timestamped attempts
are superseded and are not final-contract evidence.

The final runs are:

- Antigravity CLI / `gemini-3.5-flash-high` / high:
  `antigravity-seven-field-20260827T200119Z/`;
- Codex CLI / `gpt-5.6-sol` / xhigh:
  `codex-seven-field-20260827T184157Z/`; and
- Claude Code CLI / `claude-opus-4-8` / high:
  `claude-seven-field-20260827T205411Z/`.

Never overwrite or continue these runs.

## Compact publication sets

`public-artifacts.json` is the authoritative publication manifest inside each
final-run directory. Every listed path is relative to that directory and has an
exact byte count and SHA-256 digest. Each manifest contains only:

- the exact rendered initial prompt;
- one auditable textual trajectory;
- the staged-input manifest;
- the raw solution and checkpoint;
- run-control metadata;
- the completed tool-call count;
- the network/credential audit;
- the result summary; and
- the publication-redaction audit, when applicable.

The single published trajectory for each harness is:

| harness | published trajectory | form |
|---|---|---|
| Codex | `codex-gpt-5.6-sol-xhigh.public.jsonl` | identity-redacted event JSONL |
| Claude | `claude-code-opus-4.8-high.public.jsonl` | event-preserving text-only derivative |
| Antigravity | `antigravity-gemini-3.5-flash-high.public.jsonl` | database-derived event JSONL |

Full internal manifests and run artifacts remain available locally for audit,
but they are not part of the pull request. In particular, the public sets omit
nested input snapshots, preflight and reward dumps, version dumps, stderr,
database state, visual payloads, and other diagnostics. This follows the family
requirement of one trajectory per agent without artifact bloat.

## Rights and privacy exception

This publication bundle requests the reviewer's offered exception for
source-derived visual payloads and identity-bearing native state. The original
files remain untouched locally, while the public trajectories retain the
auditable text and bind back to the originals by SHA-256.

Codex's native trajectory is 82,624 bytes with SHA-256
`e23a07a895ed20f89da0a81b235bbb6c30be1139843486cd7476f030edcb7e14`.
Its public derivative preserves all 122 JSONL records and the complete ordered
identifier/tool-link stream, replacing 15 local-username occurrences across two
text fields. `codex-publication-redaction-audit.json` records both digests,
structural and order checks, and zero remaining identity, media, or credential
signatures.

Claude's original native trajectory is 27,200,113 bytes with SHA-256
`ed77c665eaf1d8fdcc75de77f2da2622a5748b0e1dc2cd3f7be283d619726fa9`.
Its public derivative preserves all 2,375 JSONL records, the same ordered
tool-use and tool-result identifiers, and all 123 reasoning signatures. It
replaces 64 JPEG-body occurrences: 32 `content.source.data` bodies and 32
`tool_use_result.file.base64` bodies. The bodies represent 32 unique payloads;
each replacement retains the decoded payload's byte count and SHA-256.
The same pass replaces 12 local-username occurrences across four text fields.
`claude-publication-redaction-audit.json` records the source and destination
digests, replacement totals, the preserved ordered identifier/tool-link stream,
and zero remaining identity, media-body, or credential signatures.

Antigravity's provider diagnostic log is not used as the published trajectory.
The public JSONL is decoded from the untouched 16,113,664-byte conversation
database with SHA-256
`5fceb6e4fb44fcf9daa996958f40ec5093ae759366d7d6d0d7f0bfa0241b8735`.
It emits all 768 database steps in order: one user message, 371 assistant
messages, 370 linked tool results, 23 system messages, and three checkpoints.
All 370 ordered tool request/result ID, name, argument, and provider-signature
records match exactly before privacy redaction. The derivative replaces 370
opaque provider-signature bodies and 85 referenced image bodies with SHA-256
and byte-count placeholders, then removes email and local-home identifiers.
`antigravity-publication-redaction-audit.json` records the protobuf field map,
source and destination digests, event counts, linkage checks, native-transcript
cross-checks, and exact redaction totals.

The omitted Antigravity native brain archive is 220,870,144 bytes with SHA-256
`58a5a8ccabe42ba1294db285cb36045054c1ad7a8675e2afad66ef041213e03c`.
It contains 1,745 source-derived image payloads and exceeds GitHub's 100 MB file
limit. Only the 85 image bodies referenced by emitted tool results are hashed
for placeholders; no image body is published. The native conversation database
and path inventories are also omitted because they contain authentication
identifiers or personal local paths. No credential value was detected in either
original run.

The complete local manifests remain in `claude-artifacts.json`,
`antigravity-artifacts.json`, and `codex-artifacts.json`. They are retained only
as internal integrity inventories and are deliberately excluded from the compact
public sets.
