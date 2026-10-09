# Calibration validator sources

This directory contains the validator source snapshots that produced the retained
Codex validation records, their offline mutation tests, and the deterministic
frame-session sanitizer used for the commit-sized raw-session artifact.

## Bound validators

| validation policy | source | source SHA-256 | retained evidence |
|---|---|---|---|
| `avb-formal-run-strict-v3` | `avb_validate_formal_run.py` | `cd7331f3e250c97731aefaaa83c70e251545eae1a79fae9483ee28a312a0f099` | full media, no media, single frame, scoreboard only |
| `avb-frame-dump-observed-zero-call-strict-v2` | `avb_validate_frame_dump_no_tools_run.py` | original run source: `412f521e83e96a7d70651b6f348c3855619c94b7005acaf5b11f9bed94187007` | Codex all-frame contact-sheet diagnostic |

The strict-v3 file is byte-identical to the source snapshot whose hash is embedded
in its retained validation records. The frame validator differs from its bound
`412f...` source only by removing two machine-local argument defaults: callers must
now provide `--docker-host` and `--docker-config`. This avoids committing a personal
filesystem path while preserving validation behavior for explicit invocations. The
packaged file hash is recorded in `SHA256SUMS`; the validation record continues to
bind the exact original source hash.

The frame validator's historical filename contains `no_tools`; its actual policy and
claim boundary are observed-zero-call only. It does not prove backend `tools=[]` or
`tool_choice=none`.

## Mutation tests

The staged tests contain the same test cases as their local source versions, with
only path plumbing made portable:

- `test_avb_validate_formal_run.py`: validator lookup is sibling-relative and the
  optional real-overlay checksum test reads `AVB_FORMAL_FULL_MEDIA_OVERLAY`.
- `test_avb_validate_frame_dump_no_tools_run.py`: validator lookup is
  sibling-relative.

The original local test-source hashes before those path-only packaging edits were:

```text
74f2f0298ed9b884af20e43406130150b87aea172b22ba32360cd0e17ed4dcfa  test_avb_validate_formal_run.py
9a13ce439d988cdbdeef6f016c09001ced81435bcf7558b20758faf0ce0f5604  test_avb_validate_frame_dump_no_tools_run.py
```

Run the portable suite with:

```bash
python3 -m unittest -v \
  test_avb_validate_formal_run.py \
  test_avb_validate_frame_dump_no_tools_run.py \
  test_sanitize_frame_dump_session.py
```

The suite has 45 tests: 13 strict-v3 tests, 29 observed-zero-call tests, and three
session-sanitizer tests. The one test that binds the real full-media overlay is
skipped unless
`AVB_FORMAL_FULL_MEDIA_OVERLAY` is supplied. The current portable run passes 44
tests and skips that one external-overlay check; earlier packaging validation
supplied the overlay and passed the original 42 validator tests.

`test_avb_validate_frame_dump_no_tools_run.py` requires Pillow.

## Session sanitizer

`sanitize_frame_dump_session.py` replaces quoted base64 image data URLs, encrypted
reasoning payloads, and the complete account-scoped `rate_limits` object with
deterministic `{redacted, bytes, sha256}` objects. The latter removes credit balances,
limit identifiers, reset windows, and related account metadata while retaining token
usage. The script verifies that every byte outside those three redaction classes is
copied unchanged. It also compares a normalized audit projection of every JSONL event
before and after sanitization, preserving event order, timestamps, model messages,
operation evidence, and ordered image identities. Its manifest records the original
session hash and size, the sanitized hash and size, counts and aggregate hashes for
all three redaction classes, and per-image decoded hashes. It never writes decoded
image bytes or a personal absolute path.

## Deliberate omissions

This package currently contains the portable validators for the retained Codex
runs. Harness-specific Antigravity validators belong here only together with a
terminal-valid archived trajectory and its completed validation report; setup
failures, interrupted runs, and gate-denied diagnostics are not scored evidence.

`SHA256SUMS` records the packaged hashes of every file in this directory except the
checksum file itself.
