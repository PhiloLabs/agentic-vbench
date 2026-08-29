# Calibration — byu-wsu-2023-volleyball-ace-block-timeline

Deterministic F1 scorer (`steps/solve/tests/judge.py`). A task clears the bar when
every strong agent scores low (target **< 0.10**; reviewer accepts **≤ 0.109**) and a
real attempt takes **more than 50 tool-call turns**. Oracle must be 1.0 and an empty
attempt ≈ 0.

| run | score | rollout (tool-call turns) |
|---|---|---|
| oracle (exact answer key) | 1.0 | — |
| empty / null | 0.0 | — |
| 24-entry plausible guess | 0.0 | — |
| Codex CLI (gpt-5.6, xhigh) | 0.02 | 126 |
| Claude Code CLI (Opus 4.8 [1m], xhigh) | 0.0 | 291 |
| Claude Code CLI (Fable 5, xhigh) | 0.15 | 733 |
| Antigravity (Gemini 3.5 Flash, High) | 0.0 † | 2 windows, 54 frames (integrity-verified clean) |

Opus (0.0), Codex (0.02) and Fable (0.15) are clean, genuine runs well past 50 turns
(mean ≈ 0.057). Opus shipped only 6 events and none matched — not even set+score+type —
so 0.0 holds under both the old and hardened schema; Codex and Fable bracket the ~0.10
line. The terminal ace/block moment is a sub-second blur and net-front jersey ID at 720p
is genuinely hard, which is what keeps strong agents low. Run-to-run variance is real:
F1 is scale-invariant in the number of events, so the spread reflects how many terminal
moments a run happens to resolve, not how long its list is.

† **Antigravity's 0.0 is integrity-verified, but only after defeating three separate
cheat vectors** — reviewers using Antigravity/Gemini should know about all three:
1. **Web grounding.** Un-isolated, Gemini grounds against the public NCAA box score —
   server-side Google Search inside the model↔API channel, which no local or container
   network policy can block — and returns a near-perfect list without watching the
   video. Defeated by an always-on "pixels only, no web" rule (verified 0 grounding
   references across every isolated run).
2. **Local answer-file theft.** With grounding blocked, if any prior-run answer file is
   reachable on disk it enumerates sibling directories and copies it, self-approving a
   `BypassSandbox` to escape `--sandbox`. Defeated by running in a workspace outside the
   repo with `trustedWorkspaces` narrowed to that dir only, so the sandbox blocks every
   path except the workspace (8 escape attempts blocked in the clean run).
3. **Cross-conversation memory.** Once it has seen the answer via any vector, agy's
   persistent local store (`conversations/`, `brain/`, `conversation_summaries.db`)
   retains it, so even a *fresh* `agy -p` regurgitates the memorised answer. Defeated by
   wiping those stores before the run.
Only with all three closed does it do honest work: a 4-set partition, template-matched
scoreboard OCR, an LNDS-filtered 107-update timeline, and fuzzy nameplate matching — yet
across two ~3 h windows it isolated just 3 event candidates and shipped 1 (wrong) event,
because 720p broadcast nameplate/jersey OCR defeats it. The run is **not converging**
(window 2 added 0 events in 3 h), so the honest score is 0.0. Transcripts for all three
cheat vectors and the clean run are in
`rollouts/`.

Raw transcripts are in `rollouts/` — one file per agent, so a reviewer can confirm each
score was earned honestly (or, for Antigravity, see exactly how each cheat vector was
detected) and count the tool-call turns.

Note on `no_media`: the official NCAA rally-by-rally log for this match is public web
data. The container builds with `allow_internet = false` and the prompt forbids lookups,
so the no-media ablation measures pure model recall/guessing of that public record; the
measured row above verifies it is ≈ 0.

`frames/` (added with calibration) holds sample frames at block moments from the baked
720p file, showing that jersey numbers resolve at the shipped resolution.
