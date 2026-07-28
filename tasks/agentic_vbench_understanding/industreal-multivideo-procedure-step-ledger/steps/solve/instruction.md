# State-Transition Ledger Reconstruction

You are given seven silent egocentric videos at `/workspace/materials/A.mp4` through
`/workspace/materials/G.mp4`. Each shows a person assembling or maintaining the same
construction-toy car. Reconstruct the complete chronological ledger of every stable
assembly-state checkpoint across all seven videos.

Use `/workspace/materials/overview-of-states.pdf` as the visual dictionary for the
parts and correct assembly states. Use tools such as `ffmpeg` and `ffprobe` to seek,
sample, compare, and inspect the videos.

## What counts as a checkpoint

Track each component as absent, incorrectly installed, or correctly installed. A
checkpoint is anchored to the **earliest video frame on which one or more component
states have changed**. This is the assembly-state transition time, not the end of the
surrounding hand action:

- a correct-install event occurs on the first frame where the component is fully and
  correctly installed, including any required pin, screw, nut, or tightening;
- an incorrect-install event occurs on the first frame where the component has been
  installed in an incorrect state;
- a removal event occurs on the first frame where a previously correctly or
  incorrectly installed component is no longer mechanically attached, even if the
  person is still holding it or sets it down later.

For an `incorrect -> absent` transition, use that component's normal removal step ID
in `changes`.

If the exact transition is occluded by a hand, use the earliest frame where the new
component state can be confirmed. Do not wait for hands to leave the scene, the part
to be placed on the desk, the person to inspect the result, or the next action to
begin.

The component states visible at the first frame of a video are initial conditions,
not checkpoints. For example, do not emit a checkpoint merely because the base or a
completed assembly is already present at `00:00`.

Report `time_s` on the **absolute timeline of the original A--G video**, starting at
`0.0` seconds. Do not report a timestamp relative to a seeked subclip or extracted
window: if a subclip begins at 80 seconds and the transition is 4 seconds into that
subclip, report `84.0`, not `4.0`.

A single state transition can change multiple components at once. Submit one
checkpoint containing every applicable step ID in `changes`, not separate rows with
the same timestamp.

Include all of the following:

- correct installations;
- incorrect installations;
- removals of correctly installed components;
- removals of incorrectly installed components;
- repeated removals and reinstallations.

Do not record intermediate hand motions, picking up a loose part, or merely touching
or aligning a component before its state changes. Timestamps should be accurate
within 2 seconds of the state-transition frame defined above.

## State vector

Every checkpoint must include `state_after`: the complete 11-component state after
all changes at that checkpoint. Use `-1` for incorrectly installed, `0` for absent,
and `1` for correctly installed. The vector always uses this order:

| Index | Component |
|---:|---|
| 0 | base |
| 1 | front chassis |
| 2 | front chassis pin |
| 3 | rear chassis |
| 4 | short rear chassis |
| 5 | front-rear chassis pin |
| 6 | rear-rear chassis pin |
| 7 | front bracket |
| 8 | front bracket screw |
| 9 | front wheel assembly |
| 10 | rear wheel assembly |

Report all 11 entries, including components that did not change at that checkpoint.
The values must describe the stable physical state immediately after the transition.

## Closed step vocabulary

| ID | Procedure step |
|---:|---|
| 0 | Install base |
| 1 | Incorrectly install base |
| 2 | Remove base |
| 3 | Install front chassis |
| 4 | Incorrectly install front chassis |
| 5 | Remove front chassis |
| 6 | Install front chassis pin |
| 7 | Incorrectly install front chassis pin |
| 8 | Remove front chassis pin |
| 9 | Install rear chassis |
| 10 | Incorrectly install rear chassis |
| 11 | Remove rear chassis |
| 12 | Install short rear chassis |
| 13 | Incorrectly install short rear chassis |
| 14 | Remove short rear chassis |
| 15 | Install front-rear chassis pin |
| 16 | Incorrectly install front-rear chassis pin |
| 17 | Remove front-rear chassis pin |
| 18 | Install rear-rear chassis pin |
| 19 | Incorrectly install rear-rear chassis pin |
| 20 | Remove rear-rear chassis pin |
| 21 | Install front bracket |
| 22 | Incorrectly install front bracket |
| 23 | Remove front bracket |
| 24 | Install front bracket screw |
| 25 | Incorrectly install front bracket screw |
| 26 | Remove front bracket screw |
| 27 | Install front wheel assembly |
| 28 | Incorrectly install front wheel assembly |
| 29 | Remove front wheel assembly |
| 30 | Install rear wheel assembly |
| 31 | Incorrectly install rear wheel assembly |
| 32 | Remove rear wheel assembly |

## What to submit

Write `/workspace/output/solution.json` in exactly this shape. The values below are a
fictitious format illustration, not an answer row; do not copy them unless supported
by the videos:

```json
{
  "checkpoints": [
    {
      "video": "A",
      "time_s": 12.3,
      "changes": [3, 6],
      "state_after": [1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0]
    }
  ]
}
```

- `video` must be one of `A` through `G`.
- `time_s` is seconds from the start of that video's media timeline.
- `changes` contains every applicable integer from the closed vocabulary above,
  sorted numerically with no duplicates.
- `state_after` contains exactly 11 integers in the component order above.
- Include every checkpoint exactly once. Sort checkpoints by video, then by time.

## Rules

- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look up the source recordings, labels, or dataset online.
- Derive the ledger only from the provided videos and reference PDF.
