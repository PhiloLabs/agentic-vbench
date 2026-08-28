# Overnight autonomous session — decision log (2026-08-28)

Brief: user asleep ~6 h; get at least one PR to a mergeable state. Target is PR #61
(USC block-only), which has the most reviewer items already closed.

Each entry: the question I would have asked, the default I took, why, and how to undo.
External review (ChatGPT) was NOT run — Claude in Chrome is not connected in this
session; noted per the review rule and to be revisited if any decision below is
still reversible when the user returns.

---

## D1. Ledger scope: all 23 events, or a documented sample?
- Default: verify all 23 from the post-point close-up window.
- Why: the reviewer asked for every event, and the close-up window (found today) makes
  it tractable — full frames, no per-event cropping needed.
- Undo: the ledger is an additive calibration artifact; deleting the file removes it.

## D2. Blocked-hitter field, if it proves unrecoverable on many events
- Default: keep the field, and record per-event recoverability honestly in the ledger.
  Only propose a schema change if a majority of events fail.
- Why: changing the scorer contract silently would invalidate the calibration numbers
  already measured today (Codex 0.0185, Opus 0.0). Evidence first.
- Undo: schema change is one commit; judge + tests + oracle regenerate together.

## D3. Ablation agent
- Default: run the ablations with Sonnet rather than Opus/Codex.
- Why: ablations measure whether the TASK leaks (no-media, single-frame, frame-dump),
  not model strength; a mid-tier model is the standard probe and leaves the premium
  pools for real calibration. Fable is out of credits.
- Undo: rerun with any model; ablations are cheap relative to full runs.

## D4. Antigravity
- Default: leave it marked "not run" for this task.
- Why: user's earlier instruction plus the sister-task finding that Gemini grounding
  cheats. Running it would need the 3-vector isolation recipe and free-tier quota.
- Undo: run it later under that recipe and fill the row.

## D5. Trajectory publication
- Default: publish full raw trajectories to the existing HF dataset repo, pinned by
  revision, rather than committing hundreds of MB into git.
- Why: reviewer asked for hash-pinned release/LFS/dataset assets; the repo already
  uses that HF dataset for media, and git would bloat.
- Undo: HF uploads are deletable; the repo keeps only links and hashes.
