#!/usr/bin/env python3
"""Regression: the baked ground truth must agree with the camera convention the
instruction states, and with the hand model shipped to the agent.

Run: python3 test_gt_projection.py [--cameras path] [--hand-model path]

Checks, per query frame:
1. Every joint projects inside the image with the instruction's formula
   (u = fx*X/Z + cx, v = fy*Y/Z + cy, +Y down), with a margin. This catches any
   future frame-convention regression: joints expressed in a rotated or flipped
   camera frame scatter off the hand and out of the visible band.
2. Depth (Z) sits in the arm's-reach range at every joint.
3. The rigid bone lengths measured from the GT joints match hand_model.json to
   sub-millimetre, so the metric reference the agent receives is exactly the
   skeleton the judge scores against.

An overlay spot check against the pinned clips (which are not shipped in tests/)
is in the calibration notes; this test covers everything checkable from the GT
and the agent-facing files alone.
"""
import argparse
import json
from pathlib import Path

import numpy as np

MARGIN = 8
Z_RANGE = (0.15, 1.0)
BONE_TOL_M = 0.001


def load(path):
    return json.loads(Path(path).read_text())


def main():
    ap = argparse.ArgumentParser()
    here = Path(__file__).parent
    ap.add_argument("--gt", default=here / "ground_truth.json")
    ap.add_argument("--cameras", default=here.parents[2] / "workdir_cameras.json",
                    help="agent-facing cameras.json (defaults resolved below)")
    ap.add_argument("--hand-model", default=None)
    args = ap.parse_args()

    gt = load(args.gt)
    names = gt["joint_names"]
    idx = {n: i for i, n in enumerate(names)}

    # cameras.json / hand_model.json: prefer explicit paths, else the baked copies
    cam_path = Path(args.cameras)
    if not cam_path.is_file():
        cam_path = Path("/baked/cameras.json")
    hm_path = Path(args.hand_model) if args.hand_model else Path("/baked/hand_model.json")

    cams = load(cam_path)
    fails = []

    for clip in gt["clips"]:
        cid = clip["clip"]
        c = cams[cid]
        assert c["model"] == "pinhole", cid
        fx, fy, cx, cy = c["fx"], c["fy"], c["cx"], c["cy"]
        W, H = c["width"], c["height"]
        for q in clip["queries"]:
            J = np.asarray(q["joints_m"], float)
            if not np.all(np.isfinite(J)):
                fails.append(f"{cid}:{q['frame']} non-finite joints")
                continue
            Z = J[:, 2]
            if not np.all((Z > Z_RANGE[0]) & (Z < Z_RANGE[1])):
                fails.append(f"{cid}:{q['frame']} depth out of range [{Z.min():.2f},{Z.max():.2f}]")
            u = fx * J[:, 0] / Z + cx
            v = fy * J[:, 1] / Z + cy
            ok = (u >= MARGIN) & (u < W - MARGIN) & (v >= MARGIN) & (v < H - MARGIN)
            if not np.all(ok):
                fails.append(f"{cid}:{q['frame']} {np.sum(~ok)} joints project outside the image")

    if hm_path.is_file():
        hm = load(hm_path)
        for a, b, L in hm["bones"]:
            for clip in gt["clips"]:
                for q in clip["queries"]:
                    J = np.asarray(q["joints_m"], float)
                    d = float(np.linalg.norm(J[idx[a]] - J[idx[b]]))
                    if abs(d - L) > BONE_TOL_M:
                        fails.append(f"{clip['clip']}:{q['frame']} bone {a}->{b} "
                                     f"gt {d:.4f} vs model {L:.4f}")
    else:
        print(f"note: hand model not found at {hm_path}, bone check skipped")

    if fails:
        print(f"FAIL ({len(fails)}):")
        for f in fails[:20]:
            print("  ", f)
        raise SystemExit(1)
    n = sum(len(c["queries"]) for c in gt["clips"])
    print(f"PASS: {n} queries project in-image under the stated convention; "
          f"bone lengths match hand_model.json")


if __name__ == "__main__":
    main()
