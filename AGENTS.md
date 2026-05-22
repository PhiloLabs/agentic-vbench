# AGENTS.md

Telegraph style. Root rules only. Read scoped `AGENTS.md` before subtree work.

## Start

- Repo: `agentic-vbench`. Greenfield; conventions still forming — keep changes minimal and reversible.
- Replies: repo-root refs only, e.g. `src/foo.ts:80`. No absolute paths, no `~/`.
- Verify before deciding. Read source/tests/current behavior; do not assume APIs, defaults, or runtime from prior knowledge.
- This file is policy; `docs/` (when added) is explanation; code/config is the contract. Link across layers, never duplicate.
- Add new conventions/workflows here (or in a scoped `AGENTS.md`) — not in a code comment or commit message.
- New `AGENTS.md` in any subtree: add a sibling `CLAUDE.md` symlink (`ln -s AGENTS.md CLAUDE.md`).

## Map

- `tasks/` — Harbor task dirs, grouped into 4 family subdirs:
  - `tasks/agentic_vbench_repair/` — 18 `exp-*` audio/video repair tasks (audio / color / deblur / sr / swap / glitch / cut / disfluency).
  - `tasks/agentic_vbench_assembly/` — 18 video-assembly tasks (`agentic-vbench-assembly-task<N>`).
  - `tasks/agentic_vbench_sequencing/` — 28 video-ordering tasks (`agentic-vbench-sequencing-task<N>`).
  - `tasks/agentic_vbench_repurpose/` — 36 long-form-to-short-vertical repurpose tasks (per-task creative brief + LLM-judged rubric).
  Downstream tools resolve task names to paths via `scripts/_task_paths.py` (`task_dir(name)`, `all_tasks(family=…)`), so adding/renaming families means touching one file.
- `scripts/` — the Harbor wrapper. `install-harbor.sh` pins the Harbor CLI; `parallel_rollout.py` schedules `harbor run` across many tasks against either local Docker or Modal; `monitor_job.py` tails a running trial; `_task_paths.py` is the name→path resolver. Task-generation code (`build_*.py`, `create_agentic_vbench_*.py`, `_<family>_core.py`, `_judges/`, `scripts/v4/`) is **not** in the public tree — it lives offline in `~/Downloads/legacy_vbench/`. Tasks are evaluated using the verifier code baked into each task's `tests/judge.py` at build time; Harbor produces the per-trial `reward.json`.
- `docs/VERIFIER_DESIGN.md` — load-bearing doc for the verifier math (universal normalize-improvement).
- `jobs/`, `site/`, `logs/`, `experiments/` — runtime / local-only outputs (gitignored).
- Scoped `AGENTS.md` files: none yet. Add one when a subtree has rules that genuinely differ from root.

## Docs

- Every doc in `docs/` opens with YAML frontmatter — at minimum `summary:` (one-line description), `read_when:` (natural-language triggers for when this doc is relevant), and `title:`. Keeps the docs tree agent-navigable.

## Code

- Don't add features, abstractions, or "future-proofing" beyond what the task asks for.
- Default to no comments. Only comment non-obvious *why* — never narrate *what*.
- No backward-compatibility shims for code that has not shipped.
- Trust internal callers; validate only at external boundaries.

## Git

- Commit only what was asked. Stage specific files; avoid blanket `git add -A` / `git add .`.
- Never commit secrets, credentials, real personal data, or `.env` files.
- `main`: rebase on latest `origin/main` before push; no merge commits.
- New commits over `--amend` unless the user explicitly asks to amend.
- Never force-push, `git reset --hard`, delete branches, or skip hooks (`--no-verify`) without explicit ask.

## Risk

- Destructive or shared-state actions (force-push, dropping data, deleting unfamiliar files, sending external messages, publishing): confirm before acting, even if it slows the loop.
- When an obstacle blocks you, find the root cause. Do not bypass safety checks as a shortcut.

## Footguns

- (empty — populate as we hit real gotchas)
