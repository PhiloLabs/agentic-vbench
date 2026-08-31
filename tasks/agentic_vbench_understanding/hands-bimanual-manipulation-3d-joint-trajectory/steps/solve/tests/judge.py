#!/usr/bin/env python3
"""Task 1 scorer: right-hand 3D joint trajectory across three egocentric clips.
Deterministic, numpy only (no VLM/LLM).

For each query frame the agent submits the 20 right-hand joints in that clip's RGB
camera frame, in metres. Each joint is scored by a soft hit on its L2 error d:

    joint_score = clip(1 - d / TAU, 0, 1)

reward = mean joint_score over every (clip, query frame, joint). A frame that is
missing, malformed, or has the wrong joint count contributes 0 for all its joints.

At the tolerance distance TAU a joint earns 0; an exact joint earns 1. The exact joint
list (the oracle) scores 1.0; an empty/None submission scores 0.0; a guess scores ~0.
Recovering metric 3D joints from a single monocular view is the hard part.
The answer only comes from actually working the geometry across many frames.
"""
import argparse
import json
from pathlib import Path

import numpy as np

TAU = 0.03  # 3 cm: joint L2 error at which the soft score reaches 0


def _load_gt():
    return json.loads((Path(__file__).with_name("ground_truth.json")).read_text())


def _index_pred(pred):
    """clip_id -> {frame -> (N,3) array}."""
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
                if isinstance(e, dict) and "frame" in e and "joints_m" in e:
                    try:
                        fr[int(e["frame"])] = np.asarray(e["joints_m"], float)
                    except Exception:
                        continue
        out[cid] = fr
    return out


def score(pred, gt):
    n_joints = len(gt["joint_names"])
    pred_idx = _index_pred(pred)

    total = 0
    acc = 0.0
    per_clip = {}
    for clip in gt["clips"]:
        cid = clip["clip"]
        pfr = pred_idx.get(cid, {})
        clip_hits = []
        for q in clip["queries"]:
            f = int(q["frame"])
            g = np.asarray(q["joints_m"], float)
            total += n_joints
            p = pfr.get(f)
            if p is None or p.shape != g.shape or not np.all(np.isfinite(p)):
                clip_hits.append(0.0)
                continue
            d = np.linalg.norm(p - g, axis=1)
            js = np.clip(1.0 - d / TAU, 0.0, 1.0)
            acc += float(js.sum())
            clip_hits.append(round(float(js.mean()), 4))
        per_clip[cid] = clip_hits
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
        "tau_m": TAU,
        "n_clips": len(gt["clips"]),
        "n_query_frames": sum(len(c["queries"]) for c in gt["clips"]),
        "n_joints": len(gt["joint_names"]),
        "scored_units": total,
        "per_clip_frame_mean_hit": per_clip,
    }
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps({"reward": round(reward, 4), "details": details}, indent=2))
    args.reward_txt.write_text(f"{round(reward, 4)}\n")


if __name__ == "__main__":
    main()
