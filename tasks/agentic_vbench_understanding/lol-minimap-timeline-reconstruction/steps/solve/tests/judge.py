#!/usr/bin/env python3
"""Grade a minimap-only LoL timeline + economy reconstruction.

Pure Python stdlib, deterministic. No VLM/LLM judge.

The agent must list every key event of one full game as a 5-tuple
(game_clock_s, type, entity, minute_gain, leader_before), reconstructed from the
map view only (no HUD/clock/killfeed/names/gold). A predicted event is a true
positive only when it FULLY matches a ground-truth event on (type, entity,
minute_gain, leader_before) AND |Dt| <= TOL seconds. We then score by F1 (so both
misses and false positives hurt). reward = F1.

Why this task and metric: ~111 events across ~39.5 minutes must each be localized
and identified on a low-density abstract map, plus two economy judgements the video
never shows (inferred from map macro). No single frame yields either economy field,
and the map strips LoL's statistical HUD graphics (killfeed, tower-bar, dragon/baron
announcer), so only genuinely reconstructing the game off the video scores. The
oracle (exact list) -> 1.0; an empty or guessed list -> ~0; a strong agent that
mis-identifies portraits or cannot infer economy -> well below 0.1.

Ground truth lives verifier-side in gt.json next to this script (mounted for the
verify step only; the agent never sees it). The schema is the unified 5-tuple; the
key() function also canonicalizes the older dragon_kill/baron_kill + team schema so
legacy answers still score.
"""
import argparse
import json
import os
import re
from pathlib import Path

TOL = 3.0  # seconds of tolerance (recording is offset-0: video_t == game_clock_s)


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def n(s):
    return str(s if s is not None else "").strip().lower()


def key(e):
    """Unified 5-tuple: (type, entity, minute_gain, leader_before) + time (matched
    separately). type in {champion_kill, tower_kill, epic_monster_kill}. entity:
    champion / "{team}_{tower}" / specific epic monster (drake element, elder,
    baron). Canonicalizes old-schema answers too."""
    t = e.get("type", "")
    ent = e.get("entity")
    if ent is None:
        if t == "champion_kill":
            ent = e.get("dead_champion")
        elif t == "tower_kill":
            ent = f"{e.get('team')}_{e.get('tower')}"
        elif t == "dragon_kill":
            ent = e.get("subtype")
        elif t == "baron_kill":
            ent = "baron"
    ct = "epic_monster_kill" if t in ("dragon_kill", "baron_kill") else t
    return (ct, n(ent), n(e.get("minute_gain")), n(e.get("leader_before")))


def score(gt, ans):
    gt_e = gt["events"]
    an_e = ans.get("events", []) if isinstance(ans, dict) else []
    used = [False] * len(gt_e)
    tp = 0
    for a in an_e:
        try:
            ak, at = key(a), float(a["game_clock_s"])
        except Exception:
            continue
        best, bdt = -1, TOL + 1
        for i, g in enumerate(gt_e):
            if used[i] or key(g) != ak:
                continue
            dt_ = abs(float(g["game_clock_s"]) - at)
            if dt_ <= TOL and dt_ < bdt:
                best, bdt = i, dt_
        if best >= 0:
            used[best] = True
            tp += 1
    fp = max(0, len(an_e) - tp)
    fn = len(gt_e) - tp
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return f1, {"matched": tp, "fp": fp, "fn": fn,
                "precision": round(prec, 4), "recall": round(rec, 4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", required=True, type=Path)
    ap.add_argument("--reward-json", required=True, type=Path)
    ap.add_argument("--reward-txt", required=True, type=Path)
    ap.add_argument("--gt", type=Path, default=None,
                    help="ground-truth JSON; defaults to gt.json next to this script")
    args = ap.parse_args()

    here = Path(__file__).resolve().parent
    gt_path = args.gt if args.gt is not None else here / "gt.json"
    gt = load(gt_path)

    reason = "ok"
    ans = {}
    try:
        ans = json.loads(args.solution.read_text())
    except Exception as exc:  # malformed/missing output scores 0
        reason = f"unreadable solution.json: {exc}"

    reward, detail = score(gt, ans)
    detail["reason"] = reason
    detail["tolerance_s"] = TOL
    out = {"reward": round(reward, 4), "details": detail}
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps(out, indent=2))
    args.reward_txt.write_text(f"{round(reward, 4)}\n")
    print(json.dumps(out))


if __name__ == "__main__":
    main()
