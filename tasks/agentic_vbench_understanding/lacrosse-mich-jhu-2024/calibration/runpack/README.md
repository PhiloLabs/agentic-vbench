# Calibration run-pack — Codex (GPT-5.6 Sol) + Antigravity/Gemini

Everything needed to produce the two remaining official calibration rows.
Prereqs: `codex` CLI and `agy` (Antigravity) CLI installed and authed on this
Mac. Machine must stay on wifi with the lid open for each run (the scripts arm
`caffeinate` automatically). Claude row is already done (0.0339, 1263 calls).

## Procedure (per harness — codex shown; same for gemini)

```bash
cd tasks/lacrosse-mich-jhu-2024/calibration/runpack
./fetch_video.sh               # STEP 0: download+verify game.mp4 (set VIDEO_URL.txt first)
./stage_workspace.sh codex     # fresh clean workspace at /private/tmp/avb_calib_codex
./run_codex.sh                 # background run + caffeinate; note the pid
# ... wait for the pid to exit (a run takes 1-3 hours) ...
./audit_and_grade.sh codex ../rollouts/codex_gpt56sol.jsonl
```

For Gemini: `./stage_workspace.sh gemini`, then `./run_gemini.sh
gemini-3.5-flash` (and again with `gemini-3.1-pro` if available), then
`./audit_and_grade.sh gemini ../rollouts/antigravity_<model>.log`.

After each run, add a row to `../scores.md`: harness + version, exact model id,
reasoning effort, reward, tool calls, trajectory file. Keep the raw trajectory
(never summaries) — the PR requires it.

## Anti-cheat mechanism stack (why each exists)

| # | Mechanism | Threat it blocks |
|---|---|---|
| 1 | Workspace at `/private/tmp/avb_calib_*`, OUTSIDE any repo; stage script copies ONLY the four agent materials and hard-fails if any key/GT/verify file is present | answer-file theft (observed in the volleyball #54 thread) |
| 2 | `AGENTS.md` / `GEMINI.md` in the workspace: no network, no game identification, no recall of box scores, directory-only | model-side lookup; both CLIs read their rules file |
| 3 | Codex: `--sandbox workspace-write` (no command network) + `tools.web_search=false` | shell-level and tool-level web access |
| 4 | Gemini: conversation stores moved aside pre-run | cross-conversation memory leaking earlier sessions about this task |
| 5 | Media SHA-256 verified at staging | wrong/re-encoded video invalidating GT alignment |
| 6 | `audit_and_grade.sh` scans the raw trajectory for real **web-lookup** markers (web search / box-score fetch) and **answer-key access** — the actual disqualifiers | model-side lookup / answer theft. **Identity mentions are context, not a violation:** the team names are on the jerseys, so reading/naming them is fine (`no_media=0.0` proves identity alone yields nothing); only an external lookup or key access voids a run (false-positive watch: the model's own API endpoint is inference, not a lookup) |
| 7 | Telltale review: near-correct team-split with wrong scorers in FEW tool calls = answered from memory → VOID | search-grounding/recall that leaves no tool trace (the Gemini failure mode from #54) |
| 8 | Natural-effort check: >50 tool calls without prompt padding | the chess-PR #49 rejection pattern |

Reference bars: reward < 0.10 over 50+ natural tool-call turns, per harness.
Claude row for comparison: 0.0339 / 1263 calls / zero web attempts.

## If a run scores ≥ 0.10 or a scan hits

Do NOT discard silently. Record it in scores.md, audit the trajectory, and
diagnose: cheat (void, fix the leak, re-run) vs genuine capability (task needs
hardening — talk to the maintainers on the proposal issue before changing
anything). Every run ever executed gets reported in the PR.
