# CALIBRATION RUNBOOK — read this and follow it exactly

**You are an AI agent acting as the ORCHESTRATOR.** Your job is to run an
official calibration of a video-understanding benchmark task using a *separate*
solver agent (Codex or Gemini) and report its score. Follow the numbered steps.

## The one rule that makes the result valid

**You do NOT solve the task yourself.** Do not watch the video, do not open the
answer key, do not write `solution.json`. You only: (1) stage an isolated
workspace, (2) launch a *fresh* solver process that works from the video alone,
(3) grade and audit what it produced. If you answer the task yourself, the
result is worthless. Never pass any hint, answer, or file content to the solver
beyond what `stage_workspace.sh` copies.

## What is being measured

A strong agent, watching a silent, scoreboard-free lacrosse broadcast, tries to
reconstruct the ordered goal ledger. A valid task keeps the strong agent **below
0.10** while a careful human oracle scores 1.0. We already measured Claude Opus
4.8 at 0.0339 over 1263 tool calls. You are adding the Codex and Gemini rows.

## Prerequisites (check first; if any is missing, stop and tell the human)

- `ffmpeg`, `python3`, `shasum`, `zip`/`unzip` on PATH.
- The video `materials/game.mp4` is present. (If it is missing, the human must
  copy it in — its SHA-256 is in `materials/game.mp4.sha256`.)
- For **Codex**: the `codex` CLI installed and logged in.
- For **Gemini**: the `agy` (Antigravity) CLI installed and logged in.

All scripts below live in `calibration/runpack/`. `cd` there first.

## Step 0 — verify the video (bundled, ~1 GB)

The processed task video `materials/game.mp4` is included in this kit. Confirm
it is intact:

```
cd calibration/runpack
./fetch_video.sh
```

If the bundled file is present and its SHA-256 matches `materials/game.mp4.sha256`
this prints "already present, official hash verified" and does nothing else.
(Only if the video is missing does it rebuild it from the public YouTube source
via the official mask+mute recipe, needing `yt-dlp` + `ffmpeg`; a reproduced
file won't be byte-identical, so the script re-pins the local hash and prints a
NOTE — record that in `scores.md`.) Do not proceed until it prints `OK`/verified.

## Run Codex (GPT-5.6 Sol)

```
cd calibration/runpack
./stage_workspace.sh codex     # isolates a key-free workspace, verifies video hash
./run_codex.sh                 # launches the solver in the background
```
Then WAIT for it to finish (can take 1–3 hours; keep the machine awake and
online). When `/private/tmp/avb_calib_codex/output/solution.json` exists and the
process has exited:
```
./audit_and_grade.sh codex ../rollouts/codex_gpt56sol.jsonl
```

## Run Gemini (run BOTH models if you can)

```
cd calibration/runpack
./stage_workspace.sh gemini
./run_gemini.sh gemini-3.5-flash     # wait, then audit; then repeat for 3.1-pro
./audit_and_grade.sh gemini ../rollouts/antigravity_gemini-3_5-flash.log
```

## If a CLI flag is wrong for your installed version

Adapt the launch command, but you MUST preserve these solver requirements:
- The solver's working directory is the staged workspace only
  (`/private/tmp/avb_calib_codex` or `_gemini`). It reads only files there.
- **All web search / web fetch / search-grounding is DISABLED** at every level
  the CLI offers (flag, config, and the in-workspace `AGENTS.md`/`GEMINI.md`
  already ban it).
- The solver writes `output/solution.json` in that workspace.
- The full raw trajectory is saved to `calibration/rollouts/`.

## Anti-cheat mechanisms (already built in — do not remove)

1. **Isolated workspace.** `stage_workspace.sh` copies only the 4 solver-visible
   files, verifies the video SHA-256, and hard-fails if any answer-key / GT /
   verifier file is present. The answer key never enters the solver's reach.
2. **No network / no lookup.** `AGENTS.md` and `GEMINI.md` in the workspace, and
   `instruction.md`, forbid web use and forbid identifying the real game.
   `run_codex.sh` also disables the web-search tool via config.
3. **Gemini conversation-store wipe.** `run_gemini.sh` moves Antigravity's
   cross-conversation memory aside before launching, so no prior session leaks.
4. **Trajectory cheat-scan.** `audit_and_grade.sh` greps the raw trajectory for
   web/search markers, real-game identity terms (team/venue names), and
   answer-key access, and reports tool-call count.

## Reporting a result as VALID requires ALL of:

- reward **< 0.10** (printed by `audit_and_grade.sh`),
- **> 50** tool calls (natural, not padded),
- cheat-scan shows **no real web lookup** (a web search or box-score fetch) and
  **0 answer-key access**.

**Identity is not a disqualifier.** The team names (MICHIGAN / HOPKINS) are
visible on the jerseys, so a solver may read and even *name* them — that is NOT
cheating and does NOT void the run. Naming the game yields nothing on its own
(measured **no_media = 0.0**); a run that named the game and still scored ~0 is
positive evidence that recall does not help. The disqualifiers are an actual
external **lookup** or answer-key access, both auditable in the trajectory.
(False-positive watch: the solver's own model API endpoint — e.g.
`chatgpt.com/backend-api` — is inference, not a lookup; inspect the URLs.)

Telltale for *hidden* recall (the real risk): if the ledger's team-split/score
is suspiciously close to the real game while scorers/order are wrong in very few
tool calls, the run may have answered from memory with no tool trace → flag for
manual review.

## What to hand back to the task owner

For each harness: the printed reward, the tool-call count, the exact CLI version
and model id, and the raw trajectory file from `calibration/rollouts/`. Append a
row to `calibration/scores.md`.
