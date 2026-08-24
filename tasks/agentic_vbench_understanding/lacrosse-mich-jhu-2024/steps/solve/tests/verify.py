#!/usr/bin/env python3
"""Convenience CLI over the grader in judge.py (single source of truth).

The harness calls `judge.py` via `test.sh`. This shim exists only so the
calibration run-pack can grade a solution file positionally:

    python3 verify.py <solution.json> [answer_key.json]

It imports judge.score(), so the scoring logic is defined exactly once.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from judge import score  # noqa: E402


def main() -> None:
    pred_path = Path(sys.argv[1])
    gt_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parent / "answer_key.json"
    try:
        pred = json.loads(pred_path.read_text())
    except Exception:
        print(json.dumps({"reward": 0.0, "details": {"error": "unparseable prediction"}}))
        return
    print(json.dumps(score(pred, json.loads(gt_path.read_text()))))


if __name__ == "__main__":
    main()
