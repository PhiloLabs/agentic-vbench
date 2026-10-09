# Raw calibration trajectories

One full raw trajectory per required harness, plus the submitted ledger each one
produced. Measured scores are in `../scores.md`; ablation and replaced-round
trajectories are hash-pinned release assets listed in `../ablations/README.md`.

- `codex-gpt-5.6-sol.jsonl`: complete native Codex CLI JSONL.
- `claude-opus-4.8-native.jsonl`: native `claude -p` stream-json trajectory,
  condensed — see below. The prompt is the contents of
  `steps/solve/instruction.md` byte for byte — no system-prompt append, no
  wrapper guidance. The launcher, including the network posture, and the reason
  this row scores 0.0000 — it submitted a bare JSON array instead of
  `{"clearances": [...]}` — are both in `claude-opus-4.8-native.md`.
- `antigravity-gemini-3.6-flash-high.jsonl`: complete native Antigravity CLI
  stream-json trajectory.

## The native Claude trajectory is condensed, and the raw file is pinned

`claude -p --include-partial-messages` writes every streaming delta, so the raw
rollout is 13,395 lines / 15,343,222 bytes — an order of magnitude larger than
anything else tracked in this repository. The raw file is published as a
hash-pinned release asset instead, and the committed copy (660 lines /
1,232,159 bytes) is generated from it by `condense_trajectory.py`:

| file | bytes | sha256 |
|---|---:|---|
| `required-row_claude-opus-4.8-native_full-trajectory.jsonl.gz` (release asset) | 7,883,309 | `5a0964f465f6272691f60ac79d37c9e7856440a826d33453ce0dc41a0fc73143` |
| the same, decompressed | 15,343,222 | `819b958515268e0ccfc68c48d87d309d129b5b549eb9991af75b84d0b08a8990` |
| `claude-opus-4.8-native.jsonl` (committed) | 1,232,159 | `be4a275123397f16dea1632940aae991e0136edfec41949ba29a3fff9cdbc8df` |

<https://github.com/JordanPeng/agentic-vbench/releases/tag/flightgear-calibration-20260827>

```bash
gzip -d required-row_claude-opus-4.8-native_full-trajectory.jsonl.gz
python3 calibration/rollouts/condense_trajectory.py \
    required-row_claude-opus-4.8-native_full-trajectory.jsonl out.jsonl
cmp out.jsonl calibration/rollouts/claude-opus-4.8-native.jsonl
```

The condensation drops 12,735 `stream_event` records and replaces 84 base64
image payloads. Neither loses content: the deltas open 328 content blocks and
the assembled `assistant` records carry the same 328 (102 thinking, 79 text,
147 tool_use) under the same 147 message ids, and the one field that lives only
on the delta stream, `ttft_ms`, is copied onto the assembled record. All 147
tool calls, 147 tool results, and the final result record survive verbatim. Each
image becomes a placeholder carrying that payload's length and sha256, so "an
image of exactly these bytes was returned here" stays checkable against the
asset.

The earlier Opus 4.8 round, which ran through a VS Code Copilot agent-host whose
wrapper prompt added solving guidance the other harnesses never saw, is not a
required-harness row. It is retained as a replaced round in the release; see
`../ablations/README.md`.

## Ledgers

`ledgers/*.json` are the answers these agents actually submitted, kept next to
the judge so `python3 calibration/rescore_ledgers.py` reproduces every number in
`../scores.md` from the repository alone, with no rollout replay and no network.
`claude-opus-4.8-agent-host-superseded.json` is the replaced round's ledger,
retained so the parity comparison can be checked rather than taken on trust.

Generated images, reward dumps, and model caches are not committed. Personal
home paths and task-specific calibration workspace roots are redacted; generic
temporary/cache paths may remain. Redaction replaces path strings only; no
events, tool inputs, tool results, or model messages are removed. The one
further transform is the Claude row's condensation described above, which drops
only re-serialised streaming deltas and image bytes and is reversible in the
sense that matters — the unmodified file is a hash-pinned release asset and the
committed file regenerates from it byte for byte.

## Instruction version and harness deviations, per row

The maintainer's parity item was about the Claude row's wrapper prompt. Fixing
that surfaced a second, wider parity gap: the three original rows all ran an
*earlier* `instruction.md` than the one this PR ships. Re-running every row
against the shipped text was not possible here, so the exact deviation is
recorded per row instead.

| row | instruction sha256 | native re-run |
|---|---|---|
| Codex GPT-5.6 Sol | `0963eb1a…c3e1` (6887 B) | not possible — see below |
| Antigravity Gemini 3.6 Flash High | `0963eb1a…c3e1` (6887 B) | attempted, abandoned — see below |
| Claude Opus 4.8 (native) | `a970d16d…11e4` (7407 B) | yes, this PR |

`a970d16d…11e4` is the full sha256 of the `steps/solve/instruction.md` shipped
in this PR; verify with `sha256sum steps/solve/instruction.md`.

The whole difference is a single hunk inside `## Clearance fields` (`diff -u`
against the old text reports exactly one `@@`); neither version describes the
scoring method. The old text applied 25 ft / 2 deg / 2 kt to
spoken targets *and every state snapshot* alike, where the shipped text splits
those — 25/2/2 for spoken targets, 100/8/3 for anything read off a gauge. The
shipped text also adds the two sentences saying that a snapshot is compared
against the trajectory at the timestamp the answer itself reports, and asks for
times as precise as the agent can make them. So both surviving rows were told to
hit a band four times tighter than the one they are now scored against, and
neither was told that its snapshots would be read at its own claimed times.
Their scores may therefore understate what those harnesses would do on the
shipped text — the deviation runs against them, not in their favour.

**Codex — cannot be re-run in this environment.** `codex exec` returns 401
Unauthorized; `~/.codex/auth.json` and `config.toml` are absent, and the
in-image `run-azure-codex` path needs `AZURE_OPENAI_API_KEY` and
`AZURE_OPENAI_UPSTREAM`, neither of which is present. The row is otherwise
clean: `status: graded`, `solver_exit_status: 0`, 88 tool calls, no wrapper
prompt and no post-processing.

**Antigravity — two further deviations, and the re-run was abandoned.** Beyond
the old instruction, this row alone received an appended paragraph no other
harness saw, telling it to re-read the Output section and validate its JSON
("do not finish with merely parseable but nonconforming JSON") — the full text
is in `operator/command.txt` in the released trajectory. It was then given a
*second* schema-repair pass on top, evidenced by `solution.pre-repair.json` and
`trajectory.repair-schema.raw.jsonl`. Its `row.json` also records
`native_result_status: ERROR`, `solver_exit_status: 1`, and
`status: graded_needs_manual_audit`.

A native re-run on the shipped instruction was built and abandoned. The
harness's own `sandbox-bash`/bwrap isolation could not be made to work in this
container, and it **fails open**: a `curl https://example.com` smoke test
returned HTTP 200 while `agy` logged `connecting to sandbox server: … connection
reset`. Three postures were tried (default, `seccomp=unconfined` +
`apparmor=unconfined` + `SYS_ADMIN`, and `--privileged`); all three ran the
command unsandboxed. Since `agy` runs its harness and its tools under the same
uid, the codex-style `--uid-owner` egress block does not apply either, so no
verified-isolated re-run was available. Rather than publish a row whose network
posture is weaker than the one it replaces, the re-run was dropped.

That decision does not weaken the existing row. The *original* antigravity
rollout was correctly isolated, and its own trajectory proves it: its only
network attempt, `pip install opencv-python-headless pillow matplotlib`, fails
with `[Errno -3] Temporary failure in name resolution` on every retry.
