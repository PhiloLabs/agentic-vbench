---
title: Task Spec Card
summary: The structured header every video-understanding task must fill in and prove.
read_when: Reviewing this task. Every field is a verifiable claim.
---

# Task Spec Card

```yaml
task: agentic_vbench_understanding/lol-minimap-timeline-reconstruction

# 1. What kind of thinking does this task need?
#    understanding = compare/order/relate; reasoning = cause/cross-event inference.
#    Both economy fields are cross-event inferences over the whole game, not perceptions.
cognitive_level: reasoning

# 2. Which modalities are REQUIRED (not just present)?
modalities_required:
  video: "Every event (champion death, turret destruction, epic-monster take) is observable only on the minimap; identity comes from champion portraits and turret icons. No HUD/killfeed/clock is shown."
  audio: "not used — the map render has no audio (stripped by construction)"

# 3. The exact question and output schema.
question: "From the map view of one full ~39.5-min League of Legends game, reconstruct every key event in chronological order as (game_clock_s, type, entity, minute_gain, leader_before)."
output_schema: "JSON {\"events\":[{game_clock_s:int seconds, type:champion_kill|tower_kill|epic_monster_kill, entity:str, minute_gain:blue|red|equal, leader_before:blue|red|equal}]}; entity = dead champion name | \"{team}_{lane}_{tier}\" turret | drake element|elder|baron; full-tuple match within 3 s, scored by F1."

# 4. Evidence chain: the specific moments the answer depends on (>=2 far-apart).
evidence:
  - "t=196s, video, first champion death (Taliyah) — identity from a portrait vanishing"
  - "t=826s, video, first turret fall — a fixed structure icon permanently disappearing"
  - "t=1731s (28:51), video, ocean drake take — objective secured while blue leads overall, yet red nets more that minute; only whole-game state separates minute_gain (red) from leader_before (blue)"
  - "t=~2373s, video, late-game tower/baron sequence — cumulative tower/control state determines leader_before for the final events"

# 5. Ground truth: value, source, tier, verification.
ground_truth:
  source: "game's Live Client Data API (/liveclientdata/eventdata) captured during local .rofl playback; objectives from the client's post-game match timeline; economy from the client's per-minute gold-lead series (thresholds 300/1000)"
  tier: "machine-truth (client-internal structured records) with a second independent annotator for the 9 objective events"
  verification: "champion_kill count 86 and tower_kill count 16 from the API event stream match the .rofl end-game aggregate (statsJson CHAMPIONS_KILLED=86, TURRETS_KILLED=16) exactly — two-independent-field cross-validation; DRAGON_KILLS=6 and BARON_KILLS=3 match the post-game timeline"

# 6. Scorer: deterministic code only.
scorer:
  metric: "F1 over events; a TP requires (type, entity, minute_gain, leader_before) all equal AND |Dt| <= 3 s; greedy 1:1 match. Any wrong field (incl. an economy call) voids that event."
  oracle_reward: 1.0
  null_reward: 0.0  # measured: empty submission -> 0.0

# 7. Difficulty: measured with a real strong-agent run.
difficulty:
  strong_agent_reward: 0.058  # gpt-5.6-sol @ Codex CLI 0.130.0, best of three
  tool_call_turns: 74  # gpt-5.6-sol; opus-4.8 ran 141 turns
  agent_model: "gpt-5.6-sol (Codex CLI 0.130.0); also opus-4.8 (Claude Code 2.1.215) = 0.010 / 141 turns; Gemini 3.1 Pro (Antigravity CLI 1.1.3) = 0.009 / 34 round-trips"

# 8. Anti-shortcut ablations: run a strong model under each degraded input.
#    Every one must score <= 0.15. TODO: run these measured ablations before the PR.
anti_shortcut:
  single_frame: "not on any frame — minute_gain spans a full minute and leader_before the whole prior game, so a single frame cannot yield a full tuple"
  video_only: "n/a — the map render has no audio by construction; the full task is video-only"
  audio_only: "0.0 — no audio exists (stripped by construction)"
  no_media: "not recallable — private game with no public timeline; the schema (111 specific entities + two economy calls each) is not guessable from the prompt alone"
  frame_dump_no_tools: "agency required — a full tuple including both economy fields needs seeking across the whole video, not pasted frames"

# 9. Input media.
input:
  url: "https://huggingface.co/datasets/iTheresaApocalypse/agentvbench/resolve/main/lol_minimap/minimap_vod.mp4"
  sha256: "9d778f43930ff1d5d9938429f2e87c36e21ea9234eddf2168485de67dd7ab743"
  length_min: 39.5
  resolution: "700x692 (2x upscale of a 350x346 minimap crop from a 720p capture)"
```

## Prompt-writing rules (the agent-facing instruction)

- One task per task: reconstruct the event timeline (with economy). No compound asks.
- Every scored term is defined: `type`, `entity` per type (champion name / `{team}_{lane}_{tier}` / drake element|elder|baron), `minute_gain` (>=300 gold net in the event's game-minute), `leader_before` (>=1000 gold lead at the prior whole minute), inhibitors ignored.
- Closed vocabularies given in full: the six drake elements, `elder`, `baron`, the four tiers, the four lanes, `base_nexus`.
- Exact output schema and deliverable path (`/workspace/output/solution.json`) stated.
- The scoring method, tolerance, and ground-truth source are NOT described to the agent.
- No trick wording: everything scored is stated in `instruction.md`.
