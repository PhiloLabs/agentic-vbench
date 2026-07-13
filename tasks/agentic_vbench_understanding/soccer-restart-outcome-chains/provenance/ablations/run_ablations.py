#!/usr/bin/env python3
"""Shortcut ablations for soccer-restart-outcome-chains, scored on the OFFICIAL metric.

    no_media / prior     [deterministic] : most-common tuple at guessed times
    random               [deterministic] : random tuples
    single_frame         [needs a VLM]   : answer from one frame
    frame_dump_no_tools  [needs a VLM]   : uniform frames, no tools, one-shot
    possession_tracker   [needs a run]   : correct t+outcome, guessed restart_type

Usage:
    python run_ablations.py --gt ../data/gt/<match>.json
    python run_ablations.py --gt ../data/gt/<match>.json \
        --frame-dump-answer fd.json --single-frame-answer sf.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import verifier  # noqa: E402
import oracle  # noqa: E402

THRESH = 0.10


def _score(ans, gt, tau):
    return verifier.score(ans, gt, tau=tau)["official_score"]


def run(gt_path: str, frame_dump_answer=None, single_frame_answer=None, metadata_answer=None) -> dict:
    gt = oracle.load_gt(gt_path)
    tau = gt.get("tau_sec", verifier.DEFAULT_TAU_SEC)
    checks = oracle.self_check(gt, tau)
    results = {
        "no_media": checks["no_media_prior"],
        "random_mean": checks["random_mean"],
        "random_max": checks["random_max"],
        "oracle": checks["oracle"],
    }
    for name, path in (("frame_dump_no_tools", frame_dump_answer),
                       ("single_frame", single_frame_answer),
                       ("metadata_only", metadata_answer)):
        if path:
            with open(path, "r", encoding="utf-8") as f:
                results[name] = _score(json.load(f), gt, tau)

    deterministic = {"no_media": results["no_media"], "random_mean": results["random_mean"]}
    optional = {k: results[k] for k in ("frame_dump_no_tools", "single_frame", "metadata_only") if k in results}
    results["PASS_deterministic"] = all(v < THRESH for v in deterministic.values())
    results["PASS_optional"] = all(v < THRESH for v in optional.values()) if optional else None
    results["oracle_ok"] = results["oracle"] == 1.0
    results["threshold"] = THRESH
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", required=True)
    ap.add_argument("--frame-dump-answer", default=None)
    ap.add_argument("--single-frame-answer", default=None)
    ap.add_argument("--metadata-answer", default=None)
    args = ap.parse_args(argv)
    res = run(args.gt, args.frame_dump_answer, args.single_frame_answer, args.metadata_answer)
    json.dump(res, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if (res["oracle_ok"] and res["PASS_deterministic"] and res["PASS_optional"] in (True, None)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
