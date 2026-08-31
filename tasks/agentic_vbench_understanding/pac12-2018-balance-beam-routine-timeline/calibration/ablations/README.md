# Shortcut-ablation trajectories

All five controls use the final seven-field task contract and deterministic
scorer. They were launched in fresh workspaces as batch `20260827T214117Z`,
with one non-resumable 5,400-second process per control. None timed out,
restarted, resumed, or used task-side web/network access.

| control | model / reasoning | reward | calls | elapsed seconds | published trajectory |
|---|---|---:|---:|---:|---|
| no media | `gpt-5.6-sol` / xhigh | 0.0 | 6 | 40.999 | `codex-no-media-20260827T214117Z/codex-gpt-5.6-sol-xhigh.public.jsonl` |
| single frame | `gpt-5.6-sol` / xhigh | 0.0 | 5 | 41.690 | `codex-single-frame-20260827T214117Z/codex-gpt-5.6-sol-xhigh.public.jsonl` |
| frame dump, no tools | `gpt-5.6-sol` / medium | 0.0 | 0 | 294.279 | `codex-frame-dump-no-tools-20260827T214117Z/codex-gpt-5.6-sol-medium.public.jsonl` |
| video only | `gpt-5.6-sol` / xhigh | 0.130435 | 138 | 1,908.435 | `codex-video-only-20260827T214117Z/codex-gpt-5.6-sol-xhigh.public.jsonl` |
| audio only | `gpt-5.6-sol` / xhigh | 0.0 | 361 | 4,155.995 | `codex-audio-only-20260827T214117Z/codex-gpt-5.6-sol-xhigh.public.jsonl` |

Every reward is at or below the required 0.15 ceiling. The strong-agent
greater-than-50-call gate does not apply to shortcut controls; the no-tools
control must use, and did use, exactly zero tools.

## Delivered degradations

- `no_media` presents the task prompt and output schema with no media file.
- `single_frame` presents one full-size frame at the locked source midpoint,
  4,178.167 seconds.
- `frame_dump_no_tools` presents 8,356 uniformly sampled source seconds in 14
  image attachments and disables tool use. The attachments cover source
  seconds 0 through 8,355 in order.
- `video_only` presents the full H.264 source with every audio stream removed.
- `audio_only` presents the full 8,356.334-second Opus stream with no video
  stream.

The input manifests record the exact delivered media hashes, probes, frozen
prompt/scorer/task hashes, and original locked-source digest. The video-only
control found three strict complete-record matches; the other four found none.

## Publication bundles

Each directory's `public-artifacts.json` is its authoritative compact manifest.
It lists the publication-safe prompt artifact, one textual trajectory, input
manifest, solution, run metadata, agent-tool audit, result summary, and
publication redaction audit with byte counts and SHA-256 digests. The
video-only prompt artifact localizes the executed workspace path; its run
metadata retains the executed-prompt hash and records that sole textual delta.

Untouched native trajectories, staged media, frame attachments, private input
snapshots, stderr, and other diagnostics remain local and excluded from git.
The `.public.jsonl` derivatives preserve event order and completed tool-call
linkage while replacing local identity/path tokens and media bodies where
needed. Their redaction audits bind each derivative to the untouched native
source and verify deterministic regeneration.
