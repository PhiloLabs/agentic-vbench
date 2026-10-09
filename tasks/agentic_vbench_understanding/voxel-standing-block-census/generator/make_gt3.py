#!/usr/bin/env python3
"""Build the v3 ground truth: every block the rig dug out that it had placed
earlier, with both timestamps moved onto the video clock.

The mod's clock starts when the capture script drops GO, a few seconds after
ffmpeg begins recording, and the rig flashes the whole screen white at
t=1.0, 2.0 and 4.0. Those gaps (1 s then 2 s) are asymmetric, so the pattern
can only be aligned one way. The offset found here is added to every event.
"""
import json, os, subprocess, sys, numpy as np

FF = os.environ.get("FFMPEG", "ffmpeg")
FP = os.environ.get("FFPROBE", "ffprobe")


def label(node):
    return node.split(":", 1)[1] if ":" in node else node


def read_log(path):
    rows = []
    for line in open(path):
        p = line.rstrip("\n").split("\t")
        if len(p) < 4:
            continue
        extra = p[4] if len(p) > 4 else "-"
        rows.append((float(p[0]), p[1], p[2], p[3], extra))
    return rows


def duration(video):
    out = subprocess.run([FP, "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", video], capture_output=True, text=True)
    return float(out.stdout.strip())


def find_flashes(video, fps=30, window=180):
    """Decode to 64x36 gray and return the start time of every run of bright frames.

    The threshold is relative, not the fixed 200 an earlier version used. The
    flash is a full-screen white overlay but the frame mean it produces depends
    on how it composites and on the capture rate: one 30-minute take peaked at
    167 and the fixed threshold found nothing at all. What actually identifies
    the flashes is the asymmetric 1 s then 2 s spacing, which solve_offset
    checks, so detection can afford to be generous.
    """
    w, h = 64, 36
    cmd = [FF, "-v", "error", "-i", video, "-t", str(window), "-vf",
           f"fps={fps},scale={w}:{h}", "-pix_fmt", "gray", "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    n = len(raw) // (w * h)
    a = np.frombuffer(raw[:n * w * h], dtype=np.uint8).reshape(n, h * w)
    m = a.mean(axis=1)
    med = float(np.median(m))
    thr = max(med + 25.0, med + 0.55 * (float(m.max()) - med))
    bright = m > thr
    runs, i = [], 0
    while i < n:
        if bright[i]:
            j = i
            while j < n and bright[j]:
                j += 1
            if j - i >= 2:
                runs.append(i / fps)
            i = j
        else:
            i += 1
    return runs, m


def solve_offset(runs, want):
    """want = the logged flash times. Return the offset that maps log -> video."""
    if len(runs) < len(want):
        return None, 9e9
    best, berr = None, 9e9
    gaps_w = np.diff(want)
    for i in range(len(runs) - len(want) + 1):
        cand = np.array(runs[i:i + len(want)])
        err = float(np.abs(np.diff(cand) - gaps_w).max())
        if err < berr:
            berr = err
            best = float(np.median(cand - np.array(want)))
    return best, berr


def main(log, video, out):
    rows = read_log(log)
    flashes = [r[0] for r in rows if r[1] == "sync"]
    if len(flashes) < 3:
        sys.exit("only %d flashes logged" % len(flashes))
    runs, _ = find_flashes(video)
    off, err = solve_offset(runs, flashes)
    if off is None or err > 0.35:
        sys.exit("flash pattern not found in the video (best spacing error %.2fs)" % err)
    dur = duration(video)
    print("flashes logged %s" % [round(f, 2) for f in flashes])
    print("flashes found  %s" % [round(f, 2) for f in runs[:8]])
    print("offset %+.3f s  spacing error %.3f s  duration %.1f s" % (off, err, dur))

    ev, drop = [], 0
    for t, act, name, pos, extra in rows:
        if act != "redig":
            continue
        td = t + off
        tp = float(extra) + off
        if td < 0 or td > dur or tp < 0 or tp > dur or tp >= td:
            drop += 1
            continue
        ev.append({"t_dig": round(td, 2), "t_place": round(tp, 2),
                   "target": label(name), "pos": pos})
    ev.sort(key=lambda e: e["t_dig"])
    gaps = np.diff([e["t_dig"] for e in ev]) if len(ev) > 1 else np.array([0.0])
    ages = np.array([e["t_dig"] - e["t_place"] for e in ev]) if ev else np.array([0.0])
    print("redig events %d  (dropped %d)" % (len(ev), drop))
    print("dig-to-dig gap   median %.2f s   min %.2f s   p10 %.2f s"
          % (np.median(gaps), gaps.min(), np.percentile(gaps, 10)))
    print("place-to-dig age median %.1f s   min %.1f s   max %.1f s"
          % (np.median(ages), ages.min(), ages.max()))
    from collections import Counter
    c = Counter(e["target"] for e in ev)
    print("classes %d  top %s" % (len(c), c.most_common(6)))
    json.dump(ev, open(out, "w"), indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
