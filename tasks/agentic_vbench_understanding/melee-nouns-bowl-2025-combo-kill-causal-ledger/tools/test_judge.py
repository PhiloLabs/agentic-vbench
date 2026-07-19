#!/usr/bin/env python3
"""Regression tests for the deterministic Melee ledger scorer."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
JUDGE = TASK_DIR / "steps/solve/tests/judge.py"
GROUND_TRUTH = TASK_DIR / "steps/solve/tests/ground_truth.json"


def score_bytes(payload: bytes) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        solution = root / "solution.json"
        reward_json = root / "reward.json"
        reward_txt = root / "reward.txt"
        solution.write_bytes(payload)
        subprocess.run(
            [
                "python3",
                str(JUDGE),
                "--solution",
                str(solution),
                "--reward-json",
                str(reward_json),
                "--reward-txt",
                str(reward_txt),
            ],
            check=True,
        )
        result = json.loads(reward_json.read_text(encoding="utf-8"))
        assert float(reward_txt.read_text(encoding="utf-8")) == result["reward"]
        return result


def score(payload: object) -> dict[str, object]:
    return score_bytes(json.dumps(payload).encode())


def main() -> None:
    ground_truth = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    events = ground_truth["events"]

    assert score(ground_truth)["reward"] == 1.0
    assert score({"events": []})["reward"] == 0.0
    assert score_bytes(b"not json")["reward"] == 0.0
    assert score({"events": "wrong type"})["reward"] == 0.0

    missing_one = score({"events": events[:-1]})
    expected_missing = round(2 * (len(events) - 1) / (2 * len(events) - 1), 4)
    assert missing_one["reward"] == expected_missing

    duplicated = score({"events": events + [events[0]]})
    expected_duplicate = round(2 * len(events) / (2 * len(events) + 1), 4)
    assert duplicated["reward"] == expected_duplicate

    malformed_entry = score({"events": [*events, {"game": 1}]})
    assert malformed_entry["details"]["n_schema_valid"] == len(events)
    assert malformed_entry["reward"] < 1.0

    reversed_events = score({"events": list(reversed(events))})
    assert reversed_events["reward"] < 0.1
    print("judge regression tests: PASS")


if __name__ == "__main__":
    main()
