#!/usr/bin/env python3
"""Nine frames evenly across each sampled step, as one 3x3 contact sheet per row.

Frames come from the same 1080p derivatives the image ships, so what the sheet shows is
what an agent could have decoded. Timestamps are burned in.
"""
import json, subprocess, pathlib, sys

OUT = pathlib.Path(sys.argv[1]); MEDIA = pathlib.Path(sys.argv[2])
rows = json.loads((OUT / "blind.json").read_text())
assert rows, "no rows to extract"
tiles = OUT / "tiles"; tiles.mkdir(exist_ok=True)
made = 0
for r in rows:
    src = MEDIA / f"{r['video']}.mp4"
    assert src.exists(), f"missing {src}"
    a, b = r["t_start"], r["t_end"]
    ts = [a + (b - a) * k / 8.0 for k in range(9)]
    paths = []
    for k, t in enumerate(ts):
        p = tiles / f"{r['slot']}_{k}.jpg"
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-ss", f"{t:.3f}",
                        "-i", str(src), "-frames:v", "1", "-vf",
                        f"scale=640:-2,drawtext=text='t\\={t:.1f}':x=8:y=8:fontsize=28:"
                        f"fontcolor=yellow:box=1:boxcolor=black@0.6:boxborderw=4",
                        "-q:v", "3", "-y", str(p)], check=True)
        assert p.exists() and p.stat().st_size > 0, f"{p} not written"
        paths.append(str(p))
    sheet = OUT / f"{r['slot']}.jpg"
    # tile works on the frames of ONE stream, so the nine stills are concatenated into a
    # stream first. Feeding it nine separate inputs silently lays down only the first and
    # leaves the other eight tiles black, which looked like a sheet until it was read.
    chain = "".join(f"[{i}:v]" for i in range(len(paths)))
    subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error",
                    *sum([["-i", p] for p in paths], []),
                    "-filter_complex",
                    f"{chain}concat=n={len(paths)}:v=1:a=0[c];[c]tile=3x3:margin=6:padding=6",
                    "-frames:v", "1", "-q:v", "3", "-y", str(sheet)], check=True)
    # a sheet whose tiles are mostly black is the failure above; require real content
    import struct
    assert sheet.exists() and sheet.stat().st_size > 60000, \
        f"{sheet} is {sheet.stat().st_size} bytes, too small to hold nine populated tiles"
    made += 1
    print(f"  {r['slot']}  {r['video']}  {a:.1f}-{b:.1f}  -> {sheet.name} "
          f"({sheet.stat().st_size//1024} kB)")
assert made == len(rows), f"made {made} sheets for {len(rows)} rows"
print(f"{made} contact sheets")
