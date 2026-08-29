# Agent integrity on this match

This match's rally-by-rally log is public, so an agent with web access can look the
answer up instead of watching the video. These are the runs where that mattered, kept
for what they show about agent behaviour rather than as calibration scores — the
scored runs are in `../rollouts/`.

## Gemini backends ground against the public record

`antigravity-gemini_grounding-tainted.txt` — the trajectory of an Antigravity run
whose Gemini backend reached the web and started reconstructing the match from the
WMT Live Stats site rather than the pixels, down to hunting the site's JSON API. Any
score from a run like this measures retrieval, not video understanding.

`antigravity-flash-noweb_copied-answer-via-BypassSandbox.txt` and
`antigravity-flash_copy_perfect_solution.py` — with the web cut off, the same agent
escalated to `BypassSandbox: true` and reached outside its workspace for a file. This
is why cutting web access alone is not enough.

## What a clean measurement needs

Three isolation vectors applied together, none of which is sufficient alone:

- workspace **outside** the repo — no `.git`, no sibling runs, no answer files
  reachable;
- `trustedWorkspaces` narrowed to that workspace only, so `--sandbox` refuses every
  other path ($HOME, /tmp and the repo all return "Operation not permitted");
- the agent's persistent memory (`conversations/`, `brain/`,
  `conversation_summaries.db`) wiped beforehand, so nothing seen in an earlier session
  can be recited.

Plus an always-on `AGENTS.md` (pixels only, no web, no access outside the workspace)
and a gate that voids the window on grounding, a successful sandbox bypass, an answer
copy, or a perfect claim backed by fewer than 30 frames.

## Under full isolation

`antigravity-flash-cleanroom_3vector-isolated_verified-clean.txt` and
`antigravity-flash-cleanroom.solution.json` — the run passes the gate (web 0, blocked
escape attempts 8, bypass successes 0, answer copies 0) and does real work: a four-set
partition, template-matched score-bug OCR, a 107-update timeline, fuzzy nameplate
matching. Across two ~3 h windows it sampled 54 frames, produced 3 event candidates
and shipped 1 — which was wrong. The second window added nothing to the first. 720p
broadcast jersey and nameplate OCR is where it stops.

`antigravity-flash-noweb-isolated_389frames_stalled.txt` — a longer isolated attempt
that stalled at 389 frames without converging on an event list.
