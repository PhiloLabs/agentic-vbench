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

- Scoped `AGENTS.md` files: none yet. Add one when a subtree has rules that genuinely differ from root.
- Directory map will grow here as the repo takes shape.

## Docs

- When `docs/` is created, every doc opens with YAML frontmatter — at minimum `summary:` (one-line description), `read_when:` (natural-language triggers for when this doc is relevant), and `title:`. Keeps the docs tree agent-navigable from day one.

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
