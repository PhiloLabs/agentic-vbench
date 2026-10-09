#!/usr/bin/env python3
"""Regression tests for the deterministic task scorer."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
JUDGE = TASK_DIR / "steps/solve/tests/judge.py"
GROUND_TRUTH = TASK_DIR / "steps/solve/tests/ground_truth.json"


def score_solution(solution: Path, root: Path) -> dict[str, object]:
    reward_json = root / "reward.json"
    reward_txt = root / "reward.txt"
    details_json = root / "verifier-details.json"
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
        timeout=3,
    )
    result = json.loads(reward_json.read_text(encoding="utf-8"))
    result["details"] = json.loads(details_json.read_text(encoding="utf-8"))
    assert float(reward_txt.read_text(encoding="utf-8")) == result["reward"]
    return result


def score_bytes(payload: bytes) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        solution = root / "solution.json"
        solution.write_bytes(payload)
        return score_solution(solution, root)


def score(payload: object) -> dict[str, object]:
    return score_bytes(json.dumps(payload).encode())


def main() -> None:
    ground_truth = json.loads(GROUND_TRUTH.read_text(encoding="utf-8"))
    chains = ground_truth["chains"]

    assert score(ground_truth)["reward"] == 1.0
    assert score({"chains": []})["reward"] == 0.0
    assert score_bytes(b"not json")["reward"] == 0.0
    oversized = b"{" + (b" " * 1_000_000) + b"}"
    oversized_result = score_bytes(oversized)
    assert oversized_result["reward"] == 0.0
    assert oversized_result["details"]["reason"].startswith("unreadable solution.json")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        target = root / "target.json"
        target.write_text(json.dumps({"chains": chains}), encoding="utf-8")
        solution = root / "solution.json"
        solution.symlink_to(target)
        symlink_result = score_solution(solution, root)
        assert symlink_result["reward"] == 0.0
        assert symlink_result["details"]["reason"].startswith("unreadable solution.json")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        solution = root / "solution.json"
        os.mkfifo(solution)
        fifo_result = score_solution(solution, root)
        assert fifo_result["reward"] == 0.0
        assert fifo_result["details"]["reason"].startswith("unreadable solution.json")
    assert score({"chains": "wrong type"})["reward"] == 0.0
    for field, value in (("team", []), ("terminal", {}), ("zone_path", [[]])):
        malformed = dict(chains[0], **{field: value})
        result = score({"chains": [malformed]})
        assert result["reward"] == 0.0
        assert result["details"]["n_schema_valid"] == 0

    assert score({"chains": [dict(chains[0], zone_path=["middle"])]})["reward"] == 0.0
    assert score({"chains": [dict(chains[0], kick_count=2**100)]})["reward"] == 0.0

    # One exact chain of 17: IoU penalizes the missing 16 reference chains.
    one_correct = score({"chains": [chains[0]]})
    assert one_correct["details"]["exact_matches"] == 1
    assert one_correct["details"]["n_predicted"] == 1
    assert one_correct["details"]["precision"] == 1.0
    assert one_correct["details"]["recall"] == round(1 / len(chains), 4)  # 0.0588
    assert one_correct["details"]["exact_iou"] == 0.0588
    assert one_correct["reward"] == 0.0588

    boundary_alternative = dict(chains[2], zone_path=["defensive", "attacking"])
    assert score({"chains": [boundary_alternative]})["details"]["exact_matches"] == 1

    # All terminals wrong: zero exact matches, so IoU collapses to 0.0.
    all_terminal_wrong = [dict(chain) for chain in chains]
    for chain in all_terminal_wrong:
        chain["terminal"] = "goal" if chain["terminal"] != "goal" else "stoppage"
    terminal_wrong_result = score({"chains": all_terminal_wrong})
    assert terminal_wrong_result["details"]["exact_matches"] == 0
    assert terminal_wrong_result["reward"] == 0.0

    missing_one = score({"chains": chains[:-1]})
    expected_missing = round((len(chains) - 1) / len(chains), 4)
    assert missing_one["reward"] == expected_missing

    duplicated = score({"chains": chains + [chains[0]]})
    assert duplicated["details"]["exact_matches"] == len(chains)
    assert duplicated["details"]["n_predicted"] == len(chains) + 1
    expected_duplicate = round(len(chains) / (len(chains) + 1), 4)
    assert duplicated["reward"] == expected_duplicate

    malformed_entry = score({"chains": [*chains, {"half": 1}]})
    assert malformed_entry["details"]["n_schema_valid"] == len(chains)
    assert malformed_entry["details"]["n_predicted"] == len(chains) + 1
    assert malformed_entry["reward"] < 1.0

    wrong_terminal = [dict(chain) for chain in chains]
    wrong_terminal[0]["terminal"] = "stoppage"
    terminal_result = score({"chains": wrong_terminal})
    assert terminal_result["details"]["exact_matches"] == len(chains) - 1
    assert terminal_result["reward"] == round((len(chains) - 1) / (len(chains) + 1), 4)

    wrong_kick = [dict(chain) for chain in chains]
    wrong_kick[0]["kick_count"] += 1
    wrong_kick_result = score({"chains": wrong_kick})
    assert wrong_kick_result["details"]["exact_matches"] == len(chains) - 1
    assert wrong_kick_result["reward"] == round((len(chains) - 1) / (len(chains) + 1), 4)

    wrong_zone = [dict(chain) for chain in chains]
    wrong_zone[0]["zone_path"] = ["defensive", "attacking"]
    wrong_zone_result = score({"chains": wrong_zone})
    assert wrong_zone_result["details"]["exact_matches"] == len(chains) - 1
    assert wrong_zone_result["reward"] == round((len(chains) - 1) / (len(chains) + 1), 4)

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

    wrong_half = dict(chains[0], half=2)
    assert score({"chains": [wrong_half]})["reward"] == 0.0

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
