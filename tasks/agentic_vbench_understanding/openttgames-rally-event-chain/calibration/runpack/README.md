# Calibration runpack

Reproducible harness for the calibration numbers in `../scores.md`. Every scored
run happens **inside the frozen task image** so the agent sees exactly the shipped
libraries, and inside a restricted network namespace so the ground-truth source is
provably unreachable.

## Why this shape

The ground truth is derived from a public GitHub repository, so "the agent did not
look it up" has to be enforced, not asserted. Three independent layers do that:

1. **Container** — the run container is built from the frozen image and never has
   the repo mounted. `stage_workspace.sh` copies in only `game.mp4`, `instruction.md`
   and the harness rules file, re-verifies the media against the pinned SHA-256, and scans
   the whole filesystem to prove no reference, judge, or annotation file exists.
2. **Network** — `netgate.sh` holds a network namespace whose OUTPUT policy is
   DROP, with an allowlist of the endpoints a run genuinely needs. Run containers
   join a named gate's namespace with `--network container:$AVB_GATE` (default
   `avb-netgate`), so they inherit the policy without the frozen image being modified
   and without relying on any CLI honouring proxy environment variables. Separate
   gates can be brought up per harness and for the ablations, which is what the
   reported runs did: one run's install phase re-widens only its own allowlist and
   can never widen another run's while that run is being scored. `net_guard.sh` re-proves the blocks from
   inside the namespace before and after every run and logs the result.

   The allowlist is deliberate. A denylist keyed on resolved IPs cannot be
   complete: GitHub and the dataset host answer with different addresses on
   different lookups, so a host blocked at setup silently becomes reachable later.
   That was observed while building this runpack. Default-DROP inverts the failure
   mode — a rotated address breaks the run, which is visible, rather than exposing
   the ground truth, which is not.

   The gate runs in two phases. `up` additionally allows the Debian and npm hosts
   needed to install a CLI into the run container; `lock` drops back to the model
   endpoints alone and is called by every runner after install and before the
   scored run begins.
3. **Harness** — each CLI is additionally run with its own network and web-search
   restrictions (`--sandbox workspace-write` and `tools.web_search=false` for Codex,
   `--disallowedTools WebFetch,WebSearch` for Claude Code).

The model endpoint stays reachable: the agent harness cannot run without it. That
is inference, not lookup, and `audit_and_grade.sh` enforces the distinction on the
trajectory. Note that Gemini's Search grounding happens server-side and no network
policy can block it, which is why the trajectory scan and the telltale check exist.

Agent CLIs are installed into the *run* container at calibration time. They are
deliberately absent from the shipped image so that no harness is privileged.

## Use

```bash
./netgate.sh up
./calibrate.sh codex
./audit_and_grade.sh codex ../rollouts/codex_gpt-5.6-sol.jsonl

./calibrate.sh claude opus-4.8
./resume_claude.sh                 # only after a rate-limit interruption; see below
./calibrate.sh antigravity gemini-3.5-flash

./run_ablation.sh single-frame
./run_ablation.sh no-media
./run_ablation.sh frame-dump

./netgate.sh down
```

Authentication is harness-specific, and `stage_workspace.sh` stages only the
credential the harness being run actually needs -- never all three, so a Codex run
carries no Anthropic or Google material:

| harness | what the reported run used |
|---|---|
| Codex CLI | the staged `CODEX_HOME` login from `~/.codex/auth.json` (falls back to `OPENAI_API_KEY`) |
| Claude Code | subscription OAuth, piped from the macOS Keychain; falls back to `~/.avb_anthropic_key` only when no subscription login exists |
| Antigravity | API-key mode from `~/.avb_gemini_key` |

`AVB_ACCOUNT_AUTH=1` switches Antigravity to account (subscription) auth and adds the
profile-picture host its eligibility check needs. It is **diagnostic only and was not
used for any reported score**: in a container the subsystems that expect a desktop
keyring log "You are not logged into Antigravity" and retry hard -- 42 times in 90
seconds -- until the container is OOM-killed, while the main inference path keeps
working. The evidence is in `rollouts/aborted/oom-accountauth.*`.

## Reproducing the frame-dump contact sheets

`build_frame_dump_sheets.sh` rebuilds the 30 contact sheets the `frame_dump_no_tools`
ablation was given, from the pinned source media, and verifies every regenerated sheet
against `../ablations/ablation_frame-dump-notools_sheets.sha256`. It exists so the manifest
is checkable: a list of digests identifies the intended bytes but proves nothing on its own
without the bytes or a derivation. A clean run reproduces all 30 digests. No JPEG binaries
are committed to the repository.

## Resuming an interrupted run

`resume_claude.sh` continues a Claude Code run that a subscription rate-limit window cut
short. It re-enters the *same* conversation with `claude --continue`, in the same container
and workspace, so the result is two execution segments of one session rather than a second
agent inheriting a stranger's files. Its continuation prompt is one neutral sentence and
restates no part of the task.

It never runs `netgate.sh up` and never re-stages: `up` recreates the gate container, and
the run container borrows that gate's network namespace, so destroying it would break the
run's networking for good and take the intermediate work with it. Only `install` and `lock`
are used, both of which edit rules in place.

Turns from both segments must be summed when reporting, and both transcripts committed.

## Gates

| check | threshold |
|---|---|
| each agent reward | < 0.10 |
| tool-call turns | > 50 |
| each ablation reward | <= 0.15 |
| oracle / empty | 1.0 / 0.0 |
