# cs2-trade-kill-ledger

Reconstruct the complete trade-kill ledger of one full CS2 competitive match from
ten time-aligned, HUD-stripped first-person POV renders. Proposal and maintainer
review: issue #52.

## Provenance

The source is the author's own private matchmaking demo (`.dem`, de_cache, MR12,
23 rounds, 169 player-vs-player kills). The `.dem` is the game server's own event
log, so the ground truth is fully mechanical: `provenance/build_gt.py` parses it
with `demoparser2` and derives every ledger field deterministically, then asserts
`verifier(oracle) == 1.0` and `verifier(empty) == 0.0`.

Conventions fixed in code (not left to interpretation):

- **Kill**: a player death caused by another player. The match's one `worldent`
  death (fall damage) is excluded; there are no suicides or teamkills in this demo.
- **Round number**: boundary-based - `1 + count(round_officially_ended < tick)` -
  so aftermath kills (exit frags) stay in the round just played, and the final
  round, which has no `officially_ended` event, still counts.
- **Trade rule**: a kill is traded iff the killer dies within 5.0 s, in the same
  round, to any player on the victim's team, *including the victim themselves via
  posthumous utility*. This is not hypothetical: round 3 of this demo contains a
  real posthumous-grenade self-trade (P3 dies, then P3's already-thrown HE kills
  the killer 0.28 s later).
- **Timestamps**: `t = (tick - t0_tick) / 64.0`. Until the render exists, `t0` is
  the `round_announce_match_start` tick; after rendering, re-run
  `build_gt.py --t0-tick <measured>` so `t` is exact video time, and spot-check two
  or three kills visually.

The `.dem` never ships with the task: it is not in the image, not reachable from
it (`allow_internet = false`), and not committed (see `.gitignore`). It can be
shared privately with maintainers for verification.

## Privacy

The other nine players' identities are anonymized. `provenance/player_map.json`
(steamid -> P-label) is gitignored; only `P1`-`P10` labels appear in the ledger,
the instruction, and the renders. Labels are deterministic: each starting team
sorted by steamid, team 2 -> P1-P5, team 3 -> P6-P10.

## Camera coverage and identity (maintainer points 1 and 3 on #52)

The render is ten first-person POVs, not one spectator camera. This makes camera
coverage structural rather than a per-kill check: **the victim's own video shows
their death by construction** (a player is in first person until the moment they
die), and direct-fire kills are visible in the killer's video too. The one nuance
is utility: for a grenade kill the killer's video shows the throw, not necessarily
the impact - the demo's round-3 posthumous-grenade kill is the concrete case, and
it remains recoverable (the throw in P3's video, the death in P8's). Identity is
the video index (`P<k>.mp4` = player `P<k>`), so no name-label compositing is
needed and there is no occlusion rule to define - the original spectator-camera +
composited-labels design is retired.

Post-render checklist (before calibration):

1. All ten POVs rendered over the **same tick range** (start tick 1441, CSDM +
   HLAE, `showOnlyDeathNotices` on with death-notice duration 0) at 720p30, music
   kit and player voices disabled.
2. Renders start at tick 1441 = the GT's `t0_tick`, so no re-run is needed; verify
   3 random GT kills against the media at the stated `t` anyway.
3. Spot-check 15 GT kills for recoverability from the media (victim POV always;
   killer POV for direct fire; throw visible for the grenade kills) - biased
   toward the weakest observability cases (grenade impacts, smoke kills,
   wallbangs, the posthumous trade) rather than a uniform random draw.
4. Run the audio ablation (below); if audio alone scores above the null band,
   strip audio from the renders and document it.
5. Upload `P1.mp4..P10.mp4` to an archive.org item (direct per-file download
   URLs, the family's accepted host); fill the base URL and per-file SHA256s in
   `environment/Dockerfile`.

Calibration plan (per the family README, post-#57): iterate with **Codex
(GPT 5.6 Sol) first**, then Antigravity (Gemini 3.5 Flash / 3.1 Pro) and Claude
Code (Fable 5 / Opus 4.8). One **raw** trajectory per agent (stream-json / session
log; summaries are not auditable), models named in `scores.md`'s performance
table, runs in an isolated env matching the shipped image. Ablations
(`no_media`, `single_frame`, `audio_only`, `frame_dump_no_tools`) are **measured
runs**, never argued numbers. Audit the Gemini trajectories for server-side
search grounding; the match is private so there is nothing to find, but the
audit is still recorded.

Hardening lever, decided in advance: with per-entry F1, ~9 accurately
reconstructed kills reach ~0.10, so a focus-one-round strategy is the realistic
bar-breaker. If official calibration lands above 0.10, the pre-committed fix is
to tighten the time tolerance (5 s -> 3 s) and, if still needed, add a scored
`weapon` field from a closed vocabulary - both raise per-kill difficulty without
changing the task's structure.

## Scoring

`steps/solve/tests/judge.py` (pure stdlib). Per maintainer guidance on #52,
matching is by `(victim, killer, |Δt| <= 5 s)` one-to-one - never by
`(round, index)` - so one missed kill cannot shift credit for a whole round. A
matched pair scores only if `round`, `was_traded`, and `trader` also agree;
reward = F1 over full tuples. The trade fields couple entries together: a missed
kill also corrupts the `was_traded` of its neighbours, so incompleteness
propagates. Diagnostics in `reward.json` separate kill-level matches from
full-tuple matches and break down per-field errors.

## Anti-shortcut ablations

To run post-render (recorded in `calibration/scores.md`): `no_media`,
`single_frame`, `audio_only` (CS2 sound leaks firefight timing but cannot
attribute killer/victim identity), `frame_dump_no_tools`. Recall is structurally
dead: private demo, no public record. HUD/killfeed/minimap/timer are removed by
construction.

## Rights

Code and verifier: Apache-2.0 (repo license). Video: CS2 gameplay footage used
under Valve's Video Policy - non-commercial, no separated game assets, music kit
disabled at record time. Copyright in the game imagery remains with Valve.
