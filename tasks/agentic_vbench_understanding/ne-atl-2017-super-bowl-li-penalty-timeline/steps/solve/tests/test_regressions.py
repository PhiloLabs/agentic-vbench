#!/usr/bin/env python3
"""Regression checks for judge.py's F-beta scorer. Run manually before submitting:

    python3 steps/solve/tests/test_regressions.py

Checks the four cases from the issue #60 review: an empty submission, one exact row,
two exact rows, and the full oracle set all land at the specified F2 values.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
JUDGE = HERE / "judge.py"

sys.path.insert(0, str(HERE))
from judge import GROUND_TRUTH  # noqa: E402

CASES = [
    ("null", [], 0.0),
    ("one_hit", [dict(GROUND_TRUTH[0])], 0.0943),
    ("two_hit", [dict(GROUND_TRUTH[0]), dict(GROUND_TRUTH[1])], 0.1852),
    ("oracle", [dict(g) for g in GROUND_TRUTH], 1.0),
]


def run(preds: list) -> float:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        sol = td / "solution.json"
        sol.write_text(json.dumps({"penalties": preds}))
        reward_json = td / "reward.json"
        subprocess.run(
            [sys.executable, str(JUDGE),
             "--solution", str(sol),
             "--reward-json", str(reward_json),
             "--reward-txt", str(td / "reward.txt")],
            check=True,
        )
        return json.loads(reward_json.read_text())["reward"]


def main() -> int:
    failed = False
    for name, preds, expected in CASES:
        got = run(preds)
        ok = abs(got - expected) < 1e-3
        print(f"{'OK  ' if ok else 'FAIL'} {name}: got {got}, expected {expected}")
        failed = failed or not ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
