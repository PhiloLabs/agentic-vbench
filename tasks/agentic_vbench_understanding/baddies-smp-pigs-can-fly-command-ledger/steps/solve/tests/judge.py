#!/usr/bin/env python3
"""Grade a spoken-command execution ledger for a multiplayer co-op session. Pure
stdlib, deterministic.

The agent watches one multiplayer Minecraft session (live voice chat on the audio
track, the recording player's first-person view on video) and must reconstruct every
actionable spoken command: who said it, to whom, what action on what object, who
visibly executed it, when execution started, and the outcome. A predicted command is a
true positive only when it FULLY reconstructs the chain: speaker, target, action,
object, executor, and outcome all match (normalized), the command timestamp is within
TOL_CMD seconds, execution start is within TOL_EXEC seconds (when execution occurs),
and the submitted evidence window overlaps the true execution interval by at least
IOU_MIN temporal IoU. One-to-one bipartite matching; reward = F1.

Why this resists shortcuts: the executor and outcome are physical facts visible only
on screen (audio-only models must guess who acted and whether it worked); deictic
objects ("put THAT there") resolve only visually; and the evidence window is pinned to
the on-screen execution, whose timing audio cannot know. Command speech, speaker
voices, and addressees live only on audio — video-only models cannot know what was
asked or by whom.
"""
import argparse
import json
import re
from pathlib import Path

TOL_CMD = 5.0      # s tolerance on the spoken-command timestamp
TOL_EXEC = 10.0    # s tolerance on execution start (speech-to-act gaps vary)
IOU_MIN = 0.5      # min temporal IoU between predicted and true evidence window
# `not_done` is gone by construction: this task only asks about requests that WERE
# eventually carried out. A never-executed row would have null executor and null
# timestamps, i.e. nothing the video settles — free points for a transcript-only
# model, which is exactly the leak the deferred framing removes.
OUTCOMES = {"completed", "partial", "corrected"}

# Scored fields. `speaker` and `target` are asked for in the prompt and reported in the
# diagnostics, but they are NOT scored: pinning which voice is speaking means
# recognising voices, which no annotator of this footage can do reliably, so grading on
# them would measure ground-truth noise rather than the agent's reading of the video.
# What IS scored is what the video settles: what was asked, who carried it out, when,
# how it turned out, and where the evidence is.
SCORED_FIELDS = ("action", "object", "executor", "outcome")
REPORTED_FIELDS = ("speaker", "target") + SCORED_FIELDS


def norm(s: str) -> str:
    """Lowercase and strip everything but a-z0-9 so 'Iron_Blocks' == 'iron blocks'."""
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def to_float(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def iou(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
    lo = max(a_start, b_start)
    hi = min(a_end, b_end)
    inter = max(0.0, hi - lo)
    union = (a_end - a_start) + (b_end - b_start) - inter
    return inter / union if union > 0 else 0.0


def is_match(pred: dict, gt: dict) -> bool:
    ct = to_float(pred.get("command_time_s"))
    if ct is None or abs(ct - float(gt["command_time_s"])) > TOL_CMD:
        return False
    for field in SCORED_FIELDS:
        if norm(pred.get(field, "")) != norm(gt[field]):
            return False
    gt_exec = gt.get("execution_start_s")
    if gt_exec is not None:
        et = to_float(pred.get("execution_start_s"))
        if et is None or abs(et - float(gt_exec)) > TOL_EXEC:
            return False
        ev_s = to_float(pred.get("evidence_start_s"))
        ev_e = to_float(pred.get("evidence_end_s"))
        if ev_s is None or ev_e is None or ev_e < ev_s:
            return False
        if iou(ev_s, ev_e, gt["evidence_start_s"], gt["evidence_end_s"]) < IOU_MIN:
            return False
    return True


def _diagnostics(preds: list, ground_truth: list) -> dict:
    """Non-scored breakdown: did the agent FIND the commands, and which field failed?

    Pairs predictions to ground truth on command time alone (the loosest possible
    notion of "found it"), then reports per-field agreement over those pairs. This
    separates "never located the utterance" from "located it but misread the video",
    which is what tells a reviewer the task is hard rather than impossible.
    """
    taken = [False] * len(ground_truth)
    pairs = []
    for pr in preds:
        if not isinstance(pr, dict):
            continue
        ct = to_float(pr.get("command_time_s"))
        if ct is None:
            continue
        best, best_gap = None, None
        for i, gt in enumerate(ground_truth):
            if taken[i]:
                continue
            gap = abs(ct - float(gt["command_time_s"]))
            if gap <= TOL_CMD and (best_gap is None or gap < best_gap):
                best, best_gap = i, gap
        if best is not None:
            taken[best] = True
            pairs.append((pr, ground_truth[best]))

    n_det, n_gt = len(pairs), len(ground_truth)
    det_p = n_det / len(preds) if preds else 0.0
    det_r = n_det / n_gt if n_gt else 0.0
    det_f1 = (2 * det_p * det_r / (det_p + det_r)) if (det_p + det_r) else 0.0
    field_hits = {f: 0 for f in REPORTED_FIELDS}
    exec_ok = ev_ok = 0
    for pr, gt in pairs:
        for f in field_hits:
            if norm(pr.get(f, "")) == norm(gt[f]):
                field_hits[f] += 1
        g_exec = gt.get("execution_start_s")
        p_exec = to_float(pr.get("execution_start_s"))
        if (g_exec is None and p_exec is None) or (
                g_exec is not None and p_exec is not None
                and abs(p_exec - float(g_exec)) <= TOL_EXEC):
            exec_ok += 1
        if gt.get("evidence_start_s") is None:
            ev_ok += 1
        else:
            ps, pe = to_float(pr.get("evidence_start_s")), to_float(pr.get("evidence_end_s"))
            if ps is not None and pe is not None and pe >= ps and iou(
                    ps, pe, gt["evidence_start_s"], gt["evidence_end_s"]) >= IOU_MIN:
                ev_ok += 1
    per = (lambda n: round(n / n_det, 4) if n_det else 0.0)
    return {
        "detected_commands": n_det,
        "detection_f1": round(det_f1, 4),
        "field_accuracy_among_detected": {f: per(n) for f, n in field_hits.items()},
        "execution_time_ok_among_detected": per(exec_ok),
        "evidence_window_ok_among_detected": per(ev_ok),
    }


def score(preds: list, ground_truth: list) -> dict:
    used = [False] * len(ground_truth)
    tp = 0
    for pr in preds:
        if not isinstance(pr, dict):
            continue
        for i, gt in enumerate(ground_truth):
            if not used[i] and is_match(pr, gt):
                used[i] = True
                tp += 1
                break
    n_pred, n_gt = len(preds), len(ground_truth)
    precision = tp / n_pred if n_pred else 0.0
    recall = tp / n_gt if n_gt else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "reward": round(f1, 4),
        "details": {
            "n_ground_truth": n_gt,
            "n_predicted": n_pred,
            "true_positives": tp,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "command_time_tolerance_s": TOL_CMD,
            "execution_time_tolerance_s": TOL_EXEC,
            "evidence_iou_min": IOU_MIN,
            "diagnostics": _diagnostics(preds, ground_truth),
        },
    }


def load_ground_truth(path: Path) -> list:
    data = json.loads(path.read_text())
    gt = data["commands"] if isinstance(data, dict) else data
    for e in gt:
        if norm(e["outcome"]) not in {norm(x) for x in OUTCOMES}:
            raise ValueError(f"ground-truth outcome not in {OUTCOMES}: {e}")
        if e.get("execution_start_s") is not None and (
                e.get("evidence_start_s") is None or e.get("evidence_end_s") is None):
            raise ValueError(f"executed command missing evidence window: {e}")
    return gt


def read_solution(path: Path) -> tuple[list, str]:
    try:
        sol = json.loads(path.read_text())
        preds = sol.get("commands", []) if isinstance(sol, dict) else sol
        if not isinstance(preds, list):
            raise ValueError("commands is not a list")
        return preds, "ok"
    except Exception as exc:  # noqa: BLE001 - malformed output scores 0
        return [], f"unreadable solution.json: {exc}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", required=True, type=Path)
    ap.add_argument("--ground-truth", required=True, type=Path,
                    help="verifier-side ground_truth.json (never in the agent image)")
    ap.add_argument("--reward-json", required=True, type=Path)
    ap.add_argument("--reward-txt", required=True, type=Path)
    args = ap.parse_args()

    ground_truth = load_ground_truth(args.ground_truth)
    preds, reason = read_solution(args.solution)
    out = score(preds, ground_truth)
    out["details"]["reason"] = reason

    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps(out, indent=2))
    args.reward_txt.write_text(f"{out['reward']}\n")


if __name__ == "__main__":
    main()
