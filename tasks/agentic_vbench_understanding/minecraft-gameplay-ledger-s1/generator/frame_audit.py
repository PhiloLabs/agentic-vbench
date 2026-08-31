#!/usr/bin/env python3
"""Objectively audit how informative a rendered session's frames are.

    frame_audit.py GAME_MP4 [STEP_SECONDS]

Two failure modes made earlier P1 renders bad footage, and both are measurable without
looking at anything:

  sky        the camera pitched off the world, so the frame is flat sky
  one_block  the player stood flush against its target, so one texture fills the frame

Both show up as "a single colour owns most of the frame", so the metric is the share of the
most common quantised colour (dom), split by whether that colour is pale sky blue. A frame
counts as uninformative when dom > 0.60. Prints the rate plus the worst offenders with
timestamps, so a fix is verified by re-running rather than by eyeballing 20 thumbnails.
"""
import subprocess, sys
from pathlib import Path
import numpy as np

FF = "/pkg/ffmpeg/4.2.2/bin/ffmpeg"
FP = "/pkg/ffmpeg/4.2.2/bin/ffprobe"
game = Path(sys.argv[1]); step = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
W, H = 160, 90
DOM_LIMIT = 0.60

dur = float(subprocess.run([FP, "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", str(game)], capture_output=True, text=True).stdout.strip())
p = subprocess.Popen([FF, "-v", "error", "-i", str(game), "-r", f"{1.0/step:g}", "-s", f"{W}x{H}",
                      "-pix_fmt", "rgb24", "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
frames, sz = [], W * H * 3
while True:
    b = p.stdout.read(sz)
    if len(b) < sz: break
    frames.append(np.frombuffer(b, np.uint8).reshape(H, W, 3))
p.wait()

rows = []
for i, f in enumerate(frames):
    q = (f.astype(np.uint16) // 24)
    key = q[:, :, 0] * 121 + q[:, :, 1] * 11 + q[:, :, 2]
    vals, counts = np.unique(key, return_counts=True)
    j = int(np.argmax(counts))
    dom = counts[j] / key.size
    mc = f[key == vals[j]].mean(axis=0)
    is_sky = mc[2] > 170 and mc[2] >= mc[1] >= mc[0] and mc[0] > 110
    rows.append((i * step, dom, "sky" if is_sky else "one_block"))

bad = [r for r in rows if r[1] > DOM_LIMIT]
sky = [r for r in bad if r[2] == "sky"]
blk = [r for r in bad if r[2] == "one_block"]
print(f"{game.name}: {dur:.0f}s, {len(rows)} frames sampled every {step:g}s")
print(f"  uninformative (dom>{DOM_LIMIT:.2f}): {len(bad)}/{len(rows)} = {100*len(bad)/max(1,len(rows)):.1f}%"
      f"   [sky {len(sky)}, one_block {len(blk)}]")
print(f"  mean dominant-colour share {np.mean([r[1] for r in rows]):.3f}")
for tag, group in (("sky", sky), ("one_block", blk)):
    worst = sorted(group, key=lambda r: -r[1])[:8]
    if worst:
        print(f"  worst {tag}: " + ", ".join(f"{t:.0f}s({d:.2f})" for t, d, _ in worst))
