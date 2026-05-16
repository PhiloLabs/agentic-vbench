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

- `tasks/` — Harbor task dirs (one per benchmark instance). `exp-*` are the v4 repair-benchmark tasks (20 active); `video-edit-bench-task-{5-4,7-3}-*` are the earlier Harbor-adapter prototypes (kept).
- `scripts/` — code that generates Harbor tasks (`build_<family>.py`) and runs the v4 scoring suite. Shared cores: `_<family>_core.py`. Per-family audio judges: `_judges/`. Original Harbor-adapter scripts (`generate_task5_4.py`, `generate_task7_3.py`, `install-harbor.sh`, `monitor_job.py`) live alongside.
- `scripts/v4/` — v4 verifier framework: universal normalize-improvement scorer + per-family judges (`judge_audio.py`, `judge_video.py`, `judge_passthrough.py`) + drivers (`recompute_all.py`, `recompute_oracle.py`, `validate_anchors.py`, `fix_oracle_solve_sh.py`).
- `docs/` — design rationale and historical reports. `docs/v4/V4_DESIGN.md` is the load-bearing doc for the v4 verifier math.
- `sources/`, `clips/`, `noise/`, `.models/` — raw inputs (gitignored; regenerable).
- `jobs/`, `site/`, `logs/` — runtime outputs (gitignored).
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
