# Calibration — minecraft-gameplay-ledger-s1

## Shipped: v38 (game_v38.mp4), timestamp-windowed metric

`game_v38.mp4`, sha256 `110f1232…d1b0e60a`, 238.5 min, **1995 events** (355 mine / 1501 place /
139 kill), 41 distinct block/mob types, 8 biomes ×9 laps, 27 structures (cabin with a full gable
roof whose timber rotates per lap, well, watchtower) + a staircase mine, 1280×720 @ 25 fps, no audio.

**Scorer:** `reward = 0.85 · F2(action,target) + 0.15 · weapon-F1 over aligned kills` (the weapon
weight applies only when the render has kills; v38 has 139). Alignment is an **order-preserving LCS
on `(action,target)` within a ±10 s time window** — a predicted event aligns only if its `t` is
within 10 s of the true video time. Recall-weighted (β=2).

## Strong-agent calibration lineup

The audit record for each row is the agent's **full raw session transcript** (every tool call, output,
turn, and frame; only secrets + home paths redacted), hosted immutably on HF and pinned by revision
with whole-file SHA256 in `rollouts/README.md`. Reward/solution dumps are alongside on HF (not in git).

| harness (version) | model | reasoning | reward | tool-call turns | trajectory |
|---|---|---|---|---|---|
| Codex CLI (0.145.0) | gpt-5.6-sol | xhigh | **0.0196** | 247 | raw archive (see `rollouts/README.md`) |
| Claude Code CLI (2.1.241) | claude-opus-4-8 | extended thinking | **0.0079** | 94 | raw archive (see `rollouts/README.md`) |
| Gemini CLI (0.57.0) | gemini-3.5-flash | default | **0.0031** | 408 | raw archive (see `rollouts/README.md`) |

All measured on the shipped v38 video + shipped scorer; every agent is far under the family's
<0.10 strong-agent bar. Codex was also run a second time (0.0105), so the Codex number is
run-dependent in the 0.01–0.02 band. The Gemini row uses **Gemini CLI** with the reviewer's named
`gemini-3.5-flash` model — the Antigravity IDE cannot run headless on our compute node, so the CLI is
the reproducible path to that model. Rollout dumps (solution.json + reward.json) on HF, pinned to an
immutable revision (not mutable `main`; trajectory SHA256s in `rollouts/README.md`):
<https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/39f1b933102acb3e52348752eb736b31c4c9d50b/minecraft-gameplay-ledger-s1/calibration>

## Anti-shortcut ablations (shipped scorer)

| submission | reward | notes |
|---|---|---|
| oracle | **1.0000** | harness path (`solve.sh` → `judge.py`); verified |
| correct multiset, order shuffled | 0.024–0.047 | LCS order + time window defeat it |
| correct multiset, random times | 0.008–0.017 | time window defeats it |
| most-common token ×N (times spread) | 0.0469 | genuine shortcut, well under 0.15 |
| actions+times right, targets "stone" | 0.0192 | genuine shortcut, well under 0.15 |
| single frame / no media | 0.0 | check_task ablations |

**Why the timestamp window.** Under the earlier order-only LCS, a shuffled full multiset scored
0.216 — an artifact of repeated-token leniency (41 distinct types over 1995 events; identical tokens
match in any order). The ±10 s window pins each event to its place in the video, collapsing that to
~0.04 while the oracle stays 1.0. The map from event time to video time was spot-checked at both ends
of the 238-min video.

## Difficulty is recall-limited (event count is the lever)

The strong agent reconstructs a roughly fixed absolute number of events (~100–200) and covers a
smaller fraction as the ledger grows, so reward falls with event count:

| render | events | length | strong-agent reward | recall |
|---|---|---|---|---|
| v34 | 1005 | 95 min | 0.177 | 0.16 |
| v36 | 1135 | 120 min | 0.174 | 0.13 |
| v37 | 1431 | 150 min | 0.120 | 0.07 |
| v38 (order-only) | 1995 | 238 min | 0.070 | 0.05 |
| **v38 (timestamp, shipped)** | 1995 | 238 min | **0.020** | 0.003 |

n=1 per render; run-dependent. Full trajectories in `rollouts/`.
