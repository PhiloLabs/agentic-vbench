"""v4 verifier framework — shared helpers.

Universal scoring form:
    score = clip( (M_out - M_broken) / (M_golden - M_broken), 0, 1 )       # higher-better
    score = clip( (M_broken - M_out) / (M_broken - M_golden), 0, 1 )       # lower-better
"""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional

import numpy as np

EXPERIMENT_ROOT = Path(__file__).resolve().parents[2]
# v4 tasks live under tasks/agentic_vbench_repair/<task> after the family-subdir
# reorganization. Use the helper so a future re-shuffle just touches one file.
import sys as _sys
_sys.path.insert(0, str(EXPERIMENT_ROOT / "scripts"))
from _task_paths import task_dir as _task_dir, TASKS_ROOT as _TASKS_ROOT  # noqa: E402
TASKS_DIR = _TASKS_ROOT / "agentic_vbench_repair"   # v4 family pool
JOBS_DIR = EXPERIMENT_ROOT / "jobs"
LOGS_DIR = EXPERIMENT_ROOT / "logs"
V4_RESULTS_TSV = LOGS_DIR / "v4-results.tsv"
V4_PER_TASK_DIR = LOGS_DIR / "v4-per-task"
V4_PER_TASK_DIR.mkdir(parents=True, exist_ok=True)


# ── Score helper ────────────────────────────────────────────────────────────

def normalize_improvement(
    m_out: float,
    m_broken: float,
    m_golden: float,
    higher_is_better: bool = True,
    min_spread: float = 1e-6,
) -> tuple[float, str]:
    """Return (score in [0,1], reason). If spread is too small, returns (0, 'degenerate')."""
    spread = m_golden - m_broken if higher_is_better else m_broken - m_golden
    if abs(spread) < min_spread:
        return 0.0, "degenerate-spread"
    if higher_is_better:
        raw = (m_out - m_broken) / (m_golden - m_broken)
    else:
        raw = (m_broken - m_out) / (m_broken - m_golden)
    return float(max(0.0, min(1.0, raw))), "ok"


# ── Artifact finder ─────────────────────────────────────────────────────────

@dataclass
class TaskPaths:
    task_id: str
    family: str
    broken: Optional[Path] = None
    golden: Optional[Path] = None
    claude: Optional[Path] = None
    window_json: Optional[Path] = None
    mask_png: Optional[Path] = None
    clip_mask_npy: Optional[Path] = None
    gt_shot_json: Optional[Path] = None
    gt_swap_json: Optional[Path] = None
    extras: dict = field(default_factory=dict)


_FAMILY_BY_PREFIX = {
    "exp-dns-denoise": "audio_inj",
    "exp-voicebank-denoise": "audio_inj",
    "exp-dereverb": "audio_inj",
    "exp-declip": "audio_inj",
    "exp-codec-restore": "audio_inj",
    "exp-color-shot": "color_shot",
    "exp-deblur": "mask_blur",
    "exp-sr-2x": "sr_shot",
    "exp-sr-4x": "sr_shot",
    "exp-swap": "swap",
    "exp-glitch-dup": "glitch",
    "exp-content-cut": "cut",
    "exp-disfluency": "cut",
}


def family_of(task_id: str) -> str:
    for pref, fam in _FAMILY_BY_PREFIX.items():
        if task_id.startswith(pref):
            return fam
    return "unknown"


def _audio_paths(task_id: str, p: TaskPaths) -> None:
    base = TASKS_DIR / task_id / "steps" / "solve"
    p.broken = base / "workdir" / "noisy.wav"
    p.golden = base / "tests" / "clean.wav"
    win = base / "tests" / "window.json"
    if win.exists():
        p.window_json = win
    if task_id == "exp-declip-task01":
        p.clip_mask_npy = base / "tests" / "clip_mask.npy"


def _video_paths(task_id: str, p: TaskPaths) -> None:
    base = TASKS_DIR / task_id / "steps" / "solve"
    # broken — varies by family
    fam = p.family
    if fam == "color_shot":
        p.broken = base / "workdir" / "source.mp4"
        p.golden = base / "tests" / "original.mp4"
        p.window_json = base / "tests" / "gt_window.json"
    elif fam == "mask_blur":
        p.broken = base / "workdir" / "corrupted.mp4"
        p.golden = base / "tests" / "clean.mp4"
        p.window_json = base / "tests" / "gt_window.json"
        mp1 = base / "tests" / "mask.png"
        mp2 = base / "workdir" / "mask.png"
        p.mask_png = mp1 if mp1.exists() else (mp2 if mp2.exists() else None)
    elif fam == "sr_shot":
        p.broken = base / "workdir" / "corrupted.mp4"
        p.golden = base / "tests" / "original.mp4"
        gt = base / "tests" / "gt_shot.json"
        if gt.exists():
            p.gt_shot_json = gt
    elif fam == "swap":
        p.broken = base / "workdir" / "corrupted.mp4"
        p.golden = base / "tests" / "original.mp4"
        gt = base / "tests" / "gt_swap.json"
        if gt.exists():
            p.gt_swap_json = gt


def get_task_paths(task_id: str) -> TaskPaths:
    p = TaskPaths(task_id=task_id, family=family_of(task_id))
    if p.family == "audio_inj":
        _audio_paths(task_id, p)
    else:
        _video_paths(task_id, p)
    p.claude = find_latest_claude_artifact(task_id, p.family)
    return p


def find_latest_claude_artifact(task_id: str, family: str) -> Optional[Path]:
    """Look in jobs/cc-<task_id>-* (latest mtime) for the agent's output."""
    pattern = re.compile(rf"^cc-{re.escape(task_id)}-\d+$")
    candidates = []
    if not JOBS_DIR.exists():
        return None
    for d in JOBS_DIR.iterdir():
        if pattern.match(d.name):
            candidates.append(d)
    if not candidates:
        return None
    # Prefer dirs that actually contain an artifact, then by latest mtime.
    art_name = _artifact_name(family)
    scored = []
    for d in candidates:
        artifacts = list(d.glob(f"*/steps/solve/artifacts/{art_name}"))
        if not artifacts:
            continue
        # mtime of the artifact
        a = artifacts[0]
        scored.append((a.stat().st_mtime, a))
    if not scored:
        return None
    scored.sort(reverse=True)
    return scored[0][1]


def _artifact_name(family: str) -> str:
    if family == "audio_inj":
        return "enhanced.wav"
    return "output.mp4"


# ── Audio loaders ───────────────────────────────────────────────────────────

def load_audio_16k(path: Path) -> np.ndarray:
    """Return mono float32 array at 16 kHz."""
    import soundfile as sf

    data, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != 16000:
        import librosa

        data = librosa.resample(data.astype(np.float32), orig_sr=sr, target_sr=16000)
    return data.astype(np.float32)


def align_lengths(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n = min(len(a), len(b))
    return a[:n], b[:n]


def read_window_json(path: Path) -> dict:
    """Returns dict {start_s, end_s, in_weight, out_weight, ...}."""
    with open(path) as f:
        d = json.load(f)
    # Audio window.json typically: {"in_window_start_s", "in_window_end_s"}
    # Video gt_window.json typically: {"start_frame", "end_frame", "fps", "weights": {...}}
    return d


# ── Video helpers ───────────────────────────────────────────────────────────

def video_frame_count(path: Path) -> int:
    import cv2

    cap = cv2.VideoCapture(str(path))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return n


def video_fps(path: Path) -> float:
    import cv2

    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    return float(fps)


def iter_frames(path: Path) -> Iterator[np.ndarray]:
    """Yield BGR uint8 frames one at a time."""
    import cv2

    cap = cv2.VideoCapture(str(path))
    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            yield frame
    finally:
        cap.release()


def iter_aligned_frames(a: Path, b: Path) -> Iterator[tuple[int, np.ndarray, np.ndarray]]:
    """Yield (idx, frame_a, frame_b) up to the shorter length."""
    import cv2

    ca = cv2.VideoCapture(str(a))
    cb = cv2.VideoCapture(str(b))
    idx = 0
    try:
        while True:
            oka, fa = ca.read()
            okb, fb = cb.read()
            if not oka or not okb or fa is None or fb is None:
                break
            yield idx, fa, fb
            idx += 1
    finally:
        ca.release()
        cb.release()


def resize_to(frame: np.ndarray, h: int, w: int) -> np.ndarray:
    import cv2

    if frame.shape[0] == h and frame.shape[1] == w:
        return frame
    return cv2.resize(frame, (w, h), interpolation=cv2.INTER_LINEAR)


# ── Result writer ───────────────────────────────────────────────────────────

def write_v4_result(task_id: str, family: str, metric: str, m_broken: float, m_golden: float,
                    m_claude: float, score_raw: float, score_calibrated: float, details: dict):
    payload = {
        "task_id": task_id,
        "family": family,
        "metric_used": metric,
        "m_broken": m_broken,
        "m_golden": m_golden,
        "m_claude": m_claude,
        "v4_raw_reward": score_raw,
        "v4_calibrated_reward": score_calibrated,
        "details": details,
    }
    out = V4_PER_TASK_DIR / f"{task_id}.json"
    with open(out, "w") as f:
        json.dump(payload, f, indent=2)
    return out


def append_tsv(task_id: str, family: str, metric: str, m_broken: float, m_golden: float,
               m_claude: float, score_raw: float, score_calibrated: float):
    V4_RESULTS_TSV.parent.mkdir(parents=True, exist_ok=True)
    new = not V4_RESULTS_TSV.exists()
    with open(V4_RESULTS_TSV, "a") as f:
        w = csv.writer(f, delimiter="\t")
        if new:
            w.writerow(["task", "family", "metric", "m_broken", "m_golden", "m_claude",
                        "v4_raw", "v4_calibrated"])
        w.writerow([task_id, family, metric,
                    f"{m_broken:.6g}", f"{m_golden:.6g}", f"{m_claude:.6g}",
                    f"{score_raw:.6f}", f"{score_calibrated:.6f}"])


# ── Self-test ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        tid = sys.argv[1]
        p = get_task_paths(tid)
        print(f"task: {tid}  family: {p.family}")
        for fld in ("broken", "golden", "claude", "window_json", "mask_png",
                    "clip_mask_npy", "gt_shot_json", "gt_swap_json"):
            v = getattr(p, fld)
            mark = "✓" if v and v.exists() else ("✗" if v else "·")
            print(f"  {mark} {fld:18s} {v}")
    else:
        # Smoke-test on a few tasks
        for tid in ("exp-dns-denoise-task01", "exp-declip-task01",
                    "exp-color-shot-v3-s1-task01", "exp-deblur-motion-f1-task01",
                    "exp-sr-2x-shot-task01", "exp-swap-car-task01"):
            p = get_task_paths(tid)
            print(f"\n{tid}  ({p.family})")
            for fld in ("broken", "golden", "claude", "window_json"):
                v = getattr(p, fld)
                mark = "✓" if v and v.exists() else ("✗" if v else "·")
                print(f"  {mark} {fld:14s} {v}")
