# AgenticVBench — agentic omni understanding

AgenticVBench has several **areas of focus**, and they are parallel, not sequential.
v1.0 is the **post-production** area (`agentic_vbench_repair`, `_assembly`,
`_sequencing`, `_repurpose`). This family, `agentic_vbench_understanding`, is the
**omni-understanding** area — the first community-built one. It does not modify the
frozen v1.0 post-production tasks; it stands on its own alongside them.

A task here gives an agent one or multiple real videos — with their audio, and
optionally additional files/context (images, documents, structured data) — and one
unambiguous question, and grades the answer with deterministic code. The answer is usually objective — a
count, an event, a time span, a yes/no — so scoring is clean and the task resists
contamination.

## Hard requirements (enforced by `tools/check_task.py`)

Every task in this family must satisfy all of these, and ships a filled-in **Spec
Card** (`TASK_SPEC.md`; copy it into your task folder as `SPEC.md`) stating each
claim so a reviewer can verify it.

- **Input video(s).** One or more real videos from a stable, downloadable source
  (archive.org or YouTube). A single-video task runs 10–300 minutes; a comparison
  task may instead use a pair (or a few) short clips, which are exempt from the
  length floor. At least 720p either way. Bake each at build time with a pinned URL
  and a SHA256 checksum.
- **Task prompt.** One clearly worded question with an explicit JSON output schema.
  No trick wording, no hidden requirements. Define every scored term; give any closed
  vocabulary in full; name the deliverable path; never leak the scoring method or the
  ground-truth source.
- **Scorer.** Deterministic code only (Python stdlib, or a small CV model). No VLM or
  LLM judge. Strict enough that guessing scores about 0.
- **Calibration (measured, not claimed).** Oracle scores 1.0; an empty/null
  submission ≤ 0.10; a strong current agent < 0.10; a real attempt takes > 50
  tool-call turns. Calibrate with Antigravity (Gemini 3.5 Flash, Gemini 3.1 Pro),
  Codex (GPT 5.6 Sol), and Claude Code (Fable 5, Opus 4.8), keeping one raw
  trajectory per agent (summaries can't be audited):

  ```bash
  claude -p "$(cat instruction.md)" --verbose --output-format stream-json > rollouts/claude.jsonl
  codex exec --json "$(cat instruction.md)" > rollouts/codex.jsonl
  agy -p "$(cat instruction.md)" --model gemini-3.5-flash --log-file rollouts/antigravity.log
  ```

  Document every run in `calibration/scores.md` as a performance table:

  | harness | harness version | model | reasoning | score | tool-call turns | trajectory |
  |---|---|---|---|---|---|---|
  | Claude Code | 2.1.210 | Fable 5 | xhigh | 0.03 | 733 | rollouts/claude.jsonl |

  Iterate with Codex (GPT 5.6 Sol) first — it is the most efficient — and once it
  meets the bar, also run the other two agents.
- **No shortcuts (ablation gate).** Under each degraded input a strong model must
  score ≤ 0.15: single frame; video-only and audio-only (for audio-visual tasks);
  no media at all (catches recall and guessable schemas); all-frames-pasted with no
  tools (proves agency matters).
- **Evidence chain.** The answer depends on at least two far-apart moments (and both
  modalities where applicable). Prefer understanding/reasoning questions over pure
  perception. Recall of famous footage and on-screen stat graphics must not be enough.
- **Ground truth by tier.** machine-truth (official structured records) > logged
  (the system's own signals) > human-verified (2+ annotators, all occurrence
  windows). Prefer the highest tier available.

## Common pitfalls (gathered from community reviews)

- **Answer key in the agent's image.** Keep ground truth verifier-side under
  `steps/solve/tests/` (only mounted for the verify step); `/baked` holds media only.
- **Simulated ablations.** Every anti-shortcut number must be a real measured run,
  not a constructed best-case submission.
- **Calibration outside the shipped environment.** Local runs are fine only in an
  isolated env with the image's exact libraries and the same harness + model versions.
- **Padded turn counts.** Prompt instructions like "use at least 51 turns" don't
  satisfy the gate — if the task finishes too fast, harden the task.
- **Unobservable ground truth.** Off-camera events, blurred-out graphics the answer
  depends on, or hidden state (official-scorer judgment calls) cap the ceiling below
  1.0 — verify every GT event is actually recoverable from the media.
- **Gemini shortcuts.** Gemini 3.1 Pro may fabricate an answer in a few tool calls;
  Gemini 3.5 Flash can fall back to Google-Search grounding *server-side*, which no
  container network policy can block. State the no-lookup/no-memory rule clearly in
  the system prompt and audit every raw trajectory before trusting a score.
- **Artifact bloat.** One raw trajectory per agent + `scores.md`; no `reward.json`
  dumps, binaries, or personal paths.

## The worked example

`gsw-cle-2018-finals-g4-three-point-timeline/` is a complete, calibrated task built to
the v1.0 Harbor layout. It bakes the full broadcast of 2018 NBA Finals Game 4 (1080p,
155 min, archive.org) and asks the agent to reconstruct the timeline of all 22 made
three-pointers — quarter, game clock, shooter, assister — scored by pure-stdlib F1.
Measured with headless Claude (Opus 4.8):

| check | result |
|---|---|
| input video | 1080p, 155 min (URL + SHA256 pinned) |
| oracle | 1.0 |
| empty / null | 0.0 |
| 22-entry guess | 0.0 |
| **strong agent (Opus 4.8)** | **0.0465** (2 of 22 threes fully reconstructed) |
| rollout | 78 tool-call turns |

An earlier version asked for the box score and a strong agent scored 0.64 by recalling
the famous game and reading on-screen graphics; the timeline redesign killed both
shortcuts. Prefer less-famous footage anyway.

## Task layout

```
tasks/agentic_vbench_understanding/<task-id>/
├── SPEC.md                       # the filled-in Spec Card (copy of TASK_SPEC.md)
├── task.toml                     # settings, resources, time limits, canary header
├── environment/Dockerfile        # base image + pinned deps; bakes the media
├── steps/solve/
│   ├── instruction.md            # what the agent reads + where to save output
│   ├── solution/solve.sh         # the oracle (works out the answer)
│   └── tests/{judge.py, test.sh} # deterministic scorer; writes reward.json
└── calibration/                  # the difficulty evidence (see below)
    ├── scores.md                 # per-agent score + rollout turns table
    └── rollouts/                 # one raw agent transcript per agent
```

### Task naming

There are no sub-domain folders — every task sits directly under
`agentic_vbench_understanding/`, so the **task id must be self-describing**. Use
lowercase words joined by hyphens, and lead with the subject so related tasks sort
together:

```
<subject>-<what-the-answer-reconstructs>
```

Examples:

- `gsw-cle-2018-finals-g4-three-point-timeline` — a specific NBA game; the timeline of made threes
- `pickplace-grasp-release-timeline` — a robotics pick-and-place; grasp and release events
- `witcher3-weapon-clipping-bug` — a Witcher 3 clip; the weapon-clipping bug and its window

Keep the id stable once the task merges — downstream tooling resolves tasks by id,
not by path.

## How to contribute (open a PR)

Read `TASK_SPEC.md`, then propose your idea first (in the community proposal agent or a
Task Proposal issue) so a maintainer can sanity-check the difficulty and long-horizon
fit before you build. Then:

1. **Build the task** — a real pinned video, the instruction prompt, the oracle, and the
   deterministic verifier (`tests/judge.py` + `test.sh`).
2. **Validate** with the checker:

   ```bash
   python3 scripts/understanding/check_task.py \
     --task-dir tasks/agentic_vbench_understanding/<task-id> \
     --video-url "<archive.org or youtube url>" \
     --oracle-reward <reward.json> --baseline-reward <reward.json> \
     --agent-reward <reward.json> --agent-turns <n> \
     --ablation-no-media <reward.json> --ablation-single-frame <reward.json> ...
   ```

3. **Calibrate against three agents.** Run the task end to end with **Antigravity**,
   **Codex CLI**, and **Claude Code CLI**, gather each agent's rollout, and grade it.
   Iterate on the prompt and verifier until the scores land below the 0.10 bar and the
   rollouts run long (> 50 tool-call turns). Keep the rollouts and a scores table under
   `<task-id>/calibration/` (one transcript per agent, plus `scores.md`).

4. **Open a PR** into `main` adding `tasks/agentic_vbench_understanding/<task-id>/`. The
   PR must include:
   - the **task prompt** (`steps/solve/instruction.md`),
   - the **verifier** (`steps/solve/tests/`) and the oracle (`steps/solve/solution/`),
   - the **agent rollouts** and the **scores for all three agents** (Antigravity, Codex,
     Claude Code), with rollout turn counts,
   - the filled `SPEC.md`.

A reviewer checks the PR against the requirements above, re-runs the oracle and a strong
agent, and reads the run for shortcuts before merging.

## To finish wiring the area

- [x] Register `agentic_vbench_understanding` in `scripts/_task_paths.py`.
- [ ] Backfill `SPEC.md` for the worked example.
- [ ] Add more calibrated tasks (a cross-modal audio+video task is the biggest gap).
