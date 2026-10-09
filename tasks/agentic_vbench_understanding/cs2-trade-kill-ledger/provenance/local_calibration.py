#!/usr/bin/env python3
"""Local scorer anchors: oracle, empty, random spam, and designed partial baselines.

Runs the real judge on synthetic attempts derived from the GT. Documents the
scorer's shape before any agent calibration; results go in calibration/scores.md.
"""
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
JUDGE = TASK / "steps" / "solve" / "tests" / "judge.py"
GT = json.loads((HERE / "gt_ledger.json").read_text())["ledger"]


def score(payload) -> dict:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "solution.json").write_text(json.dumps(payload))
        subprocess.run([sys.executable, str(JUDGE),
                        "--solution", str(td / "solution.json"),
                        "--reward-json", str(td / "reward.json"),
                        "--reward-txt", str(td / "reward.txt")],
                       check=True, capture_output=True)
        return json.loads((td / "reward.json").read_text())


def main():
    rng = random.Random(52)
    t_max = max(e["t"] for e in GT) + 30
    players = [f"P{i}" for i in range(1, 11)]

    random_spam = [{
        "t": round(rng.uniform(0, t_max), 1),
        "round": rng.randint(1, 23),
        "victim": rng.choice(players),
        "killer": rng.choice(players),
        "was_traded": rng.random() < 0.3,
        "trader": None,
    } for _ in range(len(GT))]
    for e in random_spam:
        if e["was_traded"]:
            e["trader"] = rng.choice(players)

    perfect_kills_no_trades = [
        {**e, "was_traded": False, "trader": None} for e in GT]

    fuzzed_time = [{**e, "t": round(e["t"] + rng.uniform(-4, 4), 2)} for e in GT]

    runs = {
        "oracle": {"ledger": GT},
        "empty": {"ledger": []},
        "random_spam_169": {"ledger": random_spam},
        "perfect_kills_all_untraded": {"ledger": perfect_kills_no_trades},
        "oracle_time_fuzzed_±4s": {"ledger": fuzzed_time},
        # partial-credit curve: an accurate agent that only covers the first X% of
        # the match (reviewers ask for evidence the bar is reachable and smooth)
        "oracle_first_25pct": {"ledger": GT[: len(GT) // 4]},
        "oracle_first_50pct": {"ledger": GT[: len(GT) // 2]},
        "oracle_first_75pct": {"ledger": GT[: 3 * len(GT) // 4]},
    }
    for name, payload in runs.items():
        r = score(payload)
        d = r["details"]
        print(f"{name:30s} reward={r['reward']:<7} "
              f"kill_matches={d['kill_level_matches']:<4} tp={d['true_positives_full_tuple']}")


if __name__ == "__main__":
    main()
