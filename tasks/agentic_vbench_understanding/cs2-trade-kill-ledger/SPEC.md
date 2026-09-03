# Task Spec Card

```yaml
task: agentic_vbench_understanding/cs2-trade-kill-ledger

cognitive_level: reasoning

modalities_required:
  video: killer/victim identity, weapon, and kill timing exist only in the footage
         (no killfeed, scoreboard, minimap, timer); each trade episode must be
         assembled by correlating three players' synchronized POVs
  audio: present and useful for locating firefights; not sufficient alone (identity
         and weapon come from vision) - audio_only ablation must sit in the null band

question: Reconstruct every trade episode in the match - an initial kill A->B plus
          the earliest revenge kill of A by a teammate of B within 5.0 s in the same
          round - reporting for both kills the round, video time, killer, victim, and
          weapon.
output_schema: >
  {"trade_episodes": [{"round": <int>,
    "initial_kill": {"t": <s>, "killer": "P1".."P10", "victim": "P1".."P10", "weapon": <enum>},
    "trade_kill":   {"t": <s>, "killer": "P1".."P10", "victim": "P1".."P10", "weapon": <enum>}}]}
  where trade_kill.victim == initial_kill.killer

evidence:
  - initial killer's POV, video: shows kill 1 (viewmodel weapon + target dropping)
  - initial victim's POV, video: confirms who died and exactly when (their own death)
  - trader's POV, video: shows kill 2 within 5 s
  - the three POVs are far-apart video sources that must be joined on one shared clock
  - the 5-second same-round relation couples two moments, not one

ground_truth:
  source: the match's own .dem replay (the CS2 server's event log), parsed with
          demoparser2 by provenance/build_gt.py; kills, teams, weapons, and the
          trade relation are deterministic transforms of the log
  tier: machine-truth
  verification: internal consistency asserts (10-player roster closure, two teams of
                five, at most one death per player per round, every weapon in the
                declared vocabulary, no ambiguous kill pair within 2x the judge
                tolerance) plus build-time assert verifier(oracle)==1.0 and
                verifier(empty)==0.0; independently cross-checked against the CSDM
                render-side parse (provenance/csdm_crosscheck.json)

scorer:
  metric: F1 over trade episodes; a predicted episode matches a GT episode under
          maximum-cardinality bipartite matching iff round matches, and for BOTH
          kills killer/victim/weapon match exactly and |dt| <= 2.0 s
  oracle_reward: 1.0
  null_reward: 0.0

difficulty:
  strong_agent_reward: pending pilot calibration (target < 0.10)
  tool_call_turns: pending (target > 50; ~30 episodes over 10x32 min of aggregate video)
  agent_model: Codex GPT 5.6 Sol first, then Antigravity and Claude Code
  note: >
    with 30 GT episodes, 1 fully-correct episode = F1 0.065 and 2 = 0.13, so < 0.10
    requires a strong agent to complete fewer than ~1.5 whole episodes. A single-POV
    "own timeline" variant was measured too easy (Codex 0.31), which is why the task
    scores only the identity-bearing, cross-POV trade episodes.

anti_shortcut:
  single_frame: pending (structurally ~0: an episode spans a 5 s window across POVs)
  video_only: n/a as primary; audio is auxiliary
  audio_only: pending; audio locates firefights but cannot attribute identity/weapon
  no_media: pending (structurally ~0: private match, schema not guessable - 30
            episodes each with round + 4 identities + 2 weapons + 2 timestamps)
  frame_dump_no_tools: pending

input:
  url: pending render re-host (archive.org item, P1.mp4..P10.mp4)
  sha256: pending per-file
  length_min: ~32 per POV (x10 time-aligned POVs of the same match)
  resolution: 720
```
