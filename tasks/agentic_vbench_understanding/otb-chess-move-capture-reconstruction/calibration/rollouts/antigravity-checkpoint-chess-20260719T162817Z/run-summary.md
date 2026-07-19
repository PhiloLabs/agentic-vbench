# Checkpoint-Assisted Antigravity Rollout Summary

- Run id: `antigravity-checkpoint-chess-20260719T162817Z`.
- Agent: Antigravity CLI `1.1.1`, Gemini 3.5 Flash (Medium).
- Conversation id: `ad5ef0d2-2e7e-4401-a69c-6350e7dbca18`.
- Workspace: fresh local replacement-source workspace under
  `calibration_runs_v5`; no ground truth or earlier rollout artifacts were
  present.
- Prompt: canonical benchmark instruction with only `/workspace` rewritten to
  the fresh local path.
- Processed video SHA256:
  `b9839b0e67c02ffa4ae9a7662809b25a045f6feff9749844bb66eb19d6a99420`.
- Runtime: 6 minutes 15 seconds from the first request through final JSON
  validation.
- Reward: `0.0205` (`6/292` checks passed).
- Prediction: 8 of 104 expected plies, 1 of 26 expected capture events, and
  result `unknown` instead of `black_win`.
- Rollout length: 53 completed tool calls, above the `>50` long-horizon gate and
  below the externally enforced 75-call hard cap.
- Other agents: Codex and Claude were not run in this rollout.

## Checkpoint Enforcement

The canonical initial prompt contained no turn minimum, pacing hint, or
checkpoint instruction. The external wrapper interrupted at 45 completed tool
calls because no `output/solution.json` existed, then resumed the same
conversation with `checkpoint-message.txt`.

Antigravity did not obey that first checkpoint and continued analysis. The
wrapper interrupted again at 50 calls; one already in-flight edit completed,
bringing the count to 51. It then sent `hard-checkpoint-message.txt` in the same
conversation. Antigravity used one call to write the file and one to validate
it, finishing at 53 calls. The judge returned `0.0205`, below `0.5`, so the
rollout stopped under the requested policy.

This intervention makes the result checkpoint-assisted diagnostic evidence,
not a natural-prompt acceptance rollout.

## Result

The submission correctly identified the first four move identities
(`1.e4 e5 2.Nf3 Nc6`). Only the `Nf3` and `Nc6` timestamps also passed. It then
diverged with `3.Bc4 Nf6 4.d4 exd4`, reported one false capture, and did not
reconstruct the remaining game or Black's win.

## Protocol Caveats

Antigravity ran `pip install python-chess opencv-python`; pip used cached
packages and downloaded a NumPy wheel. This changed the host-side environment
relative to the task Dockerfile and violated the no-online-tools intent, though
the transcript contains no public-game lookup or ground-truth access. All
explicit analysis files stayed in the rollout workspace; Antigravity also read
its own internal asynchronous-task log under its CLI brain directory.

The full trajectory, both checkpoint messages, all response streams, submitted
JSON, score, and turn counts are archived beside this summary.
