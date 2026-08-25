#!/usr/bin/env python3
"""Regression test for judge.py — a partial answer must not score as if complete.

Guards the coverage bug: an answer that correctly reconstructs only k of the n races used to score
1.0 because omitted GT races were dropped from the tau and accuracy denominators. The judge now
scales the reward by coverage = matched_races / total_races, so:
  * the full oracle (all races) still scores 1.0,
  * a correct 2-of-12 subset scores ~2/12 (NOT 1.0),
  * an empty answer scores 0.

Run: `python3 test_coverage.py` (exit 0 = pass). Pure stdlib; runs judge.py as the harness does.
"""
import json, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
JUDGE = HERE / "judge.py"
GT = json.loads((HERE / "ground_truth.json").read_text())["races"]


def score(sol):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "sol.json").write_text(json.dumps(sol))
        subprocess.run([sys.executable, str(JUDGE), "--solution", str(d / "sol.json"),
                        "--reward-json", str(d / "r.json"), "--reward-txt", str(d / "r.txt")],
                       check=True, capture_output=True)
        return json.loads((d / "r.json").read_text())


def oracle_races(n=None):
    rows = GT if n is None else GT[:n]
    return {"races": [{"track": r["track"], "t": round((r["t_start"] + r["t_end"]) / 2, 1),
                       "items_collected": r["items_collected"], "skid_time": r["skid_time"]} for r in rows]}


def main():
    n = len(GT)
    full = score(oracle_races())["reward"]
    part = score(oracle_races(2))
    empty = score({"races": []})["reward"]

    checks = [
        ("full oracle == 1.0", abs(full - 1.0) < 1e-6, f"reward={full}"),
        ("2-of-%d subset < 1.0 (coverage penalty)" % n, part["reward"] < 0.5, f"reward={part['reward']}"),
        ("2-of-%d subset ~= 2/%d" % (n, n), abs(part["reward"] - 2.0 / n) < 0.02,
         f"reward={part['reward']} vs {2.0/n:.4f}"),
        ("2-of-%d coverage == 2/%d" % (n, n), abs(part["details"]["coverage"] - 2.0 / n) < 1e-3,
         f"coverage={part['details']['coverage']} (det is rounded to 4dp)"),
        ("empty == 0.0", empty == 0.0, f"reward={empty}"),
    ]
    ok = True
    for name, passed, detail in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}  ({detail})")
        ok = ok and passed
    if not ok:
        sys.exit("REGRESSION FAILED")
    print("all coverage regression checks passed")


if __name__ == "__main__":
    main()
