# Video Assembly Task — `The Shot Fades In From Darkness To Revea`

You are given **12 candidate video clips**: `1.mp4`, `2.mp4`, …, `12.mp4`.
Your job is to assemble a **4-shot sequence** that matches the storyboard below.

## Additional notes

- Stay inside this working directory. Don't read, write, or search
  files outside it — no parent directories, no other paths on the
  system.
- Don't try to identify the source film or look it up online.
  Don't search for the original film, transcripts, or related
  metadata to compare against the clips — work only from the bytes
  you've been given. (Other web lookups, e.g. tool docs, are fine.)

## What to submit

1. **`/workspace/output/solution.mp4`** — the 4 clips concatenated
   in slot order. Each picked clip is used in full, exactly once.
2. **`/workspace/output/solution.json`** — a manifest describing what's
   in the final video. (Schema and rules below.)

## What to do

1. **For each storyboard slot below**, pick the candidate whose video best matches the storyboard's five fields (`description`, `shot_size`, `camera_angle`, `lens_size`, `camera_movement`). Choose the candidate that matches the **most** of these fields, weighing each field by how much it actually defines that particular shot — not every field carries the same importance for every shot. Judge by what is on screen.
2. **Concatenate** the picked clips in slot order (1 → 2 → 3 → …).
3. **Submit** the result as `/workspace/output/solution.mp4`.

## Also submit a manifest

Once `/workspace/output/solution.mp4` is finalized, write **`/workspace/output/solution.json`** describing what's actually in the final video. Use any assembly method you prefer — the verifier checks the manifest against the actual video content, so misreporting will fail.

### Format

```json
{
  "segments": [
    {"output": [0.0, 2.0], "source": "3", "source_range": [0.0, 2.0]},
    {"output": [2.0, 3.5], "source": "7", "source_range": [0.0, 1.5]}
  ]
}
```

### Rules

- Exactly **4 entries**, one per slot, in slot order.
- Intervals are **half-open** `[start, end)` — end is exclusive.
- `output` — time range where this clip appears in `solution.mp4`.
- `source` — clip number as a string (`"3"` for `3.mp4`).
- `source_range` — portion of the clip you used; full clip is `[0, clip_duration]`.
- Segments must be **contiguous**: each `output[0]` equals the previous `output[1]`; first starts at `0.0`, last ends at `solution.mp4`'s total duration.

### Example

If Slot 1 → `3.mp4` (2.0s, used in full) and Slot 2 → `7.mp4` (1.5s, used in full):

```json
{
  "segments": [
    {"output": [0.0, 2.0], "source": "3", "source_range": [0.0, 2.0]},
    {"output": [2.0, 3.5], "source": "7", "source_range": [0.0, 1.5]}
  ]
}
```

Repeat for all 4 slots.

---

## Shot Language Reference

Definitions for the cinematic terms used in the storyboard fields.

### `shot_size`

- **Extreme Wide** — Frames the subject from a great distance so that the surrounding environment overwhelmingly dominates the image. It is used to establish scale, location, and context, often making the subject appear small or isolated within a vast setting.
- **Wide** — Shows the subject from head to toe, although not necessarily filling the frame. The focus is still largely on the environment, but the subject is more prominent than in an EWS. It shows the subject within their surroundings, providing context.
- **Medium Wide** — Frames the subject from the knees up, situating them between a full body shot and a medium shot. It balances character body language with a sense of the immediate surroundings, often used for dialogue and group staging.
- **Medium** — Frames the subject from the waist up, a standard framing for conversation and everyday action. It conveys both facial expression and upper-body gesture while retaining modest environmental context.
- **Medium Close Up** — Frames the subject from roughly the chest or shoulders up, tightening focus on the face while still showing some upper body. It is commonly used for dialogue and emotionally engaged moments without fully isolating the subject.
- **Close Up** — Frames a specific part of the subject, typically the head and face, from the neck up. It tightly frames the character's face, emphasizing their emotional state and reactions. Little to no background is visible.
- **Extreme Close Up** — Frames only a small portion or detail of the subject, such as the eyes, mouth, or a specific object. It is used to create intensity, highlight a crucial detail, or convey strong emotion or tension.

### `camera_angle`

- **Eye level** — An eye-level shot positions the camera at the subject's eyeline and looks horizontally, treating the subject as a peer of the viewer. It is the neutral, baseline angle — neither empowering nor diminishing — and is the most common framing in conversation, observation, and unobtrusive narration. It registers as 'normal' precisely because it minimizes editorial implication.
- **Shoulder level** — A shoulder-level shot positions the camera at roughly the height of the subject's shoulders, slightly below true eye level. Many directors prefer it to a literal eye-level shot because it keeps the actor's head near the top of the frame and reduces unflattering head room, producing a more cinematic register. It maintains a near-neutral psychological tone but with a faintly heroic lean.
- **Hip level** — A hip-level (or 'cowboy') shot positions the camera at roughly waist height. It is a classic Western framing used when a character's hands are in play near the hip — drawing a weapon, holstering a tool, leaning on a counter — and is also useful when one subject is seated while another stands. The framing emphasizes hand action and bodily presence without yet feeling like a low angle.
- **Knee level** — A knee-level shot positions the camera approximately at the height of the subject's knees. It is often used to follow a character's walking or sneaking action without revealing the face, and when combined with a low-angle tilt up, it amplifies the subject's superiority or menace. It is also a common framing for shots that feature legwork, footing, or contact with the ground.
- **Ground level** — A ground-level shot positions the camera directly on or just above the floor or ground plane. It is most commonly used to follow feet, dust, water, or low-moving objects, and to track a character walking past without showing their face or upper body. The framing emphasizes the texture of the ground and the feet's relationship to it.
- **Low angle** — A low angle shot positions the camera below the subject's eyeline and looks upward, making the subject appear larger, dominant, powerful, or intimidating. It can also convey awe, heroism, or psychological superiority, and is frequently used to elevate villains and authority figures.
- **High angle** — A high angle shot looks down on the subject from above their eyeline, tending to make them appear smaller, weaker, vulnerable, or isolated. It is often used to diminish a character's power or to give the audience an observational, sometimes pitying, perspective.
- **Overhead** — An overhead shot, sometimes called a bird's-eye or top shot, places the camera directly above the subject pointing straight down, flattening the scene into a graphic, map-like composition. It is commonly used for interiors or mid-range action to reveal spatial relationships, choreography, or to create a detached, omniscient feel.
- **Aerial** — An aerial shot is captured from an aircraft, helicopter, or drone at substantial altitude, offering a sweeping, wide-scope view of landscapes, cityscapes, or large-scale action. It is often used as an establishing shot to convey geography, scale, and epic scope, or to provide dynamic movement over an environment.
- **Dutch angle** — A Dutch angle, also called a Dutch tilt or canted angle, rolls the camera on its lens axis so the horizon is no longer level, creating a sense of unease, disorientation, tension, or psychological instability. It is commonly used in thrillers, horror, and action sequences to signal that something is wrong or off-balance.

### `lens_size`

- **Ultra Wide & Fisheye** — Lenses with focal lengths shorter than ~24mm (full-frame equivalent), with fisheye variants typically ~8–15mm. They offer a broader field of view and often introduce edge distortion, with fisheyes producing a pronounced curved, spherical warping of straight lines.
- **Wide** — Wide-angle lenses typically span ~24–35mm (full-frame equivalent) and capture a broader field of view than the human eye without the extreme distortion of ultra wides. They emphasize environment and spatial context while exaggerating the sense of depth between foreground and background.
- **Medium** — Medium or normal lenses cover roughly ~35–70mm (full-frame equivalent), with 50mm approximating the perspective of the human eye. They render scenes with natural proportions, neutral field of view, and minimal geometric distortion.
- **Long Lens** — Long or telephoto lenses typically start at ~85mm and extend well beyond (full-frame equivalent), offering a narrow field of view. They compress spatial depth, making the foreground and background elements appear closer, and isolate subjects from their surroundings.

### `camera_movement`

- **Static** — The camera remains completely locked off on a tripod or fixed mount with no translation, rotation, or focal length change. Used to create stability, observational distance, or formal composition, letting subject motion carry the scene.
- **Push in** — The camera body physically moves toward the subject along a dolly, track, slider, gimbal, or Steadicam while focal length stays constant. It intensifies emotion, directs attention inward, and draws the audience into the subject's psychology.
- **Pull out** — The camera body physically retreats away from the subject on a dolly, track, or stabilizer while focal length stays constant. It reveals surrounding context, isolates the subject, or releases emotional tension built up in a scene.
- **Zoom in** — The camera stays physically stationary while the lens's focal length lengthens, magnifying the subject optically. It is often used for sudden emphasis, a surveillance feel, or a stylized punch-in.
- **Zoom out** — The camera stays stationary while the lens's focal length shortens, optically widening the field of view. It can reveal context, diminish a subject, or deliver a reveal without any physical camera motion.
- **Pan left** — The camera pivots horizontally to the left around a fixed vertical axis on its tripod or head, with the body itself not translating. It is used to follow action, scan a space, or reveal something to the subject's left.
- **Pan right** — The camera pivots horizontally to the right around a fixed vertical axis, while the body remains in place. It follows rightward motion, scans a landscape, or redirects attention across a scene.
- **Tilt up** — The camera pivots upward on its horizontal axis while remaining in the same physical location. It reveals height, establishes scale, or moves the gaze from a lower element to a higher one.
- **Tilt down** — The camera pivots downward on its horizontal axis from a fixed position. It redirects attention from a higher element to a lower one, reveals something below, or follows a falling motion.
- **Boom up** — The entire camera body rises vertically on a crane, jib, pedestal, or gimbal while its angle stays essentially level. It is used to lift the viewpoint over obstacles, reveal scale, or create a rising, elevating emotional beat.
- **Boom down** — The camera body descends vertically on a crane, jib, or pedestal while its angle remains constant. It lowers the viewpoint toward ground level, often to meet a subject, conclude a reveal, or ground the scene.
- **Dolly left** — The camera body translates laterally to the left on a dolly, track, slider, or stabilizer, keeping its heading forward. Also called trucking or tracking left, it follows subjects moving leftward or sweeps sideways through a space.
- **Dolly right** — The camera body translates laterally to the right on a dolly, track, or stabilizer, heading kept forward. Also called trucking or tracking right, it follows rightward action or traverses a setting sideways.
- **Dolly forward** — The camera body translates forward on a dolly or wheeled rig, often pacing a subject also moving forward. Unlike a push in, which approaches a stationary subject and grows its scale, a dolly forward shares the subject's momentum, keeping the subject's frame size roughly stable.
- **Dolly backward** — The camera body translates backward on a dolly or wheeled rig, often pacing a subject moving toward the lens. Unlike a pull out, which retreats from a stationary subject and shrinks its scale, a dolly backward shares the subject's forward momentum, keeping the subject's frame size roughly stable.
- **Arc** — The camera travels along a curved or circular path around the subject while keeping the subject framed, typically via a circular dolly track, Steadicam, or gimbal. It emphasizes a subject, reveals dimensionality, or creates dynamic orbital energy.
- **Camera roll** — The camera rotates around its own lens (optical) axis, so the horizon spins within the frame while the camera does not translate. It conveys disorientation, intoxication, weightlessness, or action-driven chaos.
- **Dolly zoom** — The camera physically dollies in one direction while the lens simultaneously zooms in the opposite direction, so the subject's size in frame remains constant but the background perspective warps. Known as the Vertigo effect, it visualizes psychological unease, dread, or revelation.

---

## Storyboard

### Slot 1

- **description**: The shot fades in from darkness to reveal a young girl in a dress standing in the center foreground, facing away from the camera with her arms resting at her sides. She looks out over a vast, rolling landscape featuring a winding river and distant mountains under a pink and purple sky with a large, low sun that slowly rises. The camera slowly pushes in on the girl and the landscape, which is framed by dark silhouetted trees on the left and right edges.
- **shot_size**: `Wide`
- **camera_angle**: `Eye level`
- **lens_size**: `Medium`
- **camera_movement**: `Push in`

### Slot 2

- **description**: An anime-style girl with short black hair and a black jacket is positioned on the right side of the frame, facing three-quarter toward camera-left. She gazes toward the camera with a serious expression, blinks slowly, glances quickly toward camera-left mid-shot, and then raises her eyes back toward the camera. The background features a pink sky seen through a dark structural frame.
- **shot_size**: `Medium Close Up`
- **camera_angle**: `Eye level`
- **lens_size**: `Medium`
- **camera_movement**: `Pull out`

### Slot 3

- **description**: A silhouetted figure stands motionless on a reflective surface, facing away from the camera toward a large, glowing pink hexagonal shape on the ground; her arms hang loosely at her sides, and her expression is obscured by the darkness. The figure begins walking forward, stepping onto the glowing pink shape and moving further away from the camera.
- **shot_size**: `Wide`
- **camera_angle**: `High angle`
- **lens_size**: `Wide`
- **camera_movement**: `Static`

### Slot 4

- **description**: A silhouetted woman in a skirt walks up a dark concrete staircase, facing away from the camera. She carries a bag in her right hand, her arms swinging slightly as she ascends towards a bright pink rectangular doorway at the top of the stairs. Her facial expression is completely obscured by the heavy silhouette.
- **shot_size**: `Wide`
- **camera_angle**: `Low angle`
- **lens_size**: `Wide`
- **camera_movement**: `Static`

## Done when

Both `/workspace/output/solution.mp4` and `/workspace/output/solution.json` exist.

---

## Workspace layout

- The candidate clips have been pre-downloaded to `/workspace/materials/`
  (named `1.mp4` through `N.mp4`). Read them from there.
- Use `/workspace/work/` for any intermediate scratch files.
- Use `/workspace/output/` only for the two final deliverables.
- `ffmpeg` and `ffprobe` are available on `PATH`.
