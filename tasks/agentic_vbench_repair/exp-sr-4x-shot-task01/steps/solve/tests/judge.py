#!/usr/bin/env python3
"""Shot-scoped super-resolution judge.

Components:
  - localization_iou: 1-D IoU between agent range and GT range.
  - quality_score:    in-shot PSNR-Y + SSIM-Y vs held-out original.
                      psnr_n = clip01((mean_PSNR - 15) / 25)
                      ssim_n = clip01(mean_SSIM)
                      quality_score = 0.5 * psnr_n + 0.5 * ssim_n
  - out_score:        min(mean_PSNR(input, output, frames OUTSIDE agent
                                    range) / 50, 1.0)

  reward = 0.7 * quality_score + 0.2 * iou + 0.1 * out_score

Y channel uses BT.601 luma: Y = 0.299 R + 0.587 G + 0.114 B (on RGB
[0,255]). OpenCV gives BGR so we use the standard cvtColor mapping.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from skimage.metrics import structural_similarity


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _zero(reason: str, **kw) -> dict:
    return {"reward": 0.0, "details": {"reason": reason, **kw}}


def _read_frame(cap, idx: int) -> np.ndarray | None:
    cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, idx))
    ok, frame = cap.read()
    return frame if ok else None


def _bgr_to_y(frame_bgr: np.ndarray) -> np.ndarray:
    """BT.601 luma (Y channel of YCrCb), float32 in [0, 255]."""
    ycrcb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2YCrCb)
    return ycrcb[..., 0].astype(np.float32)


def _psnr_y(a_bgr: np.ndarray, b_bgr: np.ndarray) -> float:
    """PSNR on Y channel, data_range=255. Identical inputs → 100 dB."""
    ya = _bgr_to_y(a_bgr)
    yb = _bgr_to_y(b_bgr)
    if ya.shape != yb.shape:
        yb = cv2.resize(yb, (ya.shape[1], ya.shape[0]),
                        interpolation=cv2.INTER_AREA)
    mse = float(np.mean((ya - yb) ** 2))
    if mse <= 1e-8:
        return 100.0
    return float(10.0 * np.log10((255.0 ** 2) / mse))


def _ssim_y(a_bgr: np.ndarray, b_bgr: np.ndarray) -> float:
    ya = _bgr_to_y(a_bgr)
    yb = _bgr_to_y(b_bgr)
    if ya.shape != yb.shape:
        yb = cv2.resize(yb, (ya.shape[1], ya.shape[0]),
                        interpolation=cv2.INTER_AREA)
    return float(structural_similarity(ya, yb, data_range=255.0))


def _iou_ranges(a0: int, a1: int, b0: int, b1: int) -> float:
    if a1 < a0 or b1 < b0:
        return 0.0
    inter = max(0, min(a1, b1) - max(a0, b0) + 1)
    union = (a1 - a0 + 1) + (b1 - b0 + 1) - inter
    if union <= 0:
        return 0.0
    return inter / union


def _n_frames(path: Path) -> int:
    cap = cv2.VideoCapture(str(path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return n


def score(output_mp4: Path, output_json: Path, gt_shot_json: Path,
          corrupted_mp4: Path, original_mp4: Path) -> dict:
    if not output_mp4.exists():
        return _zero(f"no output.mp4 at {output_mp4}")
    if not gt_shot_json.exists():
        return _zero(f"missing gt_shot.json at {gt_shot_json}")
    if not corrupted_mp4.exists():
        return _zero(f"missing corrupted.mp4 at {corrupted_mp4}")
    if not original_mp4.exists():
        return _zero(f"missing original.mp4 at {original_mp4}")

    try:
        gt = json.loads(gt_shot_json.read_text())
        gt_lo = int(gt["start_frame"])
        gt_hi = int(gt["end_frame"])
    except Exception as e:
        return _zero(f"bad gt_shot.json: {e}")

    # ---- parse agent json ----
    agent_lo, agent_hi = -1, -2
    agent_json_err = None
    if output_json.exists():
        try:
            aj = json.loads(output_json.read_text())
            agent_lo = int(aj.get("start_frame", -1))
            agent_hi = int(aj.get("end_frame", -2))
            if agent_hi < agent_lo:
                agent_json_err = "end_frame < start_frame"
                agent_lo, agent_hi = -1, -2
        except Exception as e:
            agent_json_err = f"parse error: {e}"
    else:
        agent_json_err = "output.json missing"

    n_out = _n_frames(output_mp4)
    n_corr = _n_frames(corrupted_mp4)
    n_orig = _n_frames(original_mp4)
    if n_out <= 0:
        return _zero("output.mp4 has no decodable frames")

    # ---- localization IoU ----
    iou = _iou_ranges(agent_lo, agent_hi, gt_lo, gt_hi)

    # ---- in-shot quality (PSNR-Y + SSIM-Y vs ORIGINAL on GT range) ----
    cap_out = cv2.VideoCapture(str(output_mp4))
    cap_orig = cv2.VideoCapture(str(original_mp4))
    psnrs = []
    ssims = []
    in_lo = max(0, min(n_out - 1, gt_lo))
    in_hi = max(in_lo, min(n_out - 1, gt_hi))
    for fi in range(in_lo, in_hi + 1):
        of = _read_frame(cap_out, fi)
        gf = _read_frame(cap_orig, fi)
        if of is None or gf is None:
            continue
        try:
            psnrs.append(_psnr_y(gf, of))
            ssims.append(_ssim_y(gf, of))
        except Exception:
            continue
    cap_out.release()
    cap_orig.release()
    if not psnrs:
        return _zero("no in-shot frames could be scored",
                     agent_range=[agent_lo, agent_hi], gt_range=[gt_lo, gt_hi])
    mean_psnr_in = float(np.mean(psnrs))
    mean_ssim_in = float(np.mean(ssims))
    psnr_n = _clip01((mean_psnr_in - 15.0) / 25.0)
    ssim_n = _clip01(mean_ssim_in)
    quality_score = 0.5 * psnr_n + 0.5 * ssim_n

    # ---- preservation: out-of-range PSNR between corrupted input and output ----
    cap_in = cv2.VideoCapture(str(corrupted_mp4))
    cap_out = cv2.VideoCapture(str(output_mp4))
    out_psnrs = []
    n_compare = min(n_out, n_corr)
    # If agent_lo / agent_hi are invalid, treat as empty → score whole video.
    has_valid_agent = agent_hi >= agent_lo and agent_lo >= 0
    for fi in range(n_compare):
        if has_valid_agent and agent_lo <= fi <= agent_hi:
            continue
        cap_in.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ok1, in_f = cap_in.read()
        cap_out.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ok2, out_f = cap_out.read()
        if not ok1 or not ok2:
            continue
        try:
            out_psnrs.append(_psnr_y(in_f, out_f))
        except Exception:
            continue
    cap_in.release()
    cap_out.release()
    if out_psnrs:
        mean_psnr_out = float(np.mean(out_psnrs))
    else:
        # agent claimed whole video → treat as full credit.
        mean_psnr_out = 100.0
    out_score = _clip01(mean_psnr_out / 50.0)

    reward = 0.7 * quality_score + 0.2 * iou + 0.1 * out_score
    return {
        "reward": float(reward),
        "details": {
            "reason": "ok",
            "task_type": "sr-shot",
            "agent_range": [agent_lo, agent_hi],
            "gt_range": [gt_lo, gt_hi],
            "agent_json_err": agent_json_err,
            "localization_iou": iou,
            "in_shot": {
                "n_frames": len(psnrs),
                "mean_psnr_y_db": mean_psnr_in,
                "mean_ssim_y": mean_ssim_in,
                "psnr_n": psnr_n,
                "ssim_n": ssim_n,
                "quality_score": quality_score,
            },
            "preservation": {
                "n_compared": len(out_psnrs),
                "mean_psnr_db": mean_psnr_out,
                "out_score": out_score,
            },
            "weights": {"quality": 0.7, "iou": 0.2, "preservation": 0.1},
        },
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output-mp4", required=True, type=Path)
    p.add_argument("--output-json", required=True, type=Path)
    p.add_argument("--gt-shot-json", required=True, type=Path)
    p.add_argument("--corrupted", required=True, type=Path)
    p.add_argument("--original", required=True, type=Path)
    p.add_argument("--reward-json", required=True, type=Path)
    p.add_argument("--reward-txt", required=True, type=Path)
    args = p.parse_args()

    result = score(args.output_mp4, args.output_json, args.gt_shot_json,
                   args.corrupted, args.original)
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps(result, indent=2))
    args.reward_txt.write_text(f"{result['reward']:.6f}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
