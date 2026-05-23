# Contributing to AgenticVBench

Thanks for your interest. This repo is the source of truth for the **AgenticVBench v1.0** task suite and the thin `./avb` wrapper around [Harbor](https://www.harborframework.com/). Almost all contributions land via fork + pull request — read on for the shape.

## Ways to contribute

- **Bug reports** — open an issue with the smallest reproduction you can manage. For an agent run, include the `result.json` and `reward.json` from `jobs/<job-name>/` if relevant.
- **Documentation and clarity fixes** — typos, broken links, unclear sections in `README.md` / `docs/`. Open a PR; we don't require an issue first.
- **New agents** — the four vendor-native Harbor agents (`claude-code`, `codex`, `gemini-cli`, `opencode`) are already integrated. Other agents plug in through a small Harbor adapter; the contract lives in [Harbor's agents docs](https://www.harborframework.com/docs/agents).
- **Leaderboard submissions** — submit via the flow at [agenticvbench.com](https://agenticvbench.com/), not through a PR. PRs that just add scores won't be merged.
- **New tasks / families** — out of scope for v1.0. The task suite is frozen so leaderboard runs stay comparable. Larger task additions will roll into a future versioned suite.

## Dev workflow

1. Fork [`PhiloLabs/agentic-vbench`](https://github.com/PhiloLabs/agentic-vbench) on GitHub.
2. Clone your fork, branch off `main`:
   ```bash
   git clone https://github.com/<your-username>/agentic-vbench.git
   cd agentic-vbench
   git checkout -b fix/short-description
   ```
3. Install Harbor (see the `README.md` Quick start).
4. Make the change. Sanity-check with the free oracle smoke before opening a PR:
   ```bash
   ./avb run <some-task> -a oracle -e docker
   # reward.json → ≈ 1.0, no API cost
   ```
5. Commit with a clear message. We **squash on merge**, so commit history within the PR doesn't have to be tidy.
6. Push to your fork, open a PR against `PhiloLabs/agentic-vbench:main`. Fill in what you changed, why, and how you tested.

## What gets merged fast

- Small, targeted changes (one purpose per PR)
- A clear test plan in the PR description
- Doc + code changes split into separate PRs when both apply, unless they're tightly coupled
- Bug fixes with a reproduction included

## What slows things down

- Large refactors without prior discussion in an issue
- New dependencies (we keep the runtime surface intentionally small — `argparse`, `tomllib`, stdlib)
- Changes that touch task scoring or rubrics without paper-backed justification — these can invalidate leaderboard comparability

## Internal contributors

Members of the `PhiloLabs/dev` team can push branches directly to this repo and open PRs from them, no fork needed. Same review + squash-merge flow.

## Questions

Open an issue, or for sensitive matters email `research@philolabs.ai`.
