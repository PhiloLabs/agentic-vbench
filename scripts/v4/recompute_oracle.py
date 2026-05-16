"""Score every oracle (smoke-*) artifact under v4.

Same judges as `recompute_all.py`, but the artifact-finder is redirected at
`jobs/smoke-<task>-*` directories so we score the oracle's solve.sh output
instead of claude's. Writes to `logs/v4-oracle-results.tsv`.

This surfaces the seven tasks whose oracle is a `cp broken → output`
passthrough — they will score 0 under v4 by construction (broken anchor).
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _framework as fw  # noqa: E402
from _framework import JOBS_DIR, LOGS_DIR  # noqa: E402

import judge_audio  # noqa: E402
import judge_video  # noqa: E402


V4_ORACLE_TSV = LOGS_DIR / "v4-oracle-results.tsv"
V4_ORACLE_PER_TASK = LOGS_DIR / "v4-oracle-per-task"
V4_ORACLE_PER_TASK.mkdir(parents=True, exist_ok=True)


def _find_oracle_artifact(task_id: str, family: str) -> Path | None:
    """Latest smoke job's output artifact for this task."""
    art_name = "enhanced.wav" if family == "audio_inj" else "output.mp4"
    pattern = re.compile(rf"^smoke-{re.escape(task_id)}-")
    candidates = []
    for d in JOBS_DIR.iterdir():
        if not pattern.match(d.name):
            continue
        for art in d.glob(f"*/steps/solve/artifacts/{art_name}"):
            candidates.append((art.stat().st_mtime, art))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


# Monkey-patch the framework's artifact finder so all v4 judges resolve their
# 'claude' path against jobs/smoke-* instead of jobs/cc-*.
_ORIG_GET_PATHS = fw.get_task_paths
_ORIG_WRITE = fw.write_v4_result
_ORIG_TSV = fw.append_tsv

# Redirect writes to the oracle-specific destinations.
def _oracle_write(task_id, family, metric, m_b, m_g, m_c, score_raw, score_cal, details):
    payload = {
        "task_id": task_id, "family": family, "metric_used": metric,
        "m_broken": m_b, "m_golden": m_g, "m_claude": m_c,  # 'm_claude' here = oracle, kept name-stable for downstream loaders
        "v4_raw_reward": score_raw, "v4_calibrated_reward": score_cal,
        "details": details,
    }
    out = V4_ORACLE_PER_TASK / f"{task_id}.json"
    out.write_text(json.dumps(payload, indent=2))


def _oracle_append(task_id, family, metric, m_b, m_g, m_c, score_raw, score_cal):
    new = not V4_ORACLE_TSV.exists()
    with V4_ORACLE_TSV.open("a") as f:
        w = csv.writer(f, delimiter="\t")
        if new:
            w.writerow(["task", "family", "metric", "m_broken", "m_golden",
                        "m_oracle", "v4_raw", "v4_calibrated"])
        w.writerow([task_id, family, metric,
                    f"{m_b:.6g}", f"{m_g:.6g}", f"{m_c:.6g}",
                    f"{score_raw:.6f}", f"{score_cal:.6f}"])


def _oracle_get_paths(task_id: str):
    p = _ORIG_GET_PATHS(task_id)
    art = _find_oracle_artifact(task_id, p.family)
    if art:
        p.claude = art
    else:
        p.claude = None
    return p


def main(argv: list[str]) -> int:
    # Install patches
    fw.get_task_paths = _oracle_get_paths
    fw.write_v4_result = _oracle_write
    fw.append_tsv = _oracle_append
    judge_audio.get_task_paths = fw.get_task_paths
    judge_audio.write_v4_result = fw.write_v4_result
    judge_audio.append_tsv = fw.append_tsv
    judge_video.get_task_paths = fw.get_task_paths
    judge_video.write_v4_result = fw.write_v4_result
    judge_video.append_tsv = fw.append_tsv

    if V4_ORACLE_TSV.exists():
        os.remove(V4_ORACLE_TSV)
        print(f"Cleared {V4_ORACLE_TSV}")

    from judge_audio import JUDGES as AUDIO_JUDGES
    from judge_video import JUDGES as VIDEO_JUDGES
    all_judges = {**AUDIO_JUDGES, **VIDEO_JUDGES}

    tasks = argv[1:] or list(all_judges.keys())
    print(f"v4 ORACLE scoring: {len(tasks)} task(s)")
    for tid in tasks:
        if tid not in all_judges:
            continue
        try:
            p = fw.get_task_paths(tid)
            if p.claude is None:
                print(f"  {tid:42s} no smoke artifact found, skipped")
                continue
            r = all_judges[tid](tid)
            d = r["details"]
            mp = d["metric_primary"]
            ms = d.get(mp, {})
            broken_val = ms.get("broken", "?")
            golden_val = ms.get("golden", "?")
            oracle_val = ms.get("claude", "?")  # naming inherited; this is oracle's metric value
            bv = f"{broken_val:.3g}" if isinstance(broken_val, (int, float)) else str(broken_val)
            gv = f"{golden_val:.3g}" if isinstance(golden_val, (int, float)) else str(golden_val)
            ov = f"{oracle_val:.3g}" if isinstance(oracle_val, (int, float)) else str(oracle_val)
            print(f"  {tid:42s} score={r['score']:.3f}  metric={mp}  m_b={bv}  m_g={gv}  m_oracle={ov}")
        except Exception as e:
            import traceback
            print(f"  {tid:42s} ERROR {e}")
            traceback.print_exc()

    print(f"\nResults: {V4_ORACLE_TSV}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
