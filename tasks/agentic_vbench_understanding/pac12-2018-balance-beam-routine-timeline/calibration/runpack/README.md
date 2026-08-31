# Fresh local calibration runbook

This runbook prepares the three required runs but must not be executed until
`../../annotations/status.json` says `complete`.

The runs use a clean local/offline path: each workspace is fresh, the exact
media bytes and harness versions are recorded, task web access is disabled, and
the native trace is auditable. As of 2026-08-27, the maintainer has not yet
answered the requested host-run exception. The task Dockerfile remains the
reproducible environment definition.

All commands below run from the repository root. Set these shell variables once:

```bash
task_root=tasks/agentic_vbench_understanding/pac12-2018-balance-beam-routine-timeline
repo_root="$(pwd)"
source_video="$repo_root/work/source/source.mp4"
artifact_dir="$repo_root/$task_root/calibration/rollouts"
```

## 1. Record tool versions

Save the unedited output of:

```bash
ffmpeg -version
ffprobe -version
codex --version
claude --version
agy --version
```

The source must hash to
`7dfc9e139254cc9480948af734988bdebc796c89c6e5d439055a248c251130cb`.

Before staging Claude, require `claude auth status` to report
`"loggedIn": true`. If it does not, complete `claude auth login --claudeai`
and check again. Store only the redacted `loggedIn`, `authMethod`, and
`subscriptionType` fields with the rollout; do not store account or
organization identifiers.

## 2. Stage one empty workspace per harness

`stage_workspace.py` refuses an existing workspace, refuses a pending
annotation gate, verifies the source digest, localizes only the canonical
`/workspace` path in the prompt, and writes the exact rendered prompt plus an
input manifest to the rollout directory.

Example for Codex:

```bash
python3 "$task_root/calibration/runpack/stage_workspace.py" \
  --source "$source_video" \
  --workspace /private/tmp/avb-pac12-codex \
  --harness codex \
  --artifact-dir "$artifact_dir"
```

Repeat with new paths and harness names `claude` and `antigravity`. Never
reuse a staged directory.

## 3. Start one non-resumable 90-minute process

The wrapper launches one process group, terminates the entire group at 5,400
seconds, writes exact command/timing metadata, and never invokes a resume or
continue command.

Codex:

```bash
python3 "$task_root/calibration/runpack/run_with_deadline.py" \
  --seconds 5400 \
  --cwd /private/tmp/avb-pac12-codex \
  --stdin-file /private/tmp/avb-pac12-codex/prompt.md \
  --output "$artifact_dir/codex-gpt-5.6-sol-xhigh.jsonl" \
  --stderr "$artifact_dir/codex-stderr.txt" \
  --metadata "$artifact_dir/codex-run.json" \
  -- codex exec --json --ephemeral --ignore-user-config \
  --skip-git-repo-check --sandbox workspace-write \
  --model gpt-5.6-sol --config 'model_reasoning_effort="xhigh"' -
```

Claude Code:

```bash
python3 "$task_root/calibration/runpack/run_with_deadline.py" \
  --seconds 5400 \
  --cwd /private/tmp/avb-pac12-claude \
  --prompt-file /private/tmp/avb-pac12-claude/prompt.md \
  --output "$artifact_dir/claude-code-opus-4.8-high.jsonl" \
  --stderr "$artifact_dir/claude-stderr.txt" \
  --metadata "$artifact_dir/claude-run.json" \
  -- claude -p __PROMPT__ --model claude-opus-4-8 --effort high \
  --output-format stream-json --verbose --include-partial-messages \
  --no-session-persistence --safe-mode --no-chrome \
  --permission-mode dontAsk \
  --allowedTools Bash,Read,Write,Edit,Glob,Grep \
  --disallowedTools WebFetch,WebSearch
```

Antigravity:

```bash
python3 "$task_root/calibration/runpack/run_with_deadline.py" \
  --seconds 5400 \
  --cwd /private/tmp/avb-pac12-antigravity \
  --prompt-file /private/tmp/avb-pac12-antigravity/prompt.md \
  --output "$artifact_dir/antigravity-console.txt" \
  --stderr "$artifact_dir/antigravity-stderr.txt" \
  --metadata "$artifact_dir/antigravity-run.json" \
  -- agy -p __PROMPT__ --model gemini-3.5-flash-high --effort high \
  --mode accept-edits --sandbox --dangerously-skip-permissions \
  --new-project --print-timeout 90m \
  --log-file /private/tmp/avb-pac12-antigravity/native-trajectory.txt
```

Do not add `--continue`, `--conversation`, `resume`, or `--resume` to any
command. Do not restart a timed-out or quota-interrupted run.

Codex uses its network-disabled workspace sandbox. Claude web tools are disabled
and Antigravity terminal sandboxing is enabled. Antigravity print mode cannot
show tool-confirmation prompts, so its command preapproves tool requests while
retaining terminal sandbox restrictions. In all three cases, the prompt also
forbids web or outside knowledge. Audit the native trajectory for any web tool,
URL fetch, or network-capable shell command; an offending run is invalid and
must not be published as calibration evidence.

## 4. Preserve outputs without rewriting

After each process exits, copy its workspace
`output/solution.json` verbatim into the rollout directory with the harness
name. For Antigravity, also copy `native-trajectory.txt` verbatim. Do not strip
inline images or edit paths in native logs. Run the verifier, count native
completed tool calls, then hash the prompt, input manifest, raw trajectory, raw
solution, and run metadata:

```bash
python3 "$task_root/calibration/runpack/hash_artifacts.py" \
  --output "$artifact_dir/codex-artifacts.json" \
  "$artifact_dir/codex-initial-prompt.md" \
  "$artifact_dir/codex-input-manifest.json" \
  "$artifact_dir/codex-gpt-5.6-sol-xhigh.jsonl" \
  "$artifact_dir/codex-solution.json" \
  "$artifact_dir/codex-run.json"
```

Repeat for Claude and Antigravity, including both the Antigravity native log and
console capture. Then update `../scores.md` with measured rewards, real
tool-call turns, exact versions, and artifact links.

## 5. Build the Antigravity publication derivative

Keep the native database, sidecars, brain archive, and diagnostic log untouched.
Generate the single public Antigravity trajectory from the preserved database:

```bash
python3 "$task_root/calibration/runpack/extract_antigravity_public_trajectory.py" \
  --database "$artifact_dir/antigravity-conversation.db" \
  --brain-archive "$artifact_dir/antigravity-native-brain.tar" \
  --output "$artifact_dir/antigravity-gemini-3.5-flash-high.public.jsonl" \
  --audit-output "$artifact_dir/antigravity-publication-redaction-audit.json"
```

The extractor opens SQLite with immutable read-only access, emits every step in
database order, links ordered tool requests and results, replaces provider
signatures and referenced media bodies with digest placeholders, redacts local
identity strings, and validates the result against the native rendered
transcript stored in the brain archive. Re-running it with unchanged inputs must
produce byte-identical JSONL and audit files.

For Codex JSONL, run `redact_jsonl_publication.py` with `--source`, `--output`,
and `--audit-output`. For Claude JSONL, add `--redact-image-bodies`. The script
preserves record structure and ordered identifier/tool-link values, replaces
local identity strings, replaces only the two recognized Claude image-body
fields, and rejects remaining identity, encoded-media, or credential
signatures. Originals remain the source of record and must stay locally
excluded from the compact publication set.
