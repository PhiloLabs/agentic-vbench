"""v4 anchor validation — replace 'claude' input with broken and golden,
verify the judge returns 0.0 and 1.0 respectively.

This is the load-bearing test for the v4 design: the universal formula
should make the broken passthrough score 0 by construction and the golden
score 1 by construction.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _framework as fw  # noqa: E402

# Patch get_task_paths to swap p.claude with broken or golden for sanity check.
import judge_audio  # noqa: E402
import judge_video  # noqa: E402


# swap tasks have timeline-offset shots: corrupted_start != original_start for
# at least one swap entry, so the trivial 'claude=golden' substitution does NOT
# correspond to a perfect submission (it reads golden at the corrupted-timeline
# position, not the original-timeline position the judge expects). Skip those
# from the strict golden-anchor check; broken-anchor still validates.
_SWAP_FAMILY_TASKS = {"exp-swap-car-task01", "exp-swap-product-task01"}

_ORIG_GET_PATHS = fw.get_task_paths
_ORIG_WRITE = fw.write_v4_result
_ORIG_TSV = fw.append_tsv

# Suppress writes during validation runs.
fw.write_v4_result = lambda *a, **k: None
fw.append_tsv = lambda *a, **k: None
judge_audio.write_v4_result = fw.write_v4_result
judge_audio.append_tsv = fw.append_tsv
judge_video.write_v4_result = fw.write_v4_result
judge_video.append_tsv = fw.append_tsv


def _patched_paths(task_id, claude_src):
    p = _ORIG_GET_PATHS(task_id)
    if claude_src == "broken":
        p.claude = p.broken
    elif claude_src == "golden":
        p.claude = p.golden
    return p


def _validate(task_id, judge_fn):
    results = {}
    for src in ("broken", "golden"):
        patched = lambda tid, s=src: _patched_paths(tid, s)
        # Repoint each module's binding (judges did `from _framework import get_task_paths`,
        # so they have a local name that needs setting).
        fw.get_task_paths = patched
        judge_audio.get_task_paths = patched
        judge_video.get_task_paths = patched
        try:
            r = judge_fn(task_id)
            results[src] = r["score"]
        except Exception as e:
            import traceback
            traceback.print_exc()
            results[src] = f"ERROR: {e}"
    fw.get_task_paths = _ORIG_GET_PATHS
    judge_audio.get_task_paths = _ORIG_GET_PATHS
    judge_video.get_task_paths = _ORIG_GET_PATHS
    return results


JUDGE_MAP = {
    **{tid: judge_audio.judge_dns_denoise if tid == "exp-dns-denoise-task01" else
       judge_audio.judge_voicebank_denoise if tid == "exp-voicebank-denoise-task01" else
       judge_audio.judge_dereverb if tid == "exp-dereverb-task01" else
       judge_audio.judge_declip if tid == "exp-declip-task01" else
       judge_audio.judge_codec_restore for tid in (
           "exp-dns-denoise-task01", "exp-voicebank-denoise-task01",
           "exp-dereverb-task01", "exp-declip-task01", "exp-codec-restore-task01")},
    **{tid: judge_video.JUDGES[tid] for tid in judge_video.JUDGES},
}


def main(argv):
    tasks = argv[1:] or list(JUDGE_MAP.keys())
    print(f"v4 anchor validation: {len(tasks)} task(s)\n")
    print(f"{'task':45s} {'broken→':>9s}  {'golden→':>9s}  notes")
    failures = []
    for tid in tasks:
        if tid not in JUDGE_MAP:
            print(f"  [skip] unknown task: {tid}")
            continue
        try:
            r = _validate(tid, JUDGE_MAP[tid])
            b = r["broken"]
            g = r["golden"]
            b_ok = isinstance(b, float) and abs(b) < 0.05
            g_ok = isinstance(g, float) and g > 0.95
            mark_b = "✓" if b_ok else "✗"
            mark_g = "✓" if g_ok else "✗"
            note = ""
            if tid in _SWAP_FAMILY_TASKS and not g_ok:
                note = "  (swap timeline-offset; golden substitution is approximate)"
                g_ok = isinstance(g, float) and g > 0.85
                mark_g = "≈" if g_ok else "✗"
            b_str = f"{b:>8.3f}" if isinstance(b, float) else f"{str(b):>8s}"
            g_str = f"{g:>8.3f}" if isinstance(g, float) else f"{str(g):>8s}"
            print(f"  {tid:45s} {b_str}{mark_b}  {g_str}{mark_g}{note}")
            if not (b_ok and g_ok):
                failures.append((tid, b, g))
        except Exception as e:
            print(f"  {tid:45s} ERROR  {e}")
            failures.append((tid, None, None))

    print()
    if failures:
        print(f"FAILED: {len(failures)} tasks did not satisfy broken≤0.05 / golden≥0.95")
        for tid, b, g in failures:
            print(f"  - {tid}  broken={b}  golden={g}")
        return 1
    print(f"PASSED: all {len(tasks)} tasks satisfy broken≤0.05 + golden≥0.95")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
