#!/usr/bin/env python3
"""Reference trade-episode derivation from a flat kill list. Deterministic.

A trade episode: kill A->B at t1, then the EARLIEST kill of A by a teammate of B
with 0 < t2 - t1 <= 5.0 in the same round. One episode per initial kill.
Team membership: P1..P5 vs P6..P10 (matches the roster labeling).
"""
import json
import re
import sys

WINDOW = 5.0


def team(label):
    return 0 if int(label[1:]) <= 5 else 1


def canon_weapon(w):
    return re.sub(r"[^a-z0-9]", "", str(w).lower())


def derive(kills):
    """kills: list of {t, round, killer, victim, weapon}. Returns episodes."""
    kills = sorted(kills, key=lambda k: k["t"])
    episodes = []
    for a in kills:
        cands = [b for b in kills
                 if b["round"] == a["round"]
                 and b["victim"] == a["killer"]
                 and team(b["killer"]) == team(a["victim"])
                 and 0 < b["t"] - a["t"] <= WINDOW]
        if not cands:
            continue
        b = min(cands, key=lambda k: k["t"])
        episodes.append({
            "round": a["round"],
            "initial_kill": {"t": round(a["t"], 2), "killer": a["killer"],
                             "victim": a["victim"], "weapon": canon_weapon(a["weapon"])},
            "trade_kill": {"t": round(b["t"], 2), "killer": b["killer"],
                           "victim": b["victim"], "weapon": canon_weapon(b["weapon"])},
        })
    return sorted(episodes, key=lambda e: e["initial_kill"]["t"])


if __name__ == "__main__":
    # Build the rounds 1-2 PILOT GT from the debug kills JSON (has weapons).
    src = json.load(open(sys.argv[1], encoding="utf-8-sig"))
    rows = src if isinstance(src, list) else src.get("kills", src.get("ledger", []))
    kills = [{"t": r["t_video"], "round": r["round"], "killer": r["killer"],
              "victim": r["victim"], "weapon": r["weapon"]} for r in rows]
    eps = derive(kills)
    print(json.dumps({"trade_episodes": eps}, indent=2))
    print(f"\n{len(eps)} episodes from {len(kills)} kills", file=sys.stderr)
