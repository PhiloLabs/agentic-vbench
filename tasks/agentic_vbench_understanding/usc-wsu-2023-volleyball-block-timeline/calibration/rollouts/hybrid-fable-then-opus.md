# Resume-with-a-different-model experiment

Question: when a run is cut off partway, does resuming it with a different model land
anywhere near a clean run of that model? It matters here because Fable's run stopped
at 210 tool-call turns when that model's credit pool ran out, and it would have been
convenient to finish it with Opus and call the result Fable's.

Setup: Fable's interrupted session (210 turns, all of its frame work intact) resumed
with Opus 5, xhigh, across three legs totalling 137 further tool-call turns.

| run | score | events submitted |
|---|---|---|
| Opus 5, fresh, clean workspace | 0.0 | 1 |
| Fable 210 turns then Opus 5 | **0.0** | 3 |

The hybrid submitted three block points and matched none — not even the rally
anchors, so its three were the wrong rallies rather than the right rallies with wrong
names. Inheriting 210 turns of another model's exploration did not move the outcome.

Two things this settles for the calibration:

1. Fable's interrupted run stays **unscored**. Finishing it with another model would
   not have recovered a Fable number; it would have produced a third 0.0 wearing
   Fable's name.
2. Both models, independently, concluded that jersey numbers at the moment of contact
   are unreadable — the hybrid's closing note says "~10 px tall and motion-blurred,
   and 5x magnification did not recover them". Both are right about the rally and
   wrong about the task: the numbers are legible, but in the post-point close-up, not
   at contact. See `../observability/`.

Method note, in case it is useful to anyone running similar experiments:
`claude --resume` restores the session's recorded working directory, so copying the
session file into a second project directory is not enough to isolate a resumed run —
the agent still writes into the original workspace. Isolating the conversation and
isolating the filesystem are separate problems. Here the conversation stayed at 210
turns, but the original workspace had to be restored afterwards by quarantining
everything the resumed agent wrote.
