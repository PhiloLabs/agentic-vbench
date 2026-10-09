#!/usr/bin/env python3
"""Project each logged event onto the frame it happened in and crop it.

Luanti's fov setting is the vertical field of view; the horizontal follows
from the aspect ratio. The camera sits at the rig position plus the player
eye height, yaws with the walk and holds a fixed downward pitch, so a block's
world position maps to a pixel directly. This is the only check that answers
"was it on screen" rather than "did the pixels change", which camera motion
and parallax make unanswerable by differencing.
"""
import json, math, os, subprocess, sys, numpy as np

FF = os.environ.get("FFMPEG", "ffmpeg")   # needs an x11grab-capable build to record, not to project
W, H = 1280, 720
FOV_V = math.radians(72.0)
PITCH = math.radians(-34.0)
EYE = 1.5


def project(cam, yaw, blk):
    """Pixel of blk seen from cam. Returns None when behind the camera."""
    dx = blk[0] - cam[0]
    dy = blk[1] - (cam[1] + EYE)
    dz = blk[2] - cam[2]
    # forward = (-sin yaw, cos yaw); right = (cos yaw, sin yaw)
    f = -math.sin(yaw) * dx + math.cos(yaw) * dz
    r = math.cos(yaw) * dx + math.sin(yaw) * dz
    # rotate the forward/up plane by the pitch
    fp = f * math.cos(PITCH) + dy * math.sin(PITCH)
    up = -f * math.sin(PITCH) + dy * math.cos(PITCH)
    if fp <= 0.5:
        return None
    ty = math.tan(FOV_V / 2)
    tx = ty * W / H
    px = W / 2 * (1 + (r / fp) / tx)
    py = H / 2 * (1 - (up / fp) / ty)
    return px, py, fp


def rows(path):
    out = []
    for line in open(path):
        p = line.rstrip("\n").split("\t")
        if len(p) < 6:
            continue
        cam = p[5].split(",")
        out.append(dict(t=float(p[0]), act=p[1], name=p[2],
                        pos=[int(v) for v in p[3].split(",")], extra=p[4],
                        cam=[float(cam[0]), float(cam[1]), float(cam[2])],
                        yaw=float(cam[3])))
    return out


def main(log, video, offset, n=40):
    R = [r for r in rows(log) if r["act"] in ("redig", "place")]
    off = float(offset)
    stats = {"redig": [0, 0, []], "place": [0, 0, []]}
    for r in R:
        pr = project(r["cam"], r["yaw"], [v + 0.5 for v in r["pos"]])
        s = stats[r["act"]]
        s[1] += 1
        if pr is None:
            continue
        px, py, d = pr
        if 0 <= px < W and 0 <= py < H:
            s[0] += 1
            s[2].append((d, 2 * math.atan(0.5 / d) / FOV_V * H))
    for k, (ok, tot, sz) in stats.items():
        if not sz:
            print("%-6s on screen %d/%d" % (k, ok, tot)); continue
        d = np.array([x[0] for x in sz]); px = np.array([x[1] for x in sz])
        print("%-6s on screen %d/%d   distance median %.1f nodes   "
              "apparent size median %.0f px  p10 %.0f px"
              % (k, ok, tot, np.median(d), np.median(px), np.percentile(px, 10)))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])


def crops(log, video, offset, out, n=6):
    """Save a wide crop centred on where each of n removals should be."""
    R = [r for r in rows(log) if r["act"] == "redig"]
    off = float(offset)
    for i, r in enumerate(R[:n]):
        pr = project(r["cam"], r["yaw"], [v + 0.5 for v in r["pos"]])
        if pr is None:
            continue
        px, py, d = pr
        x0 = max(0, min(W - 320, int(px) - 160))
        y0 = max(0, min(H - 200, int(py) - 100))
        for tag, tv in (("before", r["t"] + off - 1.0), ("after", r["t"] + off + 1.0)):
            subprocess.run([FF, "-v", "error", "-ss", "%.3f" % tv, "-i", video,
                            "-frames:v", "1", "-vf",
                            "crop=320:200:%d:%d,scale=640:400:flags=neighbor" % (x0, y0),
                            "-q:v", "2", "%s/cr%d_%s.jpg" % (out, i, tag), "-y"])
        print("%d %-26s t=%.1f d=%.0f px=(%.0f,%.0f)" % (i, r["name"], r["t"] + off, d, px, py))
