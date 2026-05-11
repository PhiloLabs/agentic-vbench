# Video Ordering Task — Silicon Valley's New Miracle Drug

You are given **35 candidate video clips**: `1.mp4`, `2.mp4`, …, `35.mp4`.

These clips are the shots of a single chapter from a short film, **renamed and shuffled into a random order**. Each clip appears **exactly once** in the correct ordering — there are no extra clips and no duplicates.

## Your job

Reassemble the clips into the original narrative order described below.

## Story overview

Reporter Dan Toomey investigates the craze for injectable peptides, unregulated drugs often sourced from China that promise health and cosmetic benefits. He interviews freelance reporter Ezra Marcus about peptide "stacks" sold through both legitimate med spas and grey-market channels. Online communities connect consumers to Chinese manufacturers who label products "for research purposes only" to bypass regulations. Biohacker Tore Pastore endures severe side effects but deems the risk worth the wedding-day results. Skeptic Dr. Eric Topol calls the claims unproven "bro science," while proponents frame the risk-taking as a new health frontier.

## Additional notes

- Stay inside this working directory. Don't read, write, or search
  files outside it — no parent directories, no other paths on the
  system.
- Don't try to identify the source film or look it up online.
  Don't search for the original chapter, transcripts, or related
  metadata to compare against the clips — work only from the bytes
  you've been given. (Other web lookups, e.g. tool docs, are fine.)

## What to submit

1. **`/workspace/output/solution.mp4`** — the 35 clips concatenated in the correct narrative order, in this folder. Each clip is used in full, exactly once.
2. **`/workspace/output/solution.json`** — a manifest describing the order you chose.

### `solution.json` format

```json
{
  "segments": [
    {"output": [0.0, 7.417], "source": "2", "source_range": [0.0, 7.417]},
    {"output": [7.417, 10.917], "source": "6", "source_range": [0.0, 3.500]}
  ]
}
```

### Rules

- Exactly **35 entries**, one per slot, in slot order.
- Each clip number from `"1"` to `"35"` must appear **exactly once** as a `source`.
- Intervals are **half-open** `[start, end)` — end is exclusive.
- `output` — time range where this clip appears in `solution.mp4`.
- `source` — clip number as a string (e.g. `"3"` for `3.mp4`).
- `source_range` — portion of the clip used; should be `[0, clip_duration]` (use each clip in full).
- Segments must be **contiguous**: each `output[0]` equals the previous `output[1]`; first starts at `0.0`, last ends at `solution.mp4`'s total duration.

## Done when

Both `/workspace/output/solution.mp4` and `/workspace/output/solution.json` exist.

---

## Workspace layout

- The candidate clips have been pre-downloaded to `/workspace/materials/`
  (named `1.mp4` through `N.mp4`). Read them from there.
- Use `/workspace/work/` for any intermediate scratch files.
- Use `/workspace/output/` only for the two final deliverables.
- `ffmpeg` and `ffprobe` are available on `PATH`.
