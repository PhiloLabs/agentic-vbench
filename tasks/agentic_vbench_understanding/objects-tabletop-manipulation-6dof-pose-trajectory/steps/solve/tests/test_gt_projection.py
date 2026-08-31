#!/usr/bin/env python3
"""Regression: the baked poses must agree with the camera convention the
instruction states (u = fx*X/Z + cx, v = fy*Y/Z + cy, +Y down) and keep the
target inside the image at every query.

Run: python3 test_gt_projection.py [--cameras path]

Checks, per query: at least 98 percent of the object's canonical points, mapped
by the ground-truth pose and projected with the stated formula, land inside the
image with a margin, and the camera-frame depth stays in arm's reach. A pose
expressed in a rotated or flipped camera frame scatters the points off-target
and fails immediately, which is the regression this guards against.
"""
import argparse
import json
from pathlib import Path

import numpy as np

MARGIN = 8
IN_IMAGE_MIN = 0.98
Z_RANGE = (0.1, 1.5)


def quat_wxyz_to_R(q):
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def main():
    ap = argparse.ArgumentParser()
    here = Path(__file__).parent
    ap.add_argument("--gt", default=here / "ground_truth.json")
    ap.add_argument("--cameras", default="/baked/cameras.json")
    args = ap.parse_args()

    gt = json.loads(Path(args.gt).read_text())
    cams = json.loads(Path(args.cameras).read_text())
    fails = []

    for clip in gt["clips"]:
        cid = clip["clip"]
        c = cams[cid]
        assert c["model"] == "pinhole", cid
        fx, fy, cx, cy = c["fx"], c["fy"], c["cx"], c["cy"]
        W, H = c["width"], c["height"]
        pts = np.asarray(clip["mesh_points_obj"], float)
        for q in clip["queries"]:
            R = quat_wxyz_to_R(q["q_wxyz"])
            t = np.asarray(q["t_xyz_m"], float)
            if not (Z_RANGE[0] < t[2] < Z_RANGE[1]):
                fails.append(f"{cid}:{q['frame']} depth {t[2]:.2f} out of range")
            P = (R @ pts.T).T + t
            Z = P[:, 2]
            if np.any(Z <= 0.05):
                fails.append(f"{cid}:{q['frame']} points behind the camera")
                continue
            u = fx * P[:, 0] / Z + cx
            v = fy * P[:, 1] / Z + cy
            frac = float(np.mean((u >= MARGIN) & (u < W - MARGIN) &
                                 (v >= MARGIN) & (v < H - MARGIN)))
            if frac < IN_IMAGE_MIN:
                fails.append(f"{cid}:{q['frame']} only {frac:.2f} of points in-image")

    if fails:
        print(f"FAIL ({len(fails)}):")
        for f in fails[:20]:
            print("  ", f)
        raise SystemExit(1)
    n = sum(len(c["queries"]) for c in gt["clips"])
    print(f"PASS: {n} queries keep the target in-image under the stated convention")


if __name__ == "__main__":
    main()
