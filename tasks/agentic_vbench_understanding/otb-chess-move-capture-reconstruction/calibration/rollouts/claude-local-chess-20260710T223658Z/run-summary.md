# Claude Code Rollout Summary

- Run id: `claude-local-chess-20260710T223658Z`
- Agent: Claude Code CLI `2.1.204`
- Launch mode: fresh local run with `--print --verbose --output-format stream-json --permission-mode bypassPermissions --dangerously-skip-permissions --no-session-persistence`
- Final status: failed before submission; Claude returned `You've hit your session limit · resets 8:30pm (America/Los_Angeles)`
- CLI exit code: `1`
- Claude result subtype: `success` with `is_error=true`, `api_error_status=429`
- Tool-call turns counted from assistant `tool_use` blocks: `351`
- Claude result `num_turns`: `367`
- Duration: `5158890 ms`
- Total reported Claude cost: `$25.1689403`

## Output

No `/output/solution.json` was produced. The judge scored the missing file as an unreadable/empty submission.

## Score

- Reward: `0.0`
- Checks passed: `0/297`
- Predicted moves: `0`
- Predicted captures: `0`
- Judge reason: `unreadable solution.json: [Errno 2] No such file or directory`

## Checker

The task checker passed the calibration gates for this failed strong-agent rollout:

- Oracle reward: `1.0`
- Empty baseline reward: `0.0`
- Claude reward: `0.0`
- Turn gate: `351 > 50`

## Qualitative Notes

Claude spent most of the rollout on visual grounding and board-coordinate calibration. It repeatedly pivoted among manual crops, homography fitting, coordinate-label inspection, full-video frame differencing, and pairwise frame comparison. Late in the run it claimed partial opening progress (`1.Nf3 Nc6 2.d4`) but did not assemble or write a final JSON answer before the Claude session limit stopped the run.
