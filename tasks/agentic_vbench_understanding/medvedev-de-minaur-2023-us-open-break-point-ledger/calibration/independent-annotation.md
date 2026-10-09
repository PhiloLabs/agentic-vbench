# Independent full-video annotation

Status: **pending**. This document defines the blind packet, ledger-freeze, and
adjudication procedure. It is not evidence that either independent annotation has
already occurred.

## Canonical run identity

| item | value |
|---|---|
| task commit | pending |
| Docker image digest | `sha256:f592cda4dfc09ca25ae3a19d7e65d17248fb01059f061368eecf14ae1ae9cb28` |
| canonical silent-video SHA-256 | `d61bee17596a28dbc8f8b607e4fc0dd6542885dbe9cdad18e1953e89363b0860` |
| video probe | H.264, 1280x720, 30000/1001 fps, 7152.578767 s, 214363 decoded frames, zero audio streams |
| annotator A | pending |
| annotator B | pending |
| adjudicator | pending |
| annotation dates | pending |

## Blind packet construction

A coordinator who does not annotate the match must prepare two byte-identical
packets, one for A and one for B. Each packet contains only:

- the canonical complete silent video;
- the task instruction and output schema, including the field vocabularies and
  observable classification rules; and
- a blank ledger template with annotator-local event IDs, start/end timestamps,
  every required scalar field, the ordered `shots` array, free-form visible-evidence
  notes, and an uncertainty flag.

The packet must not contain or disclose an expected event count, an expected total
shot-token count, pre-cut point windows, point numbers from another dataset, MCP
codes or files, the oracle, `solve.sh`, `judge.py`, any prior model output, or the
other annotator's work. Packet manifests and SHA-256 hashes must be recorded before
distribution. A and B must confirm in writing that they did not access excluded
materials or outside match data during annotation.

## Independent passes and ledger freeze

A and B work separately and do not communicate about the match. Each annotator must:

1. Watch the complete video end to end in a normal-speed discovery pass, locating
   candidate break-point opportunities from the visible match state without using
   pre-cut windows.
2. Revisit every candidate and any uncertain transition at 0.5x speed or slower.
   Frame stepping may be used where contact, bounce, pressure, or score transitions
   remain unclear.
3. Decide independently how many qualifying events exist. Record every retained
   candidate with a video window, all scalar fields, the complete ordered `shots`
   sequence, and a concise visible-evidence note. Also retain rejected candidates
   with a reason so omissions can be audited.
4. Export a canonical UTF-8 JSON ledger, compute its SHA-256, and send only the
   ledger, hash, packet-manifest hash, completion timestamp, and blind-work
   attestation to the coordinator.

The coordinator verifies both hashes, marks both ledgers frozen, and makes immutable
copies before either ledger is shown to the other annotator, the adjudicator, or
anyone with oracle/MCP access. Any later correction remains a separate file; the
original frozen ledger is never overwritten.

| artifact | annotator | packet manifest SHA-256 | frozen ledger SHA-256 | frozen at | immutable path |
|---|---|---|---|---|---|
| blind ledger A | pending | pending | pending | pending | pending |
| blind ledger B | pending | pending | pending | pending | pending |

## Union and video-only adjudication

Only after both freezes may the coordinator construct the candidate union. Events
are aligned by overlapping video windows and visible point identity, never by an
expected ordinal or answer-key row. A candidate found by only one annotator remains
in the union and must be explicitly included or excluded by adjudication; it must
not be silently dropped. One annotator's single window may also be split when the
video establishes two distinct candidates, and two windows may be merged only when
they clearly identify the same point.

The adjudicator receives the canonical video, the task schema/rules, both frozen
ledgers, and the union table. The adjudicator first reviews every union candidate at
normal speed, then reviews each disagreement or uncertain observation at 0.5x
speed or slower. Adjudication must rely on visible score, serve, contact, trajectory,
position, and pressure evidence. It must preserve A's value, B's value, the final
value, and a short rationale for inclusion/exclusion and for every field or shot
token disagreement. Shot-array review covers insertion, deletion, order, stroke,
and direction.

| union ID | A local ID/window | B local ID/window | inclusion disagreement | field/shot disagreements | final disposition | rationale recorded |
|---|---|---|---|---|---|---|
| pending | pending | pending | pending | pending | pending | pending |

If the video does not support a defensible single value, use the schema's explicit
observable fallback where available: `terminal_court_position: "unknown"`,
`terminal_result: "error_unknown"`, `terminal_error: "unknown"`, or an unknown
serve/shot direction or stroke. Otherwise mask that field from scoring or document
accepted alternatives before sign-off. Never resolve indeterminacy by consulting an
expected count, MCP label, or provisional oracle.

## Post-adjudication audit and sign-off

Freeze and hash the video-only adjudicated ledger before comparing it with MCP, the
provisional oracle, `solve.sh`, or `judge.py`. Those materials may then be used only
as a discrepancy audit. Every resulting answer-key change must cite the frozen
video evidence and must not alter either blind source ledger or the pre-comparison
adjudicated freeze.

- [ ] Packet A and packet B are byte-identical and their manifests are committed.
- [ ] Both blind-work attestations and both independent frozen raw ledgers are
      committed with verified SHA-256 hashes.
- [ ] Both annotators completed a normal-speed full-video pass and 0.5x-or-slower
      review of candidates and uncertain transitions.
- [ ] The union contains every matched and unmatched candidate from both ledgers.
- [ ] Every union disposition and every field/shot disagreement preserves A, B,
      the final value, and a visible-evidence rationale.
- [ ] The adjudicated ledger was frozen before any MCP/oracle comparison.
- [ ] `solve.sh` and `judge.py` match the final adjudicated ledger.
- [ ] Oracle remains 1.0 and an empty or missing submission remains 0.0 after any
      answer-key change.
- [ ] If adjudication changes a frozen task file or reference value, every formal
      calibration and anti-shortcut ablation is rerun before its evidence table is
      updated.
- [ ] The target `human-verified` tier is updated from pending to achieved.
