#!/usr/bin/env python3
"""Task 2 scorer: object 6DoF pose trajectory across three egocentric clips.
Deterministic, numpy only (scipy only for symmetric objects; none here).

For each query frame the agent submits the target object's pose in the RGB camera
frame: translation (metres) + unit quaternion (w,x,y,z). Scored with the ADD metric
(Hinterstoisser / BOP): transform the object's baked mesh points by the predicted and
the ground-truth pose, average the per-point Euclidean distance e, then

    frame_score = clip(1 - e / TAU, 0, 1),   TAU = ADD_FRAC * object_diameter

reward = mean frame_score over all (clip, query frame). Symmetric objects (flagged per
clip) use ADD-S (nearest-neighbour). Missing/malformed frames contribute 0.

The oracle poses score 1.0; an empty/None submission 0.0; a guess ~0. Recovering a
metric 6DoF pose (translation and rotation) of a hand-held object from a monocular
clip is the hard part. A wrong rotation or wrong metric depth both fail.
"""
import argparse
import json
from pathlib import Path

import numpy as np

ADD_FRAC = 0.10  # tolerance = 10% of the object diameter (BOP ADD-0.1d)


def _load_gt():
    return json.loads((Path(__file__).with_name("ground_truth.json")).read_text())


def quat_wxyz_to_R(q):
    q = np.asarray(q, float)
    n = np.linalg.norm(q)
    if n == 0 or not np.isfinite(n):
        return None
    w, x, y, z = q / n
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


def add_error(pts, R_p, t_p, R_g, t_g, symmetric):
    P = (R_p @ pts.T).T + t_p
    G = (R_g @ pts.T).T + t_g
    if symmetric:
        from scipy.spatial import cKDTree
        d, _ = cKDTree(G).query(P)
        return float(d.mean())
    return float(np.linalg.norm(P - G, axis=1).mean())


def _index_pred(pred):
    out = {}
    if not isinstance(pred, dict):
        return out
    clips = pred.get("clips", {})
    if not isinstance(clips, dict):
        return out
    for cid, entries in clips.items():
        fr = {}
        if isinstance(entries, list):
            for e in entries:
                if isinstance(e, dict) and "frame" in e:
                    # malformed frame ids (null, strings, floats with remainder) get no
                    # credit for that entry instead of aborting the whole grading run
                    try:
                        fr[int(e["frame"])] = e
                    except (TypeError, ValueError):
                        continue
        out[cid] = fr
    return out


def score(pred, gt):
    pred_idx = _index_pred(pred)
    total = 0
    acc = 0.0
    per_clip = {}
    for clip in gt["clips"]:
        cid = clip["clip"]
        pts = np.asarray(clip["mesh_points_obj"], float)
        tau = ADD_FRAC * clip["mesh_diag_m"]
        symmetric = bool(clip.get("symmetric", False))
        pfr = pred_idx.get(cid, {})
        hits = []
        for q in clip["queries"]:
            f = int(q["frame"])
            R_g = quat_wxyz_to_R(q["q_wxyz"])
            t_g = np.asarray(q["t_xyz_m"], float)
            total += 1
            s = 0.0
            p = pfr.get(f)
            if p is not None:
                try:
                    R_p = quat_wxyz_to_R(p["q_wxyz"])
                    t_p = np.asarray(p["t_xyz_m"], float)
                    if R_p is not None and t_p.shape == (3,) and np.all(np.isfinite(t_p)):
                        e = add_error(pts, R_p, t_p, R_g, t_g, symmetric)
                        s = float(np.clip(1.0 - e / tau, 0.0, 1.0))
                except Exception:
                    s = 0.0
            acc += s
            hits.append(round(s, 4))
        per_clip[cid] = {"object": clip["object"], "tau_m": round(tau, 5),
                         "metric": "ADD-S" if symmetric else "ADD", "scores": hits}
    reward = acc / total if total else 0.0
    return reward, per_clip, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", required=True, type=Path)
    ap.add_argument("--reward-json", required=True, type=Path)
    ap.add_argument("--reward-txt", required=True, type=Path)
    args = ap.parse_args()

    gt = _load_gt()
    reason = "ok"
    try:
        pred = json.loads(args.solution.read_text())
    except Exception as exc:  # noqa: BLE001
        pred, reason = None, f"unreadable solution.json: {exc}"

    reward, per_clip, total = score(pred, gt)
    details = {
        "reason": reason,
        "n_clips": len(gt["clips"]),
        "n_query_frames": total,
        "per_clip": per_clip,
    }
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps({"reward": round(reward, 4), "details": details}, indent=2))
    args.reward_txt.write_text(f"{round(reward, 4)}\n")


if __name__ == "__main__":
    main()
