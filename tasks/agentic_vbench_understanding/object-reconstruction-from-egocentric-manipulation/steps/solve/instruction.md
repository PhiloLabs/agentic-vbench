# 3D Object Reconstruction From Egocentric Manipulation Clips

You are given three egocentric (head-mounted, first-person) video clips. In each clip a
person picks up and turns over one small tabletop object, showing it from many angles:

- `/workspace/materials/clip_01.mp4`
- `/workspace/materials/clip_02.mp4`
- `/workspace/materials/clip_03.mp4`

For each clip, a target object is designated (see `objects.json`). Reconstruct the
3D surface mesh of each target object from how it appears across that clip.

You are also given, in `/workspace/materials/`:

- `objects.json`: the target object's name for each clip id (`clip_01`, `clip_02`,
  `clip_03`).
- `cameras.json`: the pinhole camera intrinsics for each clip, keyed by clip id, giving
  `model` (`pinhole`), image `width`/`height`, focal lengths `fx`/`fy`, and principal
  point `cx`/`cy`.

## What to submit

Write one triangle mesh per clip into `/workspace/output/`, named by clip id:

- `/workspace/output/clip_01.obj`  (or `.ply` / `.glb` / `.stl`)
- `/workspace/output/clip_02.obj`
- `/workspace/output/clip_03.obj`

Each mesh must be a watertight-ish surface reconstruction of that clip's target object:
a set of 3D vertices and triangular faces describing the object's shape. Any of `.obj`,
`.ply`, `.glb`, or `.stl` is accepted; one file per clip.

Scale and pose do not matter. Your reconstruction is compared to the reference shape
after a best-fit similarity alignment (rotation, translation, and a single global
scale), so you do not need to recover the real-world size or where the object sat, only
its shape. What matters is that the reconstructed surface has the same geometry as
the real object.

## Rules

- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online and do not rely on memory or a stock 3D model of a
  similar product; reconstruct the specific object from the clip. Use any tools in the
  image (for example `ffmpeg`/`ffprobe`) to seek and sample frames.
- Produce one mesh per clip, for the target object named in `objects.json` for that clip.
