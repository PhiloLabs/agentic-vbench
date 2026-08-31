#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parent.parent
JUDGE = TASK_DIR / "steps/solve/tests/judge.py"
GROUND_TRUTH = json.loads(
    (TASK_DIR / "steps/solve/tests/ground_truth.json").read_text()
)


def _grade(payload: dict) -> dict:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        solution = root / "solution.json"
        reward_json = root / "reward.json"
        reward_txt = root / "reward.txt"
        details_json = root / "details.json"
        solution.write_text(json.dumps(payload))
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
                "--details-json",
                str(details_json),
            ],
            check=True,
        )
        result = json.loads(reward_json.read_text())
        assert set(result) == {"reward"}
        result["details"] = json.loads(details_json.read_text())
        assert float(reward_txt.read_text()) == result["reward"]
        return result


def main() -> None:
    oracle = _grade(GROUND_TRUTH)
    assert oracle["reward"] == 1.0
    assert oracle["details"]["true_positives"] == 47

    empty = _grade({"checkpoints": []})
    assert empty["reward"] == 0.0

    checkpoint = deepcopy(GROUND_TRUTH["checkpoints"][0])
    checkpoint["time_s"] += 2.0
    boundary = _grade({"checkpoints": [checkpoint]})
    assert boundary["details"]["true_positives"] == 1

    checkpoint["time_s"] += 0.0001
    outside = _grade({"checkpoints": [checkpoint]})
    assert outside["details"]["true_positives"] == 0

    malformed_checkpoint = deepcopy(GROUND_TRUTH["checkpoints"][0])
    malformed_checkpoint["state_after"][0] = 2
    malformed = _grade({"checkpoints": [malformed_checkpoint]})
    assert malformed["reward"] == 0.0
    assert malformed["details"]["reason"] == "ignored 1 malformed checkpoint(s)"

    duplicate_checkpoint = deepcopy(GROUND_TRUTH["checkpoints"][0])
    duplicates = _grade({"checkpoints": [duplicate_checkpoint, duplicate_checkpoint]})
    assert duplicates["details"]["true_positives"] == 1
    assert duplicates["details"]["n_predicted"] == 2

    normalized_checkpoint = deepcopy(GROUND_TRUTH["checkpoints"][0])
    normalized_checkpoint["video"] = normalized_checkpoint["video"].lower()
    normalized_checkpoint["changes"].reverse()
    normalized = _grade({"checkpoints": [normalized_checkpoint]})
    assert normalized["details"]["true_positives"] == 1

    print("judge regression tests passed")


if __name__ == "__main__":
    main()
