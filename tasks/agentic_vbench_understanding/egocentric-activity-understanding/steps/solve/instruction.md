# Egocentric Activity Understanding Task

You are given:

- `/workspace/materials/session.mkv`: one continuous head-mounted (egocentric) video of
  a single person preparing an American breakfast in a kitchen. 1280x960, **24 frames
  per second**, 25692 frames. There is no audio track.
- `/workspace/materials/vocabulary.json`: the complete closed label space — every verb
  and every noun you are allowed to use.

Reconstruct the complete chronological ledger of the **object-manipulation actions** the
camera wearer performs. The starting/ending frame number follows 24 fps as the original video (the first frame is 0).

## What counts as one action

An action is one continuous manipulation of one or more kitchen objects by the camera
wearer's hands, described as a verb plus the objects it acts on.

- `start_frame` is the first frame in which the manipulation is under way — the hand has
  reached the object and the motion that defines the verb has begun, not the frame the
  reach starts.
- `end_frame` is the last frame of that motion — the object has been released, closed,
  poured, flipped, or set down.
- Label only manipulations of the objects named in `vocabulary.json`. Walking,
  reaching, looking around, idle hands, and talking are not actions, and long stretches
  of the video contain no action at all.
- The same verb and objects can recur many times across the video; report every
  occurrence separately, in the order it happens.
- Actions are essentially sequential, but two can touch or briefly overlap: one action
  commonly ends on the frame the next one begins, and occasionally the two hands do
  different things at once (opening a drawer while already holding a carton). Report
  each one separately.

## Vocabulary

Use `verb` exactly as spelled in `vocabulary.json`. The 15 verbs are:

`close`, `compress`, `crack`, `cut`, `flip`, `mix`, `move around`, `open`, `pour`,
`put`, `spread`, `take`, `transfer`, `turn off`, `turn on`

`nouns` is the list of objects the verb acts on, each spelled exactly as in
`vocabulary.json`. The 35 nouns are:

`bacon`, `bacon_container`, `bagel`, `bagel_container`, `bowl`, `burner`, `cabinet`,
`cheese`, `cheese_container`, `cup`, `egg`, `egg_container`, `egg_mixture`,
`egg_shells`, `fork`, `freezer`, `fridge`, `fridge_drawer`, `knife`, `milk`,
`milk_container`, `oil`, `oil_container`, `orange_juice`, `orange_juice_container`,
`plastic_holed`, `plastic_spatula`, `plate`, `plate_container`, `plate_pronged_spoon`,
`salt`, `salt_container`, `skillet`, `trash`, `utensils`

Notes on how the vocabulary is applied:

- Give every object involved in the manipulation, including the tool and the
  destination: pouring oil from its container into the skillet is
  `pour` with `oil, oil_container, skillet`; moving egg around the skillet with the
  spatula is `move around` with `egg, skillet, plastic_spatula`.
- The published labels use both `egg` and `eggs`; this task merges both labels into
  `egg`, reducing the published 36 nouns to the 35 listed above. `egg` covers egg in any
  form — a whole egg in the shell and the cooking egg mass in the pan are both `egg`.
  `egg_mixture` is the beaten egg before it goes in the pan,
  `egg_shells` are the discarded shells, and `egg_container` is the carton; those three
  stay separate from `egg`.
- A `*_container` is the packaging an ingredient comes in. `fridge`, `freezer`,
  `fridge_drawer`, and `cabinet` are storage the wearer opens and closes.
- The order of `nouns` does not matter, but do not repeat a noun within one action.

## What to submit

Write `/workspace/output/solution.json` in exactly this shape:

```json
{
  "actions": [
    {"verb": "turn on", "nouns": ["burner"], "start_frame": 1000, "end_frame": 2000},
    {"verb": "pour", "nouns": ["oil", "oil_container", "skillet"], "start_frame": 2000, "end_frame": 3000}
  ]
}
```

Requirements:

- `verb`: one verb from the vocabulary above.
- `nouns`: a non-empty list of nouns from the vocabulary above, no repeats.
- `start_frame`, `end_frame`: integer frame numbers, where the **first frame of the
  video is frame 0** and frame `n` is at time `n / 24` seconds. Both must be in
  `[0, 25691]` and `start_frame` must be less than `end_frame`.
- Entries must be ordered by non-decreasing `start_frame`. When entries share a start
  frame, order them by `verb` alphabetically, then by the lexicographic order of their
  alphabetically sorted noun lists, then by `end_frame`. Noun order within an entry is
  still ignored for scoring.

Use `ffmpeg` and `ffprobe` (both installed) to seek through and sample the video. To
extract exactly frame `n`, select on the frame index rather than by timestamp, for
example:

```bash
ffmpeg -v error -i /workspace/materials/session.mkv \
       -vf "select=between(n\,1040\,1100)" -vsync 0 /workspace/work/f_%05d.png
```

## Rules

- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online, and do not rely on any memory of this dataset or
  video; every action must come from watching the video.
