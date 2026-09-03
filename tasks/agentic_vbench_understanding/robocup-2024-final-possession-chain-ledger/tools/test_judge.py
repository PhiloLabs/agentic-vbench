#!/usr/bin/env python3
"""Regression tests for the deterministic task scorer."""

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
        details_json = root / "verifier-details.json"
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
                "--details-json",
                str(details_json),
            ],
            check=True,
        )
        result = json.loads(reward_json.read_text(encoding="utf-8"))
        result["details"] = json.loads(details_json.read_text(encoding="utf-8"))
        assert float(reward_txt.read_text(encoding="utf-8")) == result["reward"]
        return result


def score(payload: object) -> dict[str, object]:
    return score_bytes(json.dumps(payload).encode())


def main() -> None:
    ground_truth = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    chains = ground_truth["chains"]

    assert score(ground_truth)["reward"] == 1.0
    assert score({"chains": []})["reward"] == 0.0
    assert score_bytes(b"not json")["reward"] == 0.0
    assert score({"chains": "wrong type"})["reward"] == 0.0

    missing_one = score({"chains": chains[:-1]})
    expected_missing = round(2 * (len(chains) - 1) / (2 * len(chains) - 1), 4)
    assert missing_one["reward"] == expected_missing

    duplicated = score({"chains": chains + [chains[0]]})
    expected_duplicate = round(2 * len(chains) / (2 * len(chains) + 1), 4)
    assert duplicated["reward"] == expected_duplicate

    malformed_entry = score({"chains": [*chains, {"half": 1}]})
    assert malformed_entry["details"]["n_schema_valid"] == len(chains)
    assert malformed_entry["reward"] < 1.0

    wrong_terminal = [dict(chain) for chain in chains]
    wrong_terminal[0]["terminal"] = "stoppage"
    terminal_result = score({"chains": wrong_terminal})
    assert terminal_result["details"]["full_chain_matches"] == len(chains) - 1
    assert terminal_result["details"]["partial_chain_matches"] == 1
    assert terminal_result["details"]["credited_matches"] == len(chains) - 0.5

    graded = [dict(chain) for chain in chains]
    graded[0]["kick_count"] += 1
    graded_result = score({"chains": graded})
    assert graded_result["details"]["credited_matches"] == len(chains) - 0.625

    zone_graded = [dict(chain) for chain in chains]
    zone_graded[0]["zone_path"] = ["defensive", "attacking"]
    zone_result = score({"chains": zone_graded})
    assert zone_result["details"]["credited_matches"] == len(chains) - 0.625

    terminal_only = {
        "half": 1,
        "team": "white",
        "kick_count": 99,
        "zone_path": ["attacking", "defensive", "attacking"],
        "terminal": "turnover",
    }
    assert score({"chains": [terminal_only]})["reward"] == 0.0

    wrong_core = dict(chains[0], team="black")
    assert score({"chains": [wrong_core]})["reward"] == 0.0

    boolean_half = dict(chains[0], half=True)
    boolean_result = score({"chains": [boolean_half]})
    assert boolean_result["details"]["n_schema_valid"] == 0
    assert boolean_result["reward"] == 0.0

    out_of_order = [dict(chain) for chain in chains]
    out_of_order[2], out_of_order[3] = out_of_order[3], out_of_order[2]
    assert score({"chains": out_of_order})["reward"] < 1.0

    spam = [
        {
            "half": index % 2 + 1,
            "team": ("white", "black")[(index // 2) % 2],
            "kick_count": 99,
            "zone_path": ["attacking", "defensive", "attacking"],
            "terminal": "goal",
        }
        for index in range(500)
    ]
    assert score({"chains": spam})["reward"] <= 0.01
    print("judge regression tests: PASS")


if __name__ == "__main__":
    main()
