"""v4 aggregator — run every v4 judge, write logs/v4-results.tsv.

Order:
  1. clear/truncate logs/v4-results.tsv (kept atomic)
  2. audio judges (fast: ~10s each)
  3. video judges (slower: ~5–80s each)
  4. passthrough (cut + glitch — no math change vs v3)
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _framework import V4_RESULTS_TSV  # noqa: E402


ALL_TASKS = [
    # audio (5)
    ("exp-dns-denoise-task01", "audio"),
    ("exp-voicebank-denoise-task01", "audio"),
    ("exp-dereverb-task01", "audio"),
    ("exp-declip-task01", "audio"),
    ("exp-codec-restore-task01", "audio"),
    # video (9)
    ("exp-color-shot-visit-korea-task01", "video"),
    ("exp-color-shot-gobelins-task01", "video"),
    ("exp-color-shot-v3-s1-task01", "video"),
    ("exp-deblur-motion-f1-task01", "video"),
    ("exp-deblur-gaussian-mkbhd-task01", "video"),
    ("exp-sr-2x-shot-task01", "video"),
    ("exp-sr-4x-shot-task01", "video"),
    ("exp-swap-car-task01", "video"),
    ("exp-swap-product-task01", "video"),
    # passthrough (7)
    ("exp-glitch-dup-short-task01", "pass"),
    ("exp-glitch-dup-long-task01", "pass"),
    ("exp-content-cut-mkbhd-task01", "pass"),
    ("exp-content-cut-wsj-task01", "pass"),
    ("exp-disfluency-interview-3-task01", "pass"),
    ("exp-disfluency-interview-4-task01", "pass"),
    ("exp-disfluency-pitch-meeting-task01", "pass"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-audio", action="store_true")
    ap.add_argument("--skip-video", action="store_true")
    ap.add_argument("--skip-pass", action="store_true")
    ap.add_argument("--only", nargs="*", help="Only score these task ids")
    args = ap.parse_args()

    if V4_RESULTS_TSV.exists():
        os.remove(V4_RESULTS_TSV)
        print(f"Cleared {V4_RESULTS_TSV}")

    targets = ALL_TASKS
    if args.only:
        targets = [(t, k) for (t, k) in targets if t in set(args.only)]

    audio_ids = [t for (t, k) in targets if k == "audio"]
    video_ids = [t for (t, k) in targets if k == "video"]
    pass_ids = [t for (t, k) in targets if k == "pass"]

    t0 = time.time()
    if audio_ids and not args.skip_audio:
        print(f"\n=== audio ({len(audio_ids)} tasks) ===")
        from judge_audio import main as audio_main
        audio_main(["judge_audio"] + audio_ids)
    if video_ids and not args.skip_video:
        print(f"\n=== video ({len(video_ids)} tasks) ===")
        from judge_video import main as video_main
        video_main(["judge_video"] + video_ids)
    if pass_ids and not args.skip_pass:
        print(f"\n=== passthrough ({len(pass_ids)} tasks) ===")
        from judge_passthrough import main as pass_main
        pass_main(["judge_passthrough"])

    elapsed = time.time() - t0
    print(f"\nTotal elapsed: {elapsed:.1f}s")
    print(f"Results: {V4_RESULTS_TSV}")


if __name__ == "__main__":
    main()
