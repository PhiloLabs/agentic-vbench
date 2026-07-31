# Task Spec Card

```yaml
task: agentic_vbench_understanding/cs2-trade-kill-ledger

cognitive_level: understanding

modalities_required:
  video: killer/victim identity and kill timing exist only in the footage; there is
         no killfeed, scoreboard, minimap, or timer, and no public record of this
         private match
  audio: present in the renders but not required; audio leaks firefight timing yet
         cannot attribute identity (audio_only ablation must sit in the null band,
         else audio is stripped)

question: For every kill in the match, report when it happened, in which round, who
          killed whom, and whether the kill was traded within 5.0 seconds by the
          victim's team.
output_schema: >
  {"ledger": [{"t": <seconds, |Δt| <= 5 s>, "round": <int, 1-based>,
   "victim": "P1".."P10", "killer": "P1".."P10", "was_traded": <bool>,
   "trader": "P1".."P10" | null}]}  - one entry per kill

evidence:
  - t≈21s, video, first kill of round 1 (P7 kills P2): resolving it needs the
    killer's POV plus the victim's POV at the same instant
  - t≈191s, video, posthumous-grenade self-trade in round 3: the was_traded flag
    depends on a grenade thrown seconds before the trader's own death
  - t≈1921s, video, final-round kills: correct round numbering requires having
    tracked every round boundary across the whole match
  - every was_traded field, video, depends on a 5-second forward window after the
    kill, so no single moment answers any entry

ground_truth:
  source: the match's own .dem replay (the CS2 server's event log), parsed with
          demoparser2 by provenance/build_gt.py; every field is a deterministic
          transform of the log
  tier: machine-truth
  verification: internal consistency asserts (10-player roster closure, at most one
                death per player per round, no ambiguous match pairs within scorer
                tolerance) plus build-time assert verifier(oracle)==1.0 and
                verifier(empty)==0.0; post-render, random GT kills are spot-checked
                against the killer's POV at the stated t

scorer:
  metric: F1 over full tuples; a prediction pairs one-to-one with a GT kill by
          (victim, killer, |Δt| <= 5 s) and is a TP only if round, was_traded, and
          trader also agree
  oracle_reward: 1.0
  null_reward: 0.0

difficulty:
  strong_agent_reward: pending calibration (target < 0.10)
  tool_call_turns: pending calibration (target > 50)
  agent_model: Antigravity / Codex / Claude Code, per family requirement

anti_shortcut:
  single_frame: pending render (structurally ~0: was_traded is a 5 s window)
  video_only: n/a as primary; audio is auxiliary
  audio_only: pending render; stress-tested explicitly, stripped if not in null band
  no_media: pending (structurally ~0: private match, schema not guessable - 169
            4-plus-field tuples)
  frame_dump_no_tools: pending render

input:
  url: pending render re-host (tar of P1.mp4..P10.mp4, pinned URL)
  sha256: pending
  length_min: ~33 per POV (x10 time-aligned POVs of the same match)
  resolution: 720
```
