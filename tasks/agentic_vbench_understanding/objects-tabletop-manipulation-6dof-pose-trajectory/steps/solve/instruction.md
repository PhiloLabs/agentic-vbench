# Object 6DoF Pose Trajectory From Egocentric Clips

You are given three egocentric (head-mounted, first-person) video clips of a person
manipulating small tabletop objects:

- `/workspace/materials/clip_01.mp4`
- `/workspace/materials/clip_02.mp4`
- `/workspace/materials/clip_03.mp4`

In each clip one target object is designated. For a set of query frames in each
clip, reconstruct the 6DoF pose of that target object (its position and
orientation), expressed in that clip's RGB camera coordinate frame, in metres.

You are also given, in `/workspace/materials/`:

- `objects.json`: the target object's name for each clip id (`clip_01`, `clip_02`,
  `clip_03`).
- `cameras.json`: the pinhole camera intrinsics for each clip, keyed by clip id, giving
  `model` (`pinhole`), image `width`/`height`, focal lengths `fx`/`fy`, and principal
  point `cx`/`cy` (a 3D camera-frame point `[X,Y,Z]` projects to pixel `u = fx*X/Z + cx`,
  `v = fy*Y/Z + cy`).
- `queries.json`: for each clip id, the list of 0-based integer frame indices you must
  answer for.
- `object_points.json`: for each clip id, a set of 3D points sampled from the target
  object's surface, given in the object's own canonical frame (metres). This defines the
  canonical frame your pose maps from, and is the same point set the pose is scored on.

## What a pose means here

The pose you report for a query frame is the rigid transform `T_camera_object` that maps
a point `p_obj` given in the object's canonical frame (the frame `object_points.json` is
in) to the camera frame:

```
p_camera = R * p_obj + t
```

- `t = [tx, ty, tz]` is the object origin in the camera frame, in metres
  (camera convention: +Z forward along the optical axis, +X right, +Y down).
- `R` is the rotation, which you report as a unit quaternion `q = [w, x, y, z]`.

Recover a pose per query frame such that the object points, placed by `R` and `t` and
projected through the given camera model, line up with the object as it appears in that
frame. Because you have both the object points and the camera model, a correct pose is
well defined; the difficulty is estimating it from a single moving view.

## What to submit

Write `/workspace/output/solution.json` in exactly this shape:

```json
{
  "clips": {
    "clip_01": [
      {"frame": 210, "t_xyz_m": [0.05, -0.02, 0.44], "q_wxyz": [0.98, 0.01, -0.17, 0.02]},
      {"frame": 655, "t_xyz_m": ["..."], "q_wxyz": ["..."]}
    ],
    "clip_02": [{"frame": 88, "t_xyz_m": ["..."], "q_wxyz": ["..."]}],
    "clip_03": [{"frame": 51, "t_xyz_m": ["..."], "q_wxyz": ["..."]}]
  }
}
```

- One entry per query frame listed in `queries.json`, under its clip id.
- `frame`: the 0-based frame index (must match a frame in `queries.json`).
- `t_xyz_m`: object origin in the camera frame, metres.
- `q_wxyz`: unit quaternion (w first) for the object's orientation in the camera frame.

## Rules

- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online and do not rely on memory; measure the object from the
  clips. Use any tools in the image (for example `ffmpeg`/`ffprobe`) to seek and sample.
- Answer only the query frames in `queries.json`, and only the target object named in
  `objects.json` for that clip.
