#!/usr/bin/env python3
"""Deterministic scorer for OTB chess move and capture reconstruction."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


GROUND_TRUTH_PATH = Path(__file__).with_name("ground_truth.json")
TIME_TOLERANCE_S = 6.0


def normalize_san(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip().replace("0", "O")
    text = re.sub(r"[!?+#]+", "", text)
    return text


def normalize_uci(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^a-h1-8qrbn]", "", value.lower())


def normalize_token(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^a-z0-9_]", "", value.lower())


def parse_time(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    parts = value.strip().split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        if len(parts) == 1:
            return float(parts[0])
    except ValueError:
        return None
    return None


def load_solution(path: Path) -> tuple[dict[str, Any], str]:
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            raise ValueError("top-level JSON must be an object")
        return data, "ok"
    except Exception as exc:  # noqa: BLE001 - malformed output scores zero
        return {}, f"unreadable solution.json: {exc}"


def identity_ok(pred: dict[str, Any], truth: dict[str, Any]) -> bool:
    side_ok = normalize_token(pred.get("side")) == normalize_token(truth.get("side"))
    ply_ok = pred.get("ply") == truth.get("ply")
    uci_ok = normalize_uci(pred.get("uci")) == normalize_uci(truth.get("uci"))
    san_ok = normalize_san(pred.get("san")) == normalize_san(truth.get("san"))
    return bool(side_ok and ply_ok and (uci_ok or san_ok))


def time_ok(pred: dict[str, Any], truth: dict[str, Any]) -> tuple[bool, float | None]:
    pred_t = parse_time(pred.get("video_time"))
    truth_t = parse_time(truth.get("video_time"))
    if pred_t is None or truth_t is None:
        return False, None
    error = abs(pred_t - truth_t)
    return error <= TIME_TOLERANCE_S, round(error, 3)


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, details: Any = None) -> None:
    check: dict[str, Any] = {"name": name, "passed": bool(passed)}
    if details is not None:
        check["details"] = details
    checks.append(check)


def score_moves(pred_moves: Any, truth_moves: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if not isinstance(pred_moves, list):
        pred_moves = []

    for index, truth in enumerate(truth_moves):
        pred = pred_moves[index] if index < len(pred_moves) and isinstance(pred_moves[index], dict) else {}
        ident = identity_ok(pred, truth)
        time_match, time_error = time_ok(pred, truth)
        label = f"ply_{truth['ply']:03d}_{truth['side']}_{truth['san']}"
        add_check(
            checks,
            f"{label}.identity",
            ident,
            {"expected_uci": truth["uci"], "predicted_uci": pred.get("uci")},
        )
        add_check(
            checks,
            f"{label}.time",
            ident and time_match,
            {"expected_time": truth["video_time"], "predicted_time": pred.get("video_time"), "error_s": time_error},
        )

    for extra_index in range(max(0, len(pred_moves) - len(truth_moves))):
        add_check(checks, f"extra_move_{extra_index + 1}", False)

    return checks


def capture_detail_ok(pred: dict[str, Any], truth: dict[str, Any]) -> bool:
    return (
        normalize_token(pred.get("capture_square")) == normalize_token(truth.get("capture_square"))
        and normalize_token(pred.get("captured_piece")) == normalize_token(truth.get("captured_piece"))
    )


def score_captures(pred_events: Any, truth_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if not isinstance(pred_events, list):
        pred_events = []
    by_ply = {
        event.get("ply"): event
        for event in pred_events
        if isinstance(event, dict) and isinstance(event.get("ply"), int)
    }

    for truth in truth_events:
        pred = by_ply.get(truth["ply"], {})
        ident = isinstance(pred, dict) and identity_ok(pred, truth)
        detail = isinstance(pred, dict) and capture_detail_ok(pred, truth)
        time_match, time_error = time_ok(pred if isinstance(pred, dict) else {}, truth)
        label = f"capture_ply_{truth['ply']:03d}_{truth['san']}"
        add_check(checks, f"{label}.identity", ident)
        add_check(
            checks,
            f"{label}.detail",
            ident and detail,
            {
                "expected_square": truth["capture_square"],
                "expected_piece": truth["captured_piece"],
                "predicted_square": pred.get("capture_square") if isinstance(pred, dict) else None,
                "predicted_piece": pred.get("captured_piece") if isinstance(pred, dict) else None,
            },
        )
        add_check(
            checks,
            f"{label}.time",
            ident and time_match,
            {"expected_time": truth["video_time"], "predicted_time": pred.get("video_time") if isinstance(pred, dict) else None, "error_s": time_error},
        )

    truth_plys = {event["ply"] for event in truth_events}
    extra = [
        event for event in pred_events
        if isinstance(event, dict) and event.get("ply") not in truth_plys
    ]
    for extra_index, _event in enumerate(extra):
        add_check(checks, f"extra_capture_{extra_index + 1}", False)

    return checks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solution", required=True, type=Path)
    parser.add_argument("--reward-json", required=True, type=Path)
    parser.add_argument("--reward-txt", required=True, type=Path)
    args = parser.parse_args()

    truth = json.loads(GROUND_TRUTH_PATH.read_text())
    solution, reason = load_solution(args.solution)
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "result",
        normalize_token(solution.get("result")) == normalize_token(truth["result"]),
        {"expected": truth["result"], "predicted": solution.get("result")},
    )
    checks.extend(score_moves(solution.get("moves"), truth["moves"]))
    checks.extend(score_captures(solution.get("capture_events"), truth["capture_events"]))

    passed = sum(1 for check in checks if check["passed"])
    total = len(checks)
    reward = round(passed / total if total else 0.0, 4)
    details = {
        "reason": reason,
        "checks_passed": passed,
        "checks_total": total,
        "n_ground_truth_moves": len(truth["moves"]),
        "n_ground_truth_captures": len(truth["capture_events"]),
        "n_predicted_moves": len(solution.get("moves", [])) if isinstance(solution.get("moves"), list) else 0,
        "n_predicted_captures": len(solution.get("capture_events", [])) if isinstance(solution.get("capture_events"), list) else 0,
        "time_tolerance_s": TIME_TOLERANCE_S,
        "checks": checks,
    }

    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps({"reward": reward, "details": details}, indent=2))
    args.reward_txt.write_text(f"{reward}\n")


if __name__ == "__main__":
    main()
