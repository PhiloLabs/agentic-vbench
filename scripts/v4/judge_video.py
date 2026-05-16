"""v4 video judges — color, deblur, sr, swap.

All four families share:
  - Streaming frame readers (cv2.VideoCapture).
  - LPIPS feature distance (Zhang et al. CVPR 2018), AlexNet backbone, on CPU.
  - Universal normalize-improvement form against per-task (broken, golden) anchors.

Family metric choices:
  color_shot    ΔE_2000 (CIEDE2000) in-window — perceptually-corrected colour distance
  deblur        LPIPS (mask-cropped × in-window) — perceptual, paper standard for GoPro/REDS
  sr_shot       LPIPS in-window + 0.3 × Y-PSNR-norm composite — NTIRE perceptual track style
  swap          LPIPS on swap-window (per range) — captures identity/content change
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import cv2
import numpy as np
import torch

warnings.filterwarnings("ignore")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _framework import (  # noqa: E402
    append_tsv,
    get_task_paths,
    normalize_improvement,
    read_window_json,
    resize_to,
    write_v4_result,
)


_LPIPS_MODEL = None


def _get_lpips():
    global _LPIPS_MODEL
    if _LPIPS_MODEL is None:
        import lpips
        # AlexNet backbone — fastest, NTIRE-canonical
        _LPIPS_MODEL = lpips.LPIPS(net="alex", verbose=False).eval()
        # MPS on Apple Silicon if available, else CPU
        if torch.backends.mps.is_available():
            try:
                _LPIPS_MODEL = _LPIPS_MODEL.to("mps")
            except Exception:
                pass
    return _LPIPS_MODEL


def _to_lpips_tensor(frame_bgr: np.ndarray) -> torch.Tensor:
    """BGR uint8 HxWx3 -> RGB float [-1, 1] tensor 1x3xHxW."""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 127.5 - 1.0
    t = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0)
    return t


def _lpips_distance(model, a_bgr: np.ndarray, b_bgr: np.ndarray) -> float:
    """LPIPS distance between two BGR uint8 frames."""
    ta = _to_lpips_tensor(a_bgr)
    tb = _to_lpips_tensor(b_bgr)
    dev = next(model.parameters()).device
    ta = ta.to(dev)
    tb = tb.to(dev)
    with torch.no_grad():
        d = model(ta, tb).item()
    return float(d)


def _psnr_y(a: np.ndarray, b: np.ndarray) -> float:
    """PSNR on Y-channel (BT.601) for two BGR uint8 frames."""
    ay = cv2.cvtColor(a, cv2.COLOR_BGR2YCrCb)[..., 0].astype(np.float64)
    by = cv2.cvtColor(b, cv2.COLOR_BGR2YCrCb)[..., 0].astype(np.float64)
    mse = float(np.mean((ay - by) ** 2))
    if mse < 1e-10:
        return 60.0
    return 10.0 * float(np.log10(255.0 ** 2 / mse))


def _deltaE_2000(a_bgr: np.ndarray, b_bgr: np.ndarray) -> float:
    """Mean per-pixel CIEDE2000 between two BGR uint8 frames."""
    from skimage.color import deltaE_ciede2000, rgb2lab

    a_rgb = cv2.cvtColor(a_bgr, cv2.COLOR_BGR2RGB).astype(np.float64) / 255.0
    b_rgb = cv2.cvtColor(b_bgr, cv2.COLOR_BGR2RGB).astype(np.float64) / 255.0
    a_lab = rgb2lab(a_rgb)
    b_lab = rgb2lab(b_rgb)
    return float(np.mean(deltaE_ciede2000(a_lab, b_lab)))


# ── frame-range iterators ───────────────────────────────────────────────────

def _iter_triplet(broken: Path, golden: Path, claude: Path, start: int, end: int):
    """Yield (frame_idx, broken_bgr, golden_bgr, claude_bgr) for idx ∈ [start, end)."""
    cb = cv2.VideoCapture(str(broken))
    cg = cv2.VideoCapture(str(golden))
    cc = cv2.VideoCapture(str(claude))
    try:
        cb.set(cv2.CAP_PROP_POS_FRAMES, start)
        cg.set(cv2.CAP_PROP_POS_FRAMES, start)
        cc.set(cv2.CAP_PROP_POS_FRAMES, start)
        idx = start
        while idx < end:
            okb, fb = cb.read()
            okg, fg = cg.read()
            okc, fc = cc.read()
            if not (okb and okg and okc):
                break
            # Resize claude/broken to match golden's resolution if needed.
            if fc.shape[:2] != fg.shape[:2]:
                fc = resize_to(fc, fg.shape[0], fg.shape[1])
            if fb.shape[:2] != fg.shape[:2]:
                fb = resize_to(fb, fg.shape[0], fg.shape[1])
            yield idx, fb, fg, fc
            idx += 1
    finally:
        cb.release(); cg.release(); cc.release()


def _video_dims(path: Path) -> tuple[int, int, int]:
    cap = cv2.VideoCapture(str(path))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return h, w, n


# ── color judges ────────────────────────────────────────────────────────────

def judge_color(task_id: str) -> dict:
    t0 = time.time()
    p = get_task_paths(task_id)
    win = read_window_json(p.window_json)
    start = int(win["window_start_frame"])
    end = int(win["window_end_frame"])

    de_broken_sum = 0.0
    de_claude_sum = 0.0
    lpips_broken_sum = 0.0
    lpips_claude_sum = 0.0
    n = 0
    lp = _get_lpips()
    for idx, fb, fg, fc in _iter_triplet(p.broken, p.golden, p.claude, start, end):
        de_broken_sum += _deltaE_2000(fb, fg)
        de_claude_sum += _deltaE_2000(fc, fg)
        lpips_broken_sum += _lpips_distance(lp, fb, fg)
        lpips_claude_sum += _lpips_distance(lp, fc, fg)
        n += 1

    if n == 0:
        raise RuntimeError(f"{task_id}: no frames in window")

    m_broken = de_broken_sum / n
    m_golden = 0.0
    m_claude = de_claude_sum / n
    score, reason = normalize_improvement(m_claude, m_broken, m_golden, higher_is_better=False)

    lpips_b = lpips_broken_sum / n
    lpips_c = lpips_claude_sum / n

    details = {
        "metric_primary": "deltaE_2000",
        "in_window_only": True,
        "window_frames": [start, end],
        "n_frames_scored": n,
        "deltaE_2000": {"broken": m_broken, "golden": m_golden, "claude": m_claude,
                         "unit": "CIEDE2000, lower-better"},
        "lpips_diagnostic": {"broken": lpips_b, "golden": 0.0, "claude": lpips_c},
        "elapsed_s": time.time() - t0,
        "reason": reason,
    }
    write_v4_result(task_id, "color_shot", "deltaE_2000", m_broken, m_golden, m_claude, score, score, details)
    append_tsv(task_id, "color_shot", "deltaE_2000", m_broken, m_golden, m_claude, score, score)
    return {"task": task_id, "score": score, "details": details}


# ── deblur judges ───────────────────────────────────────────────────────────

def _load_mask_bbox(mask_path: Path) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """Load mask and compute its tight bbox (x0, y0, x1, y1).

    Returns (mask_uint8, bbox). If mask is full-frame, bbox covers the whole frame.
    """
    m = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
    if m is None:
        raise RuntimeError(f"could not load mask: {mask_path}")
    binmask = (m > 127).astype(np.uint8)
    ys, xs = np.where(binmask > 0)
    if len(ys) == 0:
        # Fall back to full-frame bbox
        return binmask, (0, 0, m.shape[1], m.shape[0])
    return binmask, (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def _crop_to_bbox(frame: np.ndarray, bbox: tuple[int, int, int, int],
                  frame_h: int, frame_w: int, mask_h: int, mask_w: int) -> np.ndarray:
    """Crop a frame at bbox coords expressed in mask resolution.

    If frame is at a different resolution than the mask, scale the bbox.
    """
    x0, y0, x1, y1 = bbox
    if frame_h != mask_h or frame_w != mask_w:
        sx = frame_w / mask_w
        sy = frame_h / mask_h
        x0 = int(round(x0 * sx)); x1 = int(round(x1 * sx))
        y0 = int(round(y0 * sy)); y1 = int(round(y1 * sy))
    x0 = max(0, min(x0, frame_w - 1)); x1 = max(x0 + 1, min(x1, frame_w))
    y0 = max(0, min(y0, frame_h - 1)); y1 = max(y0 + 1, min(y1, frame_h))
    return frame[y0:y1, x0:x1]


def judge_deblur(task_id: str) -> dict:
    t0 = time.time()
    p = get_task_paths(task_id)
    win = read_window_json(p.window_json)
    start = int(win["window_start_frame"])
    end = int(win["window_end_frame"])

    mask, bbox = _load_mask_bbox(p.mask_png)
    mask_h, mask_w = mask.shape[:2]

    # Probe resolutions
    gh, gw, _ = _video_dims(p.golden)

    lp = _get_lpips()
    lpips_b_sum = 0.0; lpips_c_sum = 0.0
    psnr_b_sum = 0.0; psnr_c_sum = 0.0
    n = 0
    for idx, fb, fg, fc in _iter_triplet(p.broken, p.golden, p.claude, start, end):
        # Crop to mask bbox at this frame's resolution
        fh, fw = fg.shape[:2]
        fb_c = _crop_to_bbox(fb, bbox, fh, fw, mask_h, mask_w)
        fg_c = _crop_to_bbox(fg, bbox, fh, fw, mask_h, mask_w)
        fc_c = _crop_to_bbox(fc, bbox, fh, fw, mask_h, mask_w)
        # Resize claude crop to match golden crop dims if differ
        if fc_c.shape[:2] != fg_c.shape[:2]:
            fc_c = resize_to(fc_c, fg_c.shape[0], fg_c.shape[1])
        lpips_b_sum += _lpips_distance(lp, fb_c, fg_c)
        lpips_c_sum += _lpips_distance(lp, fc_c, fg_c)
        psnr_b_sum += _psnr_y(fb_c, fg_c)
        psnr_c_sum += _psnr_y(fc_c, fg_c)
        n += 1

    if n == 0:
        raise RuntimeError(f"{task_id}: no frames in window")

    m_broken = lpips_b_sum / n
    m_golden = 0.0
    m_claude = lpips_c_sum / n
    score, reason = normalize_improvement(m_claude, m_broken, m_golden, higher_is_better=False)

    psnr_b = psnr_b_sum / n
    psnr_c = psnr_c_sum / n

    details = {
        "metric_primary": "lpips_inmask",
        "in_window_only": True,
        "window_frames": [start, end],
        "n_frames_scored": n,
        "mask_bbox": list(bbox),
        "lpips_inmask": {"broken": m_broken, "golden": m_golden, "claude": m_claude,
                         "unit": "LPIPS, lower-better"},
        "psnr_y_inmask_diagnostic": {"broken": psnr_b, "claude": psnr_c, "unit": "dB"},
        "elapsed_s": time.time() - t0,
        "reason": reason,
    }
    write_v4_result(task_id, "mask_blur", "lpips_inmask", m_broken, m_golden, m_claude, score, score, details)
    append_tsv(task_id, "mask_blur", "lpips_inmask", m_broken, m_golden, m_claude, score, score)
    return {"task": task_id, "score": score, "details": details}


# ── sr judges ───────────────────────────────────────────────────────────────

def judge_sr(task_id: str) -> dict:
    t0 = time.time()
    p = get_task_paths(task_id)
    with open(p.gt_shot_json) as f:
        gt = json.load(f)
    start = int(gt["start_frame"])
    end = int(gt["end_frame"])

    lp = _get_lpips()
    lpips_b_sum = 0.0; lpips_c_sum = 0.0
    psnr_b_sum = 0.0; psnr_c_sum = 0.0
    n = 0
    for idx, fb, fg, fc in _iter_triplet(p.broken, p.golden, p.claude, start, end):
        lpips_b_sum += _lpips_distance(lp, fb, fg)
        lpips_c_sum += _lpips_distance(lp, fc, fg)
        psnr_b_sum += _psnr_y(fb, fg)
        psnr_c_sum += _psnr_y(fc, fg)
        n += 1

    if n == 0:
        raise RuntimeError(f"{task_id}: no frames in window")

    m_broken = lpips_b_sum / n
    m_golden = 0.0
    m_claude = lpips_c_sum / n
    score_lpips, _ = normalize_improvement(m_claude, m_broken, m_golden, higher_is_better=False)

    # Composite: 0.7 * LPIPS + 0.3 * Y-PSNR (REDS/NTIRE blend)
    # Anchor golden PSNR at 50 dB (above this is indistinguishable from original).
    psnr_b = psnr_b_sum / n
    psnr_c = psnr_c_sum / n
    psnr_g_cap = 50.0
    score_psnr, _ = normalize_improvement(psnr_c, psnr_b, psnr_g_cap, higher_is_better=True)

    score = 0.7 * score_lpips + 0.3 * score_psnr
    score = float(max(0.0, min(1.0, score)))

    details = {
        "metric_primary": "lpips_psnr_composite",
        "in_window_only": True,
        "window_frames": [start, end],
        "n_frames_scored": n,
        "weights": {"lpips": 0.7, "psnr_y": 0.3},
        "lpips_psnr_composite": {"broken": 0.0, "golden": 1.0, "claude": score,
                                  "unit": "calibrated [0,1]; composite of LPIPS and Y-PSNR"},
        "lpips": {"broken": m_broken, "golden": 0.0, "claude": m_claude,
                  "unit": "LPIPS, lower-better"},
        "psnr_y": {"broken": psnr_b, "golden_cap_db": psnr_g_cap, "claude": psnr_c},
        "sub_scores": {"lpips_only": score_lpips, "psnr_only": score_psnr},
        "elapsed_s": time.time() - t0,
        "reason": "ok",
    }
    write_v4_result(task_id, "sr_shot", "lpips_psnr_composite", 0.0, 1.0, score, score, score, details)
    append_tsv(task_id, "sr_shot", "lpips_psnr_composite", 0.0, 1.0, score, score, score)
    return {"task": task_id, "score": score, "details": details}


# ── swap judges ─────────────────────────────────────────────────────────────

def judge_swap(task_id: str, tolerance_frames: int = 5) -> dict:
    """Score the SWAPPED regions only, with a ±tolerance_frames offset search.

    Rationale: the swap corruption recipe involves keyframe-aligned concat +
    AAC priming, both of which can shift video frame boundaries by 1–3 frames
    at shot boundaries. The recipe records these shifts in `gt_swap.json`
    (corrupted_start ≠ original_start), but a frame-perfect output isn't a
    meaningful task signal — any real shot-detection tool treats boundaries
    with the same kind of tolerance. So this judge searches over offsets in
    [-tolerance_frames, +tolerance_frames] for each shot and takes the BEST
    (minimum) LPIPS alignment. Applied symmetrically to both broken and
    claude so anchors stay consistent.
    """
    t0 = time.time()
    p = get_task_paths(task_id)
    with open(p.gt_swap_json) as f:
        gt = json.load(f)

    lp = _get_lpips()
    n_total = 0
    lpips_b_sum = 0.0; lpips_c_sum = 0.0
    psnr_b_sum = 0.0; psnr_c_sum = 0.0
    per_shot_offsets = []  # diagnostic: best offset chosen per swap entry
    for swap_entry, original_entry in zip(gt["swap"], gt["swap_original_timeline"]):
        cs, ce = int(swap_entry["corrupted_start"]), int(swap_entry["corrupted_end"])
        os_, oe = int(original_entry["original_start"]), int(original_entry["original_end"])
        span = min(ce - cs, oe - os_)

        # Pre-load original frames at [os_, os_ + span)
        gold_frames = []
        cg = cv2.VideoCapture(str(p.golden))
        cg.set(cv2.CAP_PROP_POS_FRAMES, os_)
        for _ in range(span):
            ok, f = cg.read()
            if not ok: break
            gold_frames.append(f)
        cg.release()

        # Pre-load output (claude) and broken frames at
        # [cs - tolerance, cs + span + tolerance) so we can search offsets.
        out_start = max(0, cs - tolerance_frames)
        out_count = (cs + span + tolerance_frames) - out_start

        def _load(path, start, count):
            cap = cv2.VideoCapture(str(path))
            cap.set(cv2.CAP_PROP_POS_FRAMES, start)
            frames = []
            for _ in range(count):
                ok, f = cap.read()
                if not ok: break
                if gold_frames and f.shape[:2] != gold_frames[0].shape[:2]:
                    f = resize_to(f, gold_frames[0].shape[0], gold_frames[0].shape[1])
                frames.append(f)
            cap.release()
            return frames

        claude_frames = _load(p.claude, out_start, out_count)
        broken_frames = _load(p.broken, out_start, out_count)

        def best_alignment(out_frames, gold_frames, start_in_out_buf):
            """Search offsets and return (best_lpips_sum, best_psnr_sum, best_offset)
            where summed over span. start_in_out_buf = index in out_frames that
            corresponds to corrupted_start (offset 0)."""
            best_lpips = float("inf")
            best_psnr = float("-inf")
            best_off = 0
            for off in range(-tolerance_frames, tolerance_frames + 1):
                lp_sum = 0.0
                ps_sum = 0.0
                valid = 0
                for k in range(span):
                    out_idx = start_in_out_buf + k + off
                    if 0 <= out_idx < len(out_frames):
                        lp_sum += _lpips_distance(lp, out_frames[out_idx], gold_frames[k])
                        ps_sum += _psnr_y(out_frames[out_idx], gold_frames[k])
                        valid += 1
                if valid != span:
                    # Penalise out-of-buffer frames with LPIPS=1, PSNR=10 dB
                    lp_sum += (span - valid) * 1.0
                    ps_sum += (span - valid) * 10.0
                if lp_sum < best_lpips:
                    best_lpips = lp_sum
                    best_psnr = ps_sum
                    best_off = off
            return best_lpips, best_psnr, best_off

        start_in_buf = cs - out_start  # index in *_frames buffer for corrupted_start
        c_lpips, c_psnr, c_off = best_alignment(claude_frames, gold_frames, start_in_buf)
        b_lpips, b_psnr, b_off = best_alignment(broken_frames, gold_frames, start_in_buf)

        lpips_c_sum += c_lpips
        psnr_c_sum += c_psnr
        lpips_b_sum += b_lpips
        psnr_b_sum += b_psnr
        n_total += span
        per_shot_offsets.append({
            "swap_index": len(per_shot_offsets),
            "claude_best_offset": c_off,
            "broken_best_offset": b_off,
            "span": span,
        })

    if n_total == 0:
        raise RuntimeError(f"{task_id}: no frames in swap windows")

    m_broken = lpips_b_sum / n_total
    m_golden = 0.0
    m_claude = lpips_c_sum / n_total
    score, reason = normalize_improvement(m_claude, m_broken, m_golden, higher_is_better=False)

    psnr_b = psnr_b_sum / n_total
    psnr_c = psnr_c_sum / n_total

    details = {
        "metric_primary": "lpips_swap_window",
        "swap_window_only": True,
        "tolerance_frames": tolerance_frames,
        "n_frames_scored": n_total,
        "n_swap_segments": len(gt["swap"]),
        "per_shot_offsets": per_shot_offsets,
        "lpips_swap_window": {"broken": m_broken, "golden": 0.0, "claude": m_claude,
                              "unit": "LPIPS, lower-better, ±5-frame offset search",
                              "tolerance_note": "Accounts for AAC-priming/keyframe drift at shot boundaries"},
        "psnr_y_swap_window_diagnostic": {"broken": psnr_b, "claude": psnr_c},
        "elapsed_s": time.time() - t0,
        "reason": reason,
    }
    write_v4_result(task_id, "swap", "lpips_swap_window", m_broken, m_golden, m_claude, score, score, details)
    append_tsv(task_id, "swap", "lpips_swap_window", m_broken, m_golden, m_claude, score, score)
    return {"task": task_id, "score": score, "details": details}


# ── driver ──────────────────────────────────────────────────────────────────

JUDGES = {
    "exp-color-shot-visit-korea-task01": judge_color,
    "exp-color-shot-gobelins-task01": judge_color,
    "exp-color-shot-v3-s1-task01": judge_color,
    "exp-deblur-motion-f1-task01": judge_deblur,
    "exp-deblur-gaussian-mkbhd-task01": judge_deblur,
    "exp-sr-2x-shot-task01": judge_sr,
    "exp-sr-4x-shot-task01": judge_sr,
    "exp-swap-car-task01": judge_swap,
    "exp-swap-product-task01": judge_swap,
}


def main(argv: list[str]) -> int:
    tasks = argv[1:] or list(JUDGES.keys())
    print(f"v4 video judge: scoring {len(tasks)} task(s)")
    for tid in tasks:
        if tid not in JUDGES:
            print(f"[skip] unknown task: {tid}")
            continue
        try:
            r = JUDGES[tid](tid)
            d = r["details"]
            mp = d["metric_primary"]
            ms = d[mp]
            g_key = "golden" if "golden" in ms else "golden_cap_db"
            print(f"  {tid:42s} score={r['score']:.3f}  metric={mp}  m_b={ms['broken']:.3g}  m_g={ms[g_key]:.3g}  m_c={ms['claude']:.3g}  elapsed={d['elapsed_s']:.1f}s")
        except Exception as e:
            import traceback
            print(f"  {tid:42s} ERROR  {e}")
            traceback.print_exc()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
