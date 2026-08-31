#!/usr/bin/env python3
"""Build the ground truth for `soccer-restart-outcome-chains` MECHANICALLY from a
SoccerNet-v2 `Labels-v2.json`. No human annotation, no judgment calls -- every
field is a deterministic transform of the published, multi-annotator labels.

SoccerNet-v2 Labels-v2.json shape (one file per match, both halves):
    {
      "UrlLocal": "...",
      "annotations": [
        {"gameTime": "1 - 00:29", "label": "Ball out of play",
         "position": "29049", "team": "not applicable", "visibility": "visible"},
        {"gameTime": "1 - 00:39", "label": "Throw-in",
         "position": "39496", "team": "home", "visibility": "not shown"},
        ...
      ]
    }
`position` is milliseconds WITHIN the half named by gameTime ("1 -" / "2 -").
We build a single timeline by offsetting half-2 by the half-1 duration.

Derivation (all mechanical):
  t            = event abs time (half-2 offset by --half1-duration-sec)
  restart_type = the restart event's label  (Throw-in / Corner / free-kicks)
  restart_team = the restart event's team    (home / away; drop "not applicable")
  outcome      = scan the same log: goal_within_30s if a Goal in [t, t+30], else
                 shot_within_15s if a Shot on/off target in [t, t+15], else none
Only visibility == "visible" restart events enter GT. Deterministic tie-break:
(t, label). No fields are invented.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os

# SoccerNet-v2 class names -> our integer codes (confirm against your Labels-v2.json).
RESTART_TYPES = {"Throw-in": 1, "Corner": 2, "Direct free-kick": 3, "Indirect free-kick": 4}
OUTCOMES = {"none": 0, "shot_within_15s": 1, "goal_within_30s": 2}
SHOT_LABELS = {"Shots on target", "Shots off target", "Shot on target", "Shot off target"}
GOAL_LABEL = "Goal"
SHOT_WINDOW_SEC = 15.0
GOAL_WINDOW_SEC = 30.0
DEFAULT_TAU_SEC = 3.0


def _half_and_pos(ann: dict) -> tuple[int, float]:
    half = int(str(ann["gameTime"]).split("-")[0].strip())
    return half, float(ann["position"]) / 1000.0  # ms -> s within the half


def build(labels_path: str, half1_duration_sec: float | None, tau: float) -> dict:
    with open(labels_path, "r", encoding="utf-8") as f:
        labels = json.load(f)
    anns = labels["annotations"]

    # Absolute timeline: offset half-2 by half-1 duration (default = last half-1 event + 60s).
    if half1_duration_sec is None:
        h1_last = max((_half_and_pos(a)[1] for a in anns if _half_and_pos(a)[0] == 1), default=0.0)
        half1_duration_sec = h1_last + 60.0

    def abs_t(ann: dict) -> float:
        half, pos = _half_and_pos(ann)
        return pos if half == 1 else pos + half1_duration_sec

    # Index shots/goals for outcome lookup.
    shots = sorted(abs_t(a) for a in anns if a["label"] in SHOT_LABELS)
    goals = sorted(abs_t(a) for a in anns if a["label"] == GOAL_LABEL)

    def outcome_of(t: float) -> int:
        if any(t <= g <= t + GOAL_WINDOW_SEC for g in goals):
            return OUTCOMES["goal_within_30s"]
        if any(t <= s <= t + SHOT_WINDOW_SEC for s in shots):
            return OUTCOMES["shot_within_15s"]
        return OUTCOMES["none"]

    instances = []
    for a in anns:
        if a["label"] not in RESTART_TYPES:
            continue
        if a.get("visibility") != "visible":
            continue
        team = a.get("team")
        if team not in ("home", "away"):
            continue  # drop "not applicable" -> no ambiguous attribution
        t = abs_t(a)
        instances.append({
            "t": round(t, 3),
            "restart_type": RESTART_TYPES[a["label"]],
            "team": team,
            "outcome": outcome_of(t),
            "label": a["label"],
        })

    instances.sort(key=lambda x: (x["t"], x["label"]))  # deterministic tie-break
    for x in instances:
        del x["label"]

    return {
        "match_id": labels.get("UrlLocal", "unknown"),
        "restart_types": RESTART_TYPES,
        "outcomes": OUTCOMES,
        "half1_duration_sec": half1_duration_sec,
        "tau_sec": tau,
        "shot_window_sec": SHOT_WINDOW_SEC,
        "goal_window_sec": GOAL_WINDOW_SEC,
        "n_instances": len(instances),
        "source": "SoccerNet-v2 Labels-v2.json (mechanical derivation, no hand labeling)",
        "instances": instances,
    }


def _load_judge():
    """Load the shipped verifier, steps/solve/tests/judge.py, from this task folder."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # provenance/..
    path = os.path.join(root, "steps", "solve", "tests", "judge.py")
    spec = importlib.util.spec_from_file_location("judge", path)
    judge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(judge)
    return judge


def prove(gt: dict, check_shipped: bool) -> None:
    """Demonstrate provenance against the shipped verifier. Two asserts:

    1. verifier(oracle) == 1.0: the derived answer key, played back as a solution,
       scores exactly 1.0 under judge.py's matcher.
    2. (when check_shipped) the derived instances equal judge.py's hardcoded
       GROUND_TRUTH entry for entry, so the shipped answer key IS this mechanical
       derivation and nothing else.
    """
    judge = _load_judge()
    derived = [{"t": i["t"], "restart_type": i["restart_type"], "team": i["team"],
                "outcome": i["outcome"]} for i in gt["instances"]]

    if check_shipped:
        assert derived == judge.GROUND_TRUTH, (
            "derived GT does not match judge.py GROUND_TRUTH -- if you are building a "
            "different match, pass --no-check-judge and regenerate judge.py's answer key")
        print(f"provenance: derived GT == shipped judge.py GROUND_TRUTH ({len(derived)} entries)")

    # verifier(oracle) == 1.0 on the derivation itself
    judge.GROUND_TRUTH = derived
    preds = [judge._norm(e) for e in derived]
    tp = judge._max_monotonic(preds, judge._match)
    n = len(derived)
    precision = tp / n if n else 0.0
    recall = tp / n if n else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    assert n > 0 and f1 == 1.0, f"verifier(oracle) != 1.0 (tp={tp}/{n}, f1={f1})"
    print("provenance: verifier(oracle) == 1.0 CONFIRMED")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build gt.json mechanically from SoccerNet-v2 Labels-v2.json.")
    ap.add_argument("--labels", required=True, help="path to Labels-v2.json")
    ap.add_argument("--half1-duration-sec", type=float, default=None, help="length of the first-half video (for the abs timeline)")
    ap.add_argument("--tau", type=float, default=DEFAULT_TAU_SEC)
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-check-judge", action="store_true",
                    help="skip the derived-GT == judge.py GROUND_TRUTH equality check "
                         "(use when building a match other than the shipped one)")
    args = ap.parse_args(argv)

    gt = build(args.labels, args.half1_duration_sec, args.tau)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(gt, f, ensure_ascii=False, indent=2)
    n = gt["n_instances"]
    from collections import Counter
    oc = Counter(i["outcome"] for i in gt["instances"])
    print(f"wrote {args.out}: {n} visible restarts | outcome dist none/shot/goal = "
          f"{oc.get(0,0)}/{oc.get(1,0)}/{oc.get(2,0)}")
    prove(gt, check_shipped=not args.no_check_judge)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
