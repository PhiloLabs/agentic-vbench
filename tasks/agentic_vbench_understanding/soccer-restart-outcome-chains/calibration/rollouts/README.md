# Rollouts

What every calibration run left behind, sanitized for the repository. The numbers these
files back are in `../scores.md`, and `../verify_scores.py` recomputes each of them from here.

## Layout

| files | what they are |
|---|---|
| `<arm>.jsonl` | the arm's trajectory. For Codex it is the session record the CLI keeps itself, with the `--json` event stream beside it as `codex-events.jsonl`. For Claude Code it is also the session record, with the `stream-json` output beside it as `claude-events.jsonl`. For Antigravity it is agy's `transcript_full.jsonl` for the one session it ran. |
| `<arm>-solution.json` | what the arm submitted |
| `<arm>-reward.json` | the shipped judge's output for that submission |
| `<arm>-manifest.json` | how the arm was run: model, effort, harness version, budget, resources, argv, prompt digest, egress checks, and what was already running |
| `<arm>-audit.txt` | `../audit_trajectory.py` run on the shipped trajectory |
| `not-reported/antigravity-1s-attempt/` | an Antigravity attempt on this contract that ended without an answer after the host slept, with its trajectory, manifest and audit |
| `superseded-2s-tolerance/` | the ledger runs made while the tolerance was 2 s, graded by the archived scorer in `../../provenance/superseded-2s-tolerance/` |
| `superseded-restart-contract/` | every run made against the first contract, which scored restarts only: the Codex run whose 0.3529 replaced that contract, the runs under the first budget, the runs stopped when the budget or the contract changed, and the first Codex and Antigravity attempts, which failed on the harness. They are graded by the archived scorer in `../../provenance/superseded-restart-contract/`, and `../scores.md` explains each. |
| `oracle-reward.json`, `empty-reward.json`, `oracle-empty-manifest.json` | the oracle and an empty submission, graded inside the image by `../run_oracle_empty.py` |
| `antigravity-hook-probe.json` | the result of `../probe_antigravity_hook.py`, which checks that the subagent hook holds |

## What differs from the raw files

Three things. Base64 image blobs of 2000 characters or more, including those inside data
URLs, are replaced by a placeholder that records their length. Local absolute paths are
rewritten to their in-image form. Email addresses, which a CLI can record for the account it
is signed in with, become `<email>`. Every command, tool call and word is left as the agent
produced it, so a turn count can be recounted here instead of taken from a table. The frames
the agents looked at are not included; each trajectory holds the command that cut them from
the pinned video.

## Re-checking a row

```bash
python3 ../../steps/solve/tests/judge.py --solution codex-solution.json \
    --reward-json /tmp/reward.json --reward-txt /tmp/reward.txt
python3 ../audit_trajectory.py --run-dir /workspace --rollout codex.jsonl
```
