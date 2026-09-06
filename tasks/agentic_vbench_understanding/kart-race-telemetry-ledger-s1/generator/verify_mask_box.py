#!/usr/bin/env python3
"""Measure the HUD mask rectangle in a rendered video and compare it to the required one.

hud_mask.py derives, from SuperTuxKart's own drawing code, the rectangle that has to be blacked
out. This checks the other half: that the rectangle actually present in the file matches it. The
box is found by looking for columns carrying a tall run of near-black pixels, which is reliable
(unlike trying to spot the sprites themselves: an alpha-blended sprite sliver is not separable
from ordinary scenery -- see NOTES.md).

Exit status is 0 when the measured box matches the required one within tolerance, 1 otherwise, so
it can gate a suite build. Run with --expect-absent to assert a video is NOT masked, which is how
the check itself is shown to fire.
"""
import argparse
import statistics
import sys

from video_frames import burst, duration
from hud_mask import mask_box


def measure(frame, blackness, min_height):
    """Return (left, right, top, bottom) of the tallest all-black column block, or None."""
    black = frame <= blackness
    h, w = black.shape
    best_run, cols = None, []
    tops, bots = [], []
    for c in range(w):
        col = black[:, c]
        run_start, run_len, best_start, best_len = None, 0, None, 0
        for r in range(h + 1):
            v = col[r] if r < h else False
            if v and run_start is None:
                run_start, run_len = r, 1
            elif v:
                run_len += 1
            elif run_start is not None:
                if run_len > best_len:
                    best_len, best_start = run_len, run_start
                run_start, run_len = None, 0
        if best_len >= min_height:
            cols.append(c)
            tops.append(best_start)
            bots.append(best_start + best_len)
    if not cols:
        return None
    # longest contiguous stretch of qualifying columns
    runs, start = [], cols[0]
    for a, b in zip(cols, cols[1:] + [None]):
        if b is None or b != a + 1:
            runs.append((start, a + 1))
            start = b
    best_run = max(runs, key=lambda r: r[1] - r[0])
    return best_run[0], best_run[1], int(statistics.median(tops)), int(statistics.median(bots))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--blackness", type=int, default=10,
                    help="a masked pixel is <= this after lossy re-encoding")
    ap.add_argument("--tol", type=int, default=3, help="allowed edge error in px")
    ap.add_argument("--agree", type=float, default=0.80,
                    help="fraction of sampled frames that must show the box")
    ap.add_argument("--expect-absent", action="store_true",
                    help="assert the video is NOT masked (used to prove this check can fire)")
    a = ap.parse_args()

    want = mask_box(a.width, a.height)                 # x, y, w, h
    wx0, wy0, ww, wh = want
    wx1, wy1 = wx0 + ww, wy0 + wh
    band_x, band_w = max(0, wx0 - 60), min(a.width, wx1 + 60) - max(0, wx0 - 60)
    band_y, band_h = 0, min(a.height, wy1 + 60)
    min_height = int(wh * 0.7)

    dur = duration(a.video)
    times = [10.0 + i * (dur - 20.0) / max(1, a.samples - 1) for i in range(a.samples)]

    print("== %s" % a.video)
    print("   required box x=[%d,%d) y=[%d,%d) from hud_mask.py" % (wx0, wx1, wy0, wy1))
    hits, seen = [], 0
    for t in times:
        arr = burst(a.video, t, band_x, band_y, band_w, band_h, 1)
        if arr is None:
            continue
        seen += 1
        m = measure(arr[0], a.blackness, min_height)
        if m is None:
            continue
        l, r, tp, bt = m
        hits.append((band_x + l, band_x + r, band_y + tp, band_y + bt))
    # A handful of frames are black all over (the transitions between races), and a black frame
    # trivially contains a black rectangle. So a mask counts as PRESENT only when the box shows up
    # in nearly every sampled frame, not merely in some.
    present = len(hits) >= a.agree * seen
    if hits:
        med = [int(statistics.median(v)) for v in zip(*hits)]
        print("   measured box x=[%d,%d) y=[%d,%d) in %d/%d frames"
              % (med[0], med[1], med[2], med[3], len(hits), seen))
    else:
        print("   measured: no black box found in %d frames" % seen)
    if a.expect_absent:
        if present:
            print("   FAIL: expected an unmasked video but found a mask box in %d/%d frames"
                  % (len(hits), seen))
            return 1
        print("   OK: no persistent mask box, as expected for unmasked media")
        return 0
    if not present:
        print("   FAIL: box found in only %d of %d frames; the shipped media is not masked"
              % (len(hits), seen))
        return 1
    errs = [abs(med[0] - wx0), abs(med[1] - wx1), abs(med[2] - wy0), abs(med[3] - wy1)]
    if max(errs) > a.tol:
        print("   FAIL: edges off by %s px (tolerance %d); the shipped mask is not the required one"
              % (errs, a.tol))
        return 1
    print("   OK: shipped mask matches the required box within %d px (max error %d)"
          % (a.tol, max(errs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
