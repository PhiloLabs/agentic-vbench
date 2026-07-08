#!/usr/bin/env python3
"""Grade a council-meeting roll-call vote timeline. Pure stdlib, deterministic.

The agent must reconstruct four agenda items and six roll-call vote events from the
meeting video. A prediction receives credit only when it matches the hidden agenda
item and vote event and reconstructs the event details: timestamps, motion type,
mover/seconder, roll-call sets, result, tie-breaker, and item-linked public-comment
count. Reward is an F1-like score over per-event credit so both missing votes and
extra hallucinated votes hurt.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

FULL_TIME_TOL = 20
PARTIAL_TIME_TOL = 60
MATCH_TIME_TOL = 5 * 60
IDENTITY_MATCH_MIN = 0.75
MISSING = object()

CANON_NAMES = {
    "barbara_de_michele": "Barbara de Michele",
    "stacy_goodman": "Stacy Goodman",
    "zach_hall": "Zach Hall",
    "victoria_hunt": "Victoria Hunt",
    "tola_marts": "Tola Marts",
    "chris_reh": "Chris Reh",
    "lindsey_walsh": "Lindsey Walsh",
    "mary_lou_pauly": "Mary Lou Pauly",
}

NAME_ALIASES = {
    "barbarademichele": "Barbara de Michele",
    "barbarademichelle": "Barbara de Michele",
    "demichele": "Barbara de Michele",
    "demichelle": "Barbara de Michele",
    "dmichele": "Barbara de Michele",
    "dmichelle": "Barbara de Michele",
    "stacygoodman": "Stacy Goodman",
    "staceygoodman": "Stacy Goodman",
    "goodman": "Stacy Goodman",
    "zachhall": "Zach Hall",
    "zackhall": "Zach Hall",
    "hall": "Zach Hall",
    "victoriahunt": "Victoria Hunt",
    "hunt": "Victoria Hunt",
    "tolamarts": "Tola Marts",
    "tolamartz": "Tola Marts",
    "marts": "Tola Marts",
    "martz": "Tola Marts",
    "chrisreh": "Chris Reh",
    "reh": "Chris Reh",
    "ray": "Chris Reh",
    "lindseywalsh": "Lindsey Walsh",
    "lindsaywalsh": "Lindsey Walsh",
    "walsh": "Lindsey Walsh",
    "welsh": "Lindsey Walsh",
    "maryloupauly": "Mary Lou Pauly",
    "maryloupaulie": "Mary Lou Pauly",
    "mayorpauly": "Mary Lou Pauly",
    "mayorpaulie": "Mary Lou Pauly",
    "pauly": "Mary Lou Pauly",
    "paulie": "Mary Lou Pauly",
}

ITEM_ALIASES = {
    "consentcalendar": "consent_calendar",
    "consentagenda": "consent_calendar",
    "consent": "consent_calendar",
    "ab8256": "AB 8256",
    "8256": "AB 8256",
    "climateactionplan": "AB 8256",
    "ab8292": "AB 8292",
    "8292": "AB 8292",
    "frontlineworkerincentivepay": "AB 8292",
    "frontlineworker": "AB 8292",
    "ab8303": "AB 8303",
    "8303": "AB 8303",
    "stepbackstandards": "AB 8303",
    "title18": "AB 8303",
}

MOTION_ALIASES = {
    "approveconsentcalendar": "approve_consent_calendar",
    "approveconsentagenda": "approve_consent_calendar",
    "consentcalendar": "approve_consent_calendar",
    "amendmotion": "amend_motion",
    "amendment": "amend_motion",
    "amend": "amend_motion",
    "adoptresolution": "adopt_resolution",
    "resolution": "adopt_resolution",
    "climateactionplan": "adopt_resolution",
    "adoptordinanceandratifymous": "adopt_ordinance_and_ratify_mous",
    "adoptordinanceratifymous": "adopt_ordinance_and_ratify_mous",
    "ordinanceandmous": "adopt_ordinance_and_ratify_mous",
    "frontlineworkerordinance": "adopt_ordinance_and_ratify_mous",
    "approvemotionasamended": "approve_motion_as_amended",
    "mainmotionasamended": "approve_motion_as_amended",
    "motionasamended": "approve_motion_as_amended",
}

RESULT_ALIASES = {
    "passed": "passed",
    "pass": "passed",
    "carried": "passed",
    "approved": "passed",
    "unanimous": "passed",
    "passedaftermayoraltiebreak": "passed_after_mayoral_tie_break",
    "passedaftermayortiebreak": "passed_after_mayoral_tie_break",
    "carriedaftermayoraltiebreak": "passed_after_mayoral_tie_break",
    "mayortiebreak": "passed_after_mayoral_tie_break",
    "tiebreak": "passed_after_mayoral_tie_break",
    "failed": "failed",
    "fail": "failed",
}

GT_ITEMS = {
    "consent_calendar": {
        "agenda_item_id": "consent_calendar",
        "item_start_time": "01:11:06",
        "spoken_item_linked_public_comment_count": 0,
    },
    "AB 8256": {
        "agenda_item_id": "AB 8256",
        "item_start_time": "01:13:32",
        "spoken_item_linked_public_comment_count": 5,
    },
    "AB 8292": {
        "agenda_item_id": "AB 8292",
        "item_start_time": "01:46:37",
        "spoken_item_linked_public_comment_count": 0,
    },
    "AB 8303": {
        "agenda_item_id": "AB 8303",
        "item_start_time": "01:55:09",
        "spoken_item_linked_public_comment_count": 0,
    },
}

GROUND_TRUTH = [
    {
        "event_id": "consent_calendar_approval",
        "agenda_item_id": "consent_calendar",
        "vote_time": "01:13:08",
        "motion_type": "approve_consent_calendar",
        "mover": "Victoria Hunt",
        "seconder": "Lindsey Walsh",
        "result": "passed",
        "yes": [
            "Lindsey Walsh",
            "Barbara de Michele",
            "Stacy Goodman",
            "Zach Hall",
            "Victoria Hunt",
            "Tola Marts",
        ],
        "no": [],
        "absent": ["Chris Reh"],
        "tie_breaker": None,
    },
    {
        "event_id": "ab8256_climate_action_plan_amendment",
        "agenda_item_id": "AB 8256",
        "vote_time": "01:44:17",
        "motion_type": "amend_motion",
        "mover": "Victoria Hunt",
        "seconder": "Zach Hall",
        "result": "passed",
        "yes": [
            "Barbara de Michele",
            "Zach Hall",
            "Victoria Hunt",
            "Tola Marts",
            "Lindsey Walsh",
        ],
        "no": ["Stacy Goodman"],
        "absent": ["Chris Reh"],
        "tie_breaker": None,
    },
    {
        "event_id": "ab8256_climate_action_plan_main_as_amended",
        "agenda_item_id": "AB 8256",
        "vote_time": "01:45:50",
        "motion_type": "adopt_resolution",
        "mover": "Victoria Hunt",
        "seconder": "Barbara de Michele",
        "result": "passed",
        "yes": [
            "Stacy Goodman",
            "Zach Hall",
            "Victoria Hunt",
            "Tola Marts",
            "Lindsey Walsh",
            "Barbara de Michele",
        ],
        "no": [],
        "absent": ["Chris Reh"],
        "tie_breaker": None,
    },
    {
        "event_id": "ab8292_frontline_worker_incentive_pay",
        "agenda_item_id": "AB 8292",
        "vote_time": "01:54:17",
        "motion_type": "adopt_ordinance_and_ratify_mous",
        "mover": "Stacy Goodman",
        "seconder": "Lindsey Walsh",
        "result": "passed",
        "yes": [
            "Zach Hall",
            "Victoria Hunt",
            "Tola Marts",
            "Lindsey Walsh",
            "Barbara de Michele",
            "Stacy Goodman",
        ],
        "no": [],
        "absent": ["Chris Reh"],
        "tie_breaker": None,
    },
    {
        "event_id": "ab8303_step_back_standards_amendment",
        "agenda_item_id": "AB 8303",
        "vote_time": "02:24:05",
        "motion_type": "amend_motion",
        "mover": "Stacy Goodman",
        "seconder": "Tola Marts",
        "result": "passed_after_mayoral_tie_break",
        "yes": ["Stacy Goodman", "Zach Hall", "Tola Marts"],
        "no": ["Barbara de Michele", "Victoria Hunt", "Lindsey Walsh"],
        "absent": ["Chris Reh"],
        "tie_breaker": {"name": "Mary Lou Pauly", "vote": "yes"},
    },
    {
        "event_id": "ab8303_step_back_standards_main_as_amended",
        "agenda_item_id": "AB 8303",
        "vote_time": "02:26:57",
        "motion_type": "approve_motion_as_amended",
        "mover": "Victoria Hunt",
        "seconder": "Lindsey Walsh",
        "result": "passed",
        "yes": [
            "Tola Marts",
            "Lindsey Walsh",
            "Barbara de Michele",
            "Stacy Goodman",
            "Zach Hall",
            "Victoria Hunt",
        ],
        "no": [],
        "absent": ["Chris Reh"],
        "tie_breaker": None,
    },
]


def squish(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def canon_item(value: Any) -> str | None:
    if value in GT_ITEMS:
        return str(value)
    s = squish(value)
    return ITEM_ALIASES.get(s)


def canon_motion(value: Any) -> str | None:
    if isinstance(value, str) and value in set(MOTION_ALIASES.values()):
        return value
    return MOTION_ALIASES.get(squish(value))


def canon_result(value: Any) -> str | None:
    if isinstance(value, str) and value in set(RESULT_ALIASES.values()):
        return value
    return RESULT_ALIASES.get(squish(value))


def canon_name(value: Any) -> str | None:
    if isinstance(value, str) and value in CANON_NAMES.values():
        return value
    return NAME_ALIASES.get(squish(value))


def canon_name_set(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    out = set()
    for value in values:
        name = canon_name(value)
        if name:
            out.add(name)
    return out


def parse_time(value: Any) -> int | None:
    if isinstance(value, (int, float)) and value >= 0:
        return int(round(float(value)))
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return int(round(float(text)))
    parts = text.split(":")
    try:
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + int(float(s))
        if len(parts) == 2:
            m, s = parts
            return int(m) * 60 + int(float(s))
    except ValueError:
        return None
    return None


def time_credit(pred: Any, gt: Any) -> float:
    ps = parse_time(pred)
    gs = parse_time(gt)
    if ps is None or gs is None:
        return 0.0
    diff = abs(ps - gs)
    if diff <= FULL_TIME_TOL:
        return 1.0
    if diff <= PARTIAL_TIME_TOL:
        return 0.5
    return 0.0


def set_credit(pred: set[str], gt: set[str]) -> float:
    if not pred and not gt:
        return 1.0
    if not pred or not gt:
        return 0.0
    return len(pred & gt) / len(pred | gt)


def count_credit(pred: Any, gt: int) -> float:
    try:
        value = int(pred)
    except (TypeError, ValueError):
        return 0.0
    if value == gt:
        return 1.0
    if abs(value - gt) == 1:
        return 0.5
    return 0.0


def field_set_credit(pred: dict[str, Any], field: str, gt: set[str]) -> float:
    if field not in pred or not isinstance(pred.get(field), list):
        return 0.0
    return set_credit(canon_name_set(pred[field]), gt)


def tie_break_credit(pred: Any, gt: Any) -> float:
    if pred is MISSING:
        return 0.0
    if gt is None:
        return 1.0 if pred in (None, {}, [], "", "none", "null") else 0.0
    if not isinstance(pred, dict):
        return 0.0
    name_ok = canon_name(pred.get("name")) == gt["name"]
    vote_ok = squish(pred.get("vote")) in {"yes", "aye", "i"}
    return 0.5 * float(name_ok) + 0.5 * float(vote_ok)


def item_lookup(solution: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    items = solution.get("agenda_items", [])
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        key = canon_item(item.get("agenda_item_id") or item.get("item_id"))
        if key and key not in out:
            out[key] = item
    return out


def identity_score(pred: dict[str, Any], gt: dict[str, Any]) -> float:
    item = canon_item(pred.get("agenda_item_id") or pred.get("item_id"))
    motion = canon_motion(pred.get("motion_type"))
    ps = parse_time(pred.get("vote_time"))
    gs = parse_time(gt["vote_time"])
    time = 0.0
    if ps is not None and gs is not None:
        diff = abs(ps - gs)
        if diff <= FULL_TIME_TOL:
            time = 1.0
        elif diff <= MATCH_TIME_TOL:
            time = max(0.0, 1.0 - diff / MATCH_TIME_TOL)
    return (
        0.45 * float(item == gt["agenda_item_id"]) +
        0.25 * float(motion == gt["motion_type"]) +
        0.30 * time
    )


def match_predictions(preds: list[dict[str, Any]]) -> list[tuple[int, int, float]]:
    candidates = []
    for pi, pred in enumerate(preds):
        for gi, gt in enumerate(GROUND_TRUTH):
            score = identity_score(pred, gt)
            if score >= IDENTITY_MATCH_MIN:
                candidates.append((score, pi, gi))
    candidates.sort(reverse=True)
    used_p: set[int] = set()
    used_g: set[int] = set()
    matches = []
    for score, pi, gi in candidates:
        if pi in used_p or gi in used_g:
            continue
        used_p.add(pi)
        used_g.add(gi)
        matches.append((pi, gi, score))
    return matches


def event_credit(pred: dict[str, Any], gt: dict[str, Any],
                 items: dict[str, dict[str, Any]]) -> tuple[float, dict[str, Any]]:
    item_id = canon_item(pred.get("agenda_item_id") or pred.get("item_id"))
    item = items.get(gt["agenda_item_id"], {})
    start_pred = pred.get("item_start_time", item.get("item_start_time"))
    count_pred = pred.get(
        "spoken_item_linked_public_comment_count",
        item.get("spoken_item_linked_public_comment_count"),
    )
    gt_item = GT_ITEMS[gt["agenda_item_id"]]

    yes_score = field_set_credit(pred, "yes", set(gt["yes"]))
    no_score = field_set_credit(pred, "no", set(gt["no"]))
    absent_score = field_set_credit(pred, "absent", set(gt["absent"]))

    components = {
        "agenda_item": float(item_id == gt["agenda_item_id"]),
        "motion_type": float(canon_motion(pred.get("motion_type")) == gt["motion_type"]),
        "vote_time": time_credit(pred.get("vote_time"), gt["vote_time"]),
        "item_start_time": time_credit(start_pred, gt_item["item_start_time"]),
        "mover": float(canon_name(pred.get("mover")) == gt["mover"]),
        "seconder": float(canon_name(pred.get("seconder")) == gt["seconder"]),
        "yes": yes_score,
        "no": no_score,
        "absent": absent_score,
        "result": float(canon_result(pred.get("result")) == gt["result"]),
        "tie_breaker": tie_break_credit(pred.get("tie_breaker", MISSING), gt["tie_breaker"]),
        "public_comment_count": count_credit(
            count_pred, gt_item["spoken_item_linked_public_comment_count"]
        ),
    }
    weights = {
        "agenda_item": 0.05,
        "motion_type": 0.10,
        "vote_time": 0.12,
        "item_start_time": 0.08,
        "mover": 0.07,
        "seconder": 0.07,
        "yes": 0.22,
        "no": 0.14,
        "absent": 0.04,
        "result": 0.05,
        "tie_breaker": 0.04,
        "public_comment_count": 0.02,
    }
    score = sum(weights[name] * components[name] for name in weights)
    return score, {"event_id": gt["event_id"], "score": round(score, 4), "components": components}


def load_solution(path: Path) -> tuple[dict[str, Any], str]:
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            raise ValueError("top-level JSON is not an object")
        return data, "ok"
    except Exception as exc:  # noqa: BLE001 - malformed outputs score 0
        return {}, f"unreadable solution.json: {exc}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", required=True, type=Path)
    ap.add_argument("--reward-json", required=True, type=Path)
    ap.add_argument("--reward-txt", required=True, type=Path)
    args = ap.parse_args()

    solution, reason = load_solution(args.solution)
    raw_preds = solution.get("vote_events", [])
    preds = [p for p in raw_preds if isinstance(p, dict)] if isinstance(raw_preds, list) else []
    items = item_lookup(solution)

    matches = match_predictions(preds)
    matched_scores = []
    credit_sum = 0.0
    for pi, gi, ident in matches:
        score, details = event_credit(preds[pi], GROUND_TRUTH[gi], items)
        details["identity_score"] = round(ident, 4)
        details["prediction_index"] = pi
        matched_scores.append(details)
        credit_sum += score

    n_pred = len(preds)
    n_gt = len(GROUND_TRUTH)
    precision = credit_sum / n_pred if n_pred else 0.0
    recall = credit_sum / n_gt if n_gt else 0.0
    reward = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    details = {
        "reason": reason,
        "n_ground_truth_vote_events": n_gt,
        "n_predicted_vote_events": n_pred,
        "n_matched_vote_events": len(matches),
        "precision_credit": round(precision, 4),
        "recall_credit": round(recall, 4),
        "matched_event_scores": matched_scores,
        "time_full_credit_tolerance_s": FULL_TIME_TOL,
        "time_partial_credit_tolerance_s": PARTIAL_TIME_TOL,
    }

    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps({"reward": round(reward, 4), "details": details}, indent=2))
    args.reward_txt.write_text(f"{round(reward, 4)}\n")


if __name__ == "__main__":
    main()
