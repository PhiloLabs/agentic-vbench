#!/usr/bin/env python3
"""Deterministically grade an ordered RoboCup possession-chain ledger."""

from __future__ import annotations

import argparse
import json
import os
import stat
from pathlib import Path


VALID_TEAMS = {"white", "black"}
VALID_ZONES = {"defensive", "middle", "attacking"}
VALID_TERMINALS = {"turnover", "stoppage", "goal"}
MAX_PREDICTIONS = 500
MAX_SOLUTION_BYTES = 1_000_000
MAX_ZONE_PATH_LENGTH = 32
MAX_KICK_COUNT = 64

CanonicalChain = tuple[int, str, int, tuple[str, ...], str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--reward-json", required=True, type=Path)
    parser.add_argument("--reward-txt", required=True, type=Path)
    parser.add_argument("--details-json", type=Path)
    return parser.parse_args()


def canonical(entry: object) -> CanonicalChain | None:
    if not isinstance(entry, dict):
        return None
    half = entry.get("half")
    team = entry.get("team")
    kick_count = entry.get("kick_count")
    zone_path = entry.get("zone_path")
    terminal = entry.get("terminal")
    if not isinstance(half, int) or isinstance(half, bool) or half not in (1, 2):
        return None
    if not isinstance(team, str) or team not in VALID_TEAMS:
        return None
    if (
        isinstance(kick_count, bool)
        or not isinstance(kick_count, int)
        or kick_count < 2
        or kick_count > MAX_KICK_COUNT
    ):
        return None
    if (
        not isinstance(zone_path, list)
        or not zone_path
        or len(zone_path) > MAX_ZONE_PATH_LENGTH
    ):
        return None
    if any(not isinstance(zone, str) or zone not in VALID_ZONES for zone in zone_path):
        return None
    if any(left == right for left, right in zip(zone_path, zone_path[1:])):
        return None
    if not isinstance(terminal, str) or terminal not in VALID_TERMINALS:
        return None
    return half, team, kick_count, tuple(zone_path), terminal


def canonical_expected(entry: object) -> frozenset[CanonicalChain] | None:
    """Return the exact accepted labels for one frozen ground-truth chain."""
    primary = canonical(entry)
    if primary is None or not isinstance(entry, dict):
        return None

    alternatives = entry.get("zone_path_alternatives")
    if alternatives is None:
        return frozenset((primary,))
    if not isinstance(alternatives, list) or not alternatives:
        return None

    accepted = {primary}
    for zone_path in alternatives:
        alternate = dict(entry)
        alternate["zone_path"] = zone_path
        alternate.pop("zone_path_alternatives", None)
        canonical_alternate = canonical(alternate)
        if canonical_alternate is None:
            return None
        accepted.add(canonical_alternate)
    return frozenset(accepted)


def exact_ordered_matches(
    predicted: list[CanonicalChain], expected: list[frozenset[CanonicalChain]]
) -> int:
    """Order-preserving one-to-one count of exact five-field matches.

    A prediction and a ground-truth chain match only when all five canonical
    fields are identical. No partial or graded credit is awarded.
    """
    previous = [0] * (len(expected) + 1)
    for prediction in predicted:
        current = [0]
        for index, ground_truth in enumerate(expected, start=1):
            if prediction in ground_truth:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[-1]))
        previous = current
    return previous[-1]


def exact_iou(matches: int, predicted: int, expected: int) -> tuple[float, float, float]:
    """Return precision, recall, and exact-match Jaccard/IoU.

    Matches are the intersection of submitted and reference chains under the
    order-preserving one-to-one alignment. The union counts every submitted
    entry, including malformed entries and duplicates, so the metric penalizes
    both false positives and missing reference chains.
    """
    precision = matches / predicted if predicted else 0.0
    recall = matches / expected if expected else 0.0
    union = predicted + expected - matches
    score = matches / union if union else 0.0
    return precision, recall, score


def read_solution(path: Path) -> object:
    """Read one bounded regular file without following special filesystem entries."""
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0)
    if not hasattr(os, "O_NOFOLLOW"):
        raise RuntimeError("platform does not support no-follow solution reads")
    descriptor = os.open(path, flags | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("solution.json is not a regular file")
        if info.st_size > MAX_SOLUTION_BYTES:
            raise ValueError(f"solution.json exceeds {MAX_SOLUTION_BYTES} bytes")

        payload = bytearray()
        while len(payload) <= MAX_SOLUTION_BYTES:
            chunk = os.read(
                descriptor, min(65536, MAX_SOLUTION_BYTES + 1 - len(payload))
            )
            if not chunk:
                break
            payload.extend(chunk)
        if len(payload) > MAX_SOLUTION_BYTES:
            raise ValueError(f"solution.json exceeds {MAX_SOLUTION_BYTES} bytes")
        return json.loads(payload.decode("utf-8"))
    finally:
        os.close(descriptor)


def main() -> None:
    args = parse_args()
    ground_truth_path = Path(__file__).with_name("ground_truth.json")
    expected_raw = json.loads(ground_truth_path.read_text(encoding="utf-8"))["chains"]
    expected = [canonical_expected(entry) for entry in expected_raw]
    if any(item is None for item in expected):
        raise RuntimeError("invalid verifier ground truth")

    reason = "ok"
    predictions_raw: list[object] = []
    try:
        solution = read_solution(args.solution)
        if not isinstance(solution, dict):
            raise ValueError("solution root is not an object")
        predictions_raw = solution.get("chains", [])
        if not isinstance(predictions_raw, list):
            raise ValueError("chains is not a list")
        if len(predictions_raw) > MAX_PREDICTIONS:
            raise ValueError(f"chains exceeds {MAX_PREDICTIONS} entries")
    except Exception as exc:  # malformed output deterministically scores zero
        reason = f"unreadable solution.json: {exc}"
        predictions_raw = []

    predictions = [item for entry in predictions_raw if (item := canonical(entry)) is not None]
    exact_matches = exact_ordered_matches(predictions, expected)
    precision, recall, reward = exact_iou(
        exact_matches, len(predictions_raw), len(expected)
    )

    details = {
        "reason": reason,
        "n_ground_truth": len(expected),
        "n_predicted": len(predictions_raw),
        "n_schema_valid": len(predictions),
        "exact_matches": exact_matches,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "exact_iou": round(reward, 4),
        "matching": "exact five-field order-preserving one-to-one; no partial credit",
        "ground_truth_zone_alternatives": sum(
            len(labels) > 1 for labels in expected
        ),
    }
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(
        json.dumps(
            {
                "reward": round(reward, 4),
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "exact_iou": round(reward, 4),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    args.reward_txt.write_text(f"{round(reward, 4)}\n", encoding="utf-8")
    details_path = args.details_json or args.reward_json.with_name("verifier-details.json")
    details_path.write_text(json.dumps(details, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
