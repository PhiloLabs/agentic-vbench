#!/usr/bin/env python3
"""Find where each SoccerNet half starts inside the baked broadcast.

SoccerNet-v2 gives every annotation a millisecond `position` inside its half video.
The baked clip is a different recording of the same broadcast (the official
Bundesliga YouTube upload), so each half needs one offset:

    clip_t = offset[half] + position / 1000

Anchors are SoccerNet's own public camera-shot annotations (Labels-cameras.json from
the SoccerNet/SN-Labels dataset): the annotated position of each shot change. Shot
changes in the clip come from ffmpeg's per-frame scene score. Every (anchor, detected
change) pair votes for the offset `change - anchor`; the true offset is where the
votes pile up. The peak is then refined on a fine grid, and the script reports its
support, the best rival peak, and the per-anchor residuals, so the alignment can be
audited instead of asserted.

    python align_halves.py --video game.mp4 --cameras Labels-cameras.json \
        --scores scene_scores.txt --out alignment.json
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import re
import statistics
import subprocess

HALF_MIN_SEC = 2400.0  # each half runs at least 40 minutes of clip time


def scene_scores(video: str, cache: str, width: int) -> list[tuple[float, float]]:
    """(pts_time, scene_score) for every frame. Cached, because decoding is slow."""
    if not os.path.exists(cache):
        vf = (f"scale={width}:-2,select='gte(scene,0)',"
              f"metadata=print:key=lavfi.scene_score:file={cache}")
        subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-loglevel", "error",
                        "-i", video, "-an", "-vf", vf, "-f", "null", "-"], check=True)
    out: list[tuple[float, float]] = []
    t = None
    with open(cache, encoding="utf-8") as f:
        for line in f:
            m = re.search(r"pts_time:([0-9.]+)", line)
            if m:
                t = float(m.group(1))
                continue
            m = re.search(r"lavfi\.scene_score=([0-9.]+)", line)
            if m and t is not None:
                out.append((t, float(m.group(1))))
                t = None
    return out


def anchors(cameras_path: str, kinds: set[str]) -> dict[int, list[float]]:
    with open(cameras_path, encoding="utf-8") as f:
        anns = json.load(f)["annotations"]
    by_half: dict[int, list[float]] = {1: [], 2: []}
    for a in anns:
        if a.get("change_type") in kinds:
            half = int(str(a["gameTime"]).split("-")[0].strip())
            by_half[half].append(float(a["position"]) / 1000.0)
    return {h: sorted(v) for h, v in by_half.items()}


def residuals(offset: float, anchor_ts: list[float], cuts: list[float], tol: float) -> list[float]:
    """Signed distance to the nearest detected change, for anchors that have one within tol."""
    res = []
    for a in anchor_ts:
        x = offset + a
        i = bisect.bisect_left(cuts, x)
        near = [cuts[j] - x for j in (i - 1, i) if 0 <= j < len(cuts)]
        if near:
            d = min(near, key=abs)
            if abs(d) <= tol:
                res.append(d)
    return res


def solve_half(anchor_ts: list[float], cuts: list[float], lo: float, hi: float,
               tol: float, bin_sec: float = 0.2) -> dict:
    votes: dict[int, int] = {}
    for a in anchor_ts:
        for c in cuts[bisect.bisect_left(cuts, a + lo):bisect.bisect_right(cuts, a + hi)]:
            b = round((c - a) / bin_sec)
            votes[b] = votes.get(b, 0) + 1
    if not votes:
        return {"offset_sec": None, "anchors": len(anchor_ts), "matched": 0}
    ranked = sorted(votes.items(), key=lambda kv: -kv[1])
    coarse = ranked[0][0] * bin_sec

    best_off, best_n = coarse, -1
    for k in range(-50, 51):  # 0.02 s grid over +-1 s
        off = coarse + k * 0.02
        n = len(residuals(off, anchor_ts, cuts, tol))
        if n > best_n:
            best_off, best_n = off, n
    r = residuals(best_off, anchor_ts, cuts, tol)
    off = best_off + statistics.median(r)  # centre the matched anchors on their changes
    r = residuals(off, anchor_ts, cuts, tol)

    rival = next((b * bin_sec for b, _ in ranked if abs(b * bin_sec - off) > 5.0), None)
    return {
        "offset_sec": round(off, 3),
        "anchors": len(anchor_ts),
        "matched": len(r),
        "median_abs_residual_sec": round(statistics.median(abs(x) for x in r), 3) if r else None,
        "max_abs_residual_sec": round(max(abs(x) for x in r), 3) if r else None,
        "rival_offset_sec": round(rival, 3) if rival is not None else None,
        "rival_matched": len(residuals(rival, anchor_ts, cuts, tol)) if rival is not None else 0,
    }


def diagnostics(frames: list[tuple[float, float]], cameras_path: str,
                offsets: dict[int, float], tol: float) -> dict:
    """The evidence a reviewer needs to believe the offsets, not just the offsets.

    - threshold_sweep: at each scene threshold, how many anchors of each change_type land
      within tol of a detected change, and the median residual in the early, middle and
      late third of each half. A cut in the upload or a drifting clock shows up as a third
      whose matches collapse or whose residual moves.
    - chance_control: the same count with the offset deliberately moved. A real offset is
      a sharp peak; a coincidence is not.
    - abrupt_peak_offsets: where the strongest scene score sits around each annotated hard
      cut, to show whether a miss is an alignment error or an annotation convention.
    """
    with open(cameras_path, encoding="utf-8") as f:
        anns = json.load(f)["annotations"]

    def half(a: dict) -> int:
        return int(str(a["gameTime"]).split("-")[0].strip())

    def nearest(cuts: list[float], x: float):
        i = bisect.bisect_left(cuts, x)
        near = [cuts[j] - x for j in (i - 1, i) if 0 <= j < len(cuts)]
        return min(near, key=abs) if near else None

    out: dict = {"tol_sec": tol, "threshold_sweep": [], "chance_control": []}
    for thr in (0.3, 0.2, 0.12, 0.08):
        cuts = sorted(t for t, s in frames if s > thr)
        row = {"threshold": thr, "detected_changes": len(cuts), "halves": {}}
        for h in (1, 2):
            rows = [(float(a["position"]) / 1000.0, a["change_type"]) for a in anns if half(a) == h]
            rows = [(p, ct, nearest(cuts, offsets[h] + p)) for p, ct in rows]
            by_type: dict = {}
            for p, ct, d in rows:
                k = by_type.setdefault(ct, {"matched": 0, "anchors": 0})
                k["anchors"] += 1
                k["matched"] += int(d is not None and abs(d) <= tol)
            span = max(p for p, _, _ in rows)
            thirds = []
            for k in range(3):
                seg = [d for p, _, d in rows if k * span / 3 <= p <= (k + 1) * span / 3 + 1e-9]
                m = [d for d in seg if d is not None and abs(d) <= tol]
                thirds.append({"matched": len(m), "anchors": len(seg),
                               "median_residual_sec": round(statistics.median(m), 3) if m else None})
            row["halves"][str(h)] = {"by_change_type": by_type, "thirds": thirds}
        out["threshold_sweep"].append(row)

    cuts = sorted(t for t, s in frames if s > 0.2)
    for h in (1, 2):
        items = [float(a["position"]) / 1000.0 for a in anns if half(a) == h]
        shifted = {}
        for shift in (-37.0, -11.3, -2.0, 0.0, 2.0, 11.3, 37.0):
            shifted[f"{shift:+.1f}"] = sum(
                1 for p in items
                if (lambda d: d is not None and abs(d) <= tol)(nearest(cuts, offsets[h] + shift + p)))
        out["chance_control"].append({"half": h, "threshold": 0.2, "anchors": len(items),
                                      "matched_by_offset_shift_sec": shifted})

    times = [t for t, _ in frames]
    scores = [s for _, s in frames]
    peaks = []
    for a in anns:
        if a.get("change_type") != "abrupt":
            continue
        x = offsets[half(a)] + float(a["position"]) / 1000.0
        lo, hi = bisect.bisect_left(times, x - 1.5), bisect.bisect_right(times, x + 1.5)
        if hi > lo:
            j = max(range(lo, hi), key=lambda k: scores[k])
            peaks.append(times[j] - x)
    out["abrupt_peak_offsets"] = {
        "anchors": len(peaks),
        "median_sec": round(statistics.median(peaks), 3) if peaks else None,
        "min_sec": round(min(peaks), 3) if peaks else None,
        "max_sec": round(max(peaks), 3) if peaks else None,
    }
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Align SoccerNet half time to clip time via shot changes.")
    ap.add_argument("--video", required=True)
    ap.add_argument("--cameras", required=True, help="SoccerNet Labels-cameras.json for the match")
    ap.add_argument("--scores", required=True, help="cache file for per-frame scene scores")
    ap.add_argument("--threshold", type=float, default=0.3, help="scene score that counts as a shot change")
    ap.add_argument("--width", type=int, default=320, help="decode width for scene scoring")
    ap.add_argument("--tol", type=float, default=0.3, help="seconds an anchor may sit from a detected change")
    ap.add_argument("--kinds", default="abrupt,logo,smooth", help="SoccerNet change_type values to use")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    frames = scene_scores(args.video, args.scores, args.width)
    duration = frames[-1][0] if frames else 0.0
    cuts = sorted(t for t, s in frames if s > args.threshold)
    anc = anchors(args.cameras, set(args.kinds.split(",")))
    hi = max(0.0, duration - HALF_MIN_SEC)
    result = {
        "video": os.path.basename(args.video),
        "frames": len(frames),
        "last_pts_sec": round(duration, 3),
        "threshold": args.threshold,
        "tol_sec": args.tol,
        "kinds": args.kinds,
        "detected_changes": len(cuts),
        "halves": {str(h): solve_half(anc[h], cuts, 0.0, hi, args.tol) for h in (1, 2)},
    }
    offsets = {h: result["halves"][str(h)]["offset_sec"] for h in (1, 2)}
    result["diagnostics"] = diagnostics(frames, args.cameras, offsets, args.tol)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
