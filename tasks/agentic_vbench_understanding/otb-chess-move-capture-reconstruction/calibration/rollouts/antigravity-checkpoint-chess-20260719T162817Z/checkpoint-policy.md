# External Checkpoint Policy

- Send the canonical task instruction first, with only `/workspace` rewritten to
  the fresh local workspace path.
- Do not add a turn minimum, pacing hint, or checkpoint request to the initial
  task prompt.
- Count completed Antigravity tool calls from the full conversation transcript.
- If no `output/solution.json` exists at 45 completed tool calls, interrupt the
  active response and resume the same conversation with one checkpoint request:
  immediately serialize the current best valid answer and stop.
- Once the run exceeds 50 completed tool calls, score any checkpoint. If its
  reward is below `0.5`, stop the rollout.
- Never allow the combined conversation to exceed 75 completed tool calls.
- Record the intervention and classify the result as a checkpoint-assisted
  rollout rather than natural-prompt calibration.
