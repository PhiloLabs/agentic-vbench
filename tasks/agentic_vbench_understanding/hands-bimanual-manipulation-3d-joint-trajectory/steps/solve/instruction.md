# Right-Hand 3D Joint Trajectory From Egocentric Clips

You are given three egocentric (head-mounted, first-person) video clips of a person
manipulating small tabletop objects with both hands:

- `/workspace/materials/clip_01.mp4`
- `/workspace/materials/clip_02.mp4`
- `/workspace/materials/clip_03.mp4`

For a set of query frames in each clip, reconstruct the 3D position of the **right
hand's** 20 skeleton joints, expressed **in that clip's RGB camera coordinate frame, in
metres**.

You are also given, in `/workspace/materials/`:

- `cameras.json`: the pinhole camera intrinsics for each clip, keyed by clip id
  (`clip_01`, `clip_02`, `clip_03`). Each entry gives `model` (`pinhole`), the image
  `width`/`height`, the focal lengths `fx`/`fy`, and the principal point `cx`/`cy`
  (standard pinhole model: a 3D camera-frame point `[X,Y,Z]` projects to pixel
  `u = fx*X/Z + cx`, `v = fy*Y/Z + cy`).
- `queries.json`: for each clip id, the list of integer frame indices you must answer
  for. Frame indices are 0-based into the corresponding mp4.
- `hand_model.json`: the bone lengths of the wearer's right hand in metres, constant
  across the clips (same person throughout). This is your metric reference: with the
  pinhole intrinsics, a bone of length L at depth Z spans about `fx * L / Z` pixels, so
  the observed pixel length of identified bones fixes the metric depth of the hand.

## Coordinate frame and joints

- **Camera frame.** The origin is the RGB camera optical centre. +Z points forward
  along the optical axis (into the scene), +X right, +Y down, following the standard
  pinhole/camera convention that the provided camera model uses. Report every joint as
  `[x, y, z]` in metres in this frame, for the clip the query belongs to.
- **The 20 joints**, in this exact order (index 0..19):

  ```
  0  thumb_fingertip        10 index_distal
  1  index_fingertip        11 middle_proximal
  2  middle_fingertip       12 middle_intermediate
  3  ring_fingertip         13 middle_distal
  4  pinky_fingertip        14 ring_proximal
  5  wrist                  15 ring_intermediate
  6  thumb_intermediate     16 ring_distal
  7  thumb_distal           17 pinky_proximal
  8  index_proximal         18 pinky_intermediate
  9  index_intermediate     19 pinky_distal
  ```

  `*_proximal / *_intermediate / *_distal` are the three finger knuckles from the palm
  outward; `*_fingertip` is the tip; `wrist` is the wrist joint. Report all 20 for every
  query frame, in the order above.

## What to submit

Write `/workspace/output/solution.json` in exactly this shape:

```json
{
  "clips": {
    "clip_01": [
      {"frame": 137, "joints_m": [[0.031, 0.044, 0.382], "... 20 rows total ..."]},
      {"frame": 402, "joints_m": ["..."]}
    ],
    "clip_02": [{"frame": 88, "joints_m": ["..."]}],
    "clip_03": [{"frame": 51, "joints_m": ["..."]}]
  }
}
```

- One object entry per query frame listed in `queries.json`, under its clip id.
- `frame`: the 0-based frame index (must match a frame in `queries.json`).
- `joints_m`: a list of exactly 20 `[x, y, z]` rows, in the joint order above, in metres,
  in that clip's camera frame.

## Rules

- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online and do not rely on memory; measure the hand from the
  clips. Use any tools in the image (for example `ffmpeg`/`ffprobe`) to seek and sample.
- Answer only the query frames in `queries.json`. Answer only the right hand.
