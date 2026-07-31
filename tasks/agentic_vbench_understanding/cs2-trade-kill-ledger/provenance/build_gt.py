#!/usr/bin/env python3
"""Build the trade-kill ledger ground truth from the private CS2 .dem file.

Author-side tool (built and cross-checked with demoparser2==0.41.4 and pandas 2.3.x;
pandas>=3 breaks demoparser2's dataframe bridge). The runtime judge is pure stdlib.
The .dem is the oracle and never ships with the task. This script writes:

  provenance/gt_ledger.json                 (public: P-labels only, safe to commit)
  provenance/player_map.json                (PRIVATE steamid->label map, gitignored)
  steps/solve/tests/gt_ledger.json          (copy the judge reads)
  steps/solve/solution/oracle_ledger.json   (oracle answer solve.sh copies)

then self-checks by running the judge on the oracle (must score 1.0) and on an
empty attempt (must score 0.0).

Conventions (fixed here, not left to interpretation):
- Ledger = deaths caused by another player. Deaths to world/fall/bomb (weapon
  "worldent"/"planted_c4") and suicides are excluded.
- round_number = boundary-based: 1 + count(round_officially_ended ticks < kill tick),
  so kills in the aftermath after a round is decided still belong to that round
  (exit frags), and the final round (which has no officially_ended) still counts.
- was_traded = the killer is killed within TRADE_WINDOW_S by any player on the
  victim's team - INCLUDING the victim themselves via utility thrown before dying
  (posthumous grenade), and in the same round. Trades never cross round boundaries.
- t = (tick - t0_tick) / tickrate, t0 defaulting to round_announce_match_start.
  After the render exists, re-run with --t0-tick so t matches video time exactly.
- Labels: sort each starting team's players by steamid; starting team 2 -> P1..P5,
  starting team 3 -> P6..P10.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

TRADE_WINDOW_S = 5.0
# Must equal TOL in steps/solve/tests/judge.py: the no-ambiguous-pair assert below
# uses 2x this value to guarantee the judge's greedy matcher is one-candidate.
JUDGE_TOL_S = 5.0
WORLD_WEAPONS = {"worldent", "planted_c4", "world"}

HERE = Path(__file__).resolve().parent
TASK = HERE.parent


# demoparser2 0.41.4 is unreliable across REPEATED calls on one process: call
# sequences involving parse_player_info and/or several parse_event calls either
# deadlock the process-wide worker pool (unkillable UE state on macOS) or crash
# on a garbage-length allocation, depending on order. Two rules keep it safe,
# established empirically against this demo:
#   1. parse_player_info (+ header) runs in a throwaway subprocess;
#   2. the main process makes exactly ONE parse_events (plural) call for all
#      events it needs, on a fresh instance.
ROSTER_SNIPPET = """
import json, sys
from demoparser2 import DemoParser
p = DemoParser(sys.argv[1])
header = p.parse_header()
info = p.parse_player_info()
# sort in Python, not pandas: row order from the parser is not a contract
roster = sorted(((int(r.team_number), int(r.steamid)) for r in info.itertuples()))
print(json.dumps({
    "header": {k: str(v) for k, v in header.items()},
    "roster": [str(sid) for _, sid in roster],
    "teams": [team for team, _ in roster],
}))
"""


def roster_and_header(dem_path: Path):
    out = subprocess.run([sys.executable, "-c", ROSTER_SNIPPET, str(dem_path)],
                         check=True, capture_output=True, text=True, timeout=300)
    data = json.loads(out.stdout.strip().splitlines()[-1])
    assert len(data["roster"]) == 10, f"expected 10 players, got {len(data['roster'])}"
    teams = data["teams"]
    assert teams[:5] == [teams[0]] * 5 and teams[5:] == [teams[5]] * 5 \
        and teams[0] != teams[5], f"expected two teams of five, got {teams}"
    label = {sid: f"P{i + 1}" for i, sid in enumerate(data["roster"])}
    return label, data["header"]


def build(dem_path: Path, t0_tick: int | None):
    from demoparser2 import DemoParser

    print("stage: roster subprocess", flush=True)
    label, header = roster_and_header(dem_path)

    print("stage: parse events", flush=True)
    frames = dict(DemoParser(str(dem_path)).parse_events(
        ["round_announce_match_start", "round_officially_ended", "player_death"],
        player=["team_num"], other=["total_rounds_played", "is_warmup_period"],
    ))

    match_start = frames["round_announce_match_start"]
    assert len(match_start) == 1
    if t0_tick is None:
        t0_tick = int(match_start.iloc[0]["tick"])

    # Valve matchmaking is fixed 64-tick; verified once for this demo by measuring
    # game_time span across all ticks (64.00 exactly). A full parse_ticks scan is
    # slow on a 217MB demo, so we don't repeat it on every build.
    assert header.get("demo_version_name") == "valve_demo_2"
    tickrate = 64.0

    # demoparser2 emits each round_officially_ended twice; dedupe
    boundaries = sorted(set(int(t) for t in frames["round_officially_ended"]["tick"]))

    deaths = frames["player_death"].sort_values("tick")
    assert not deaths["is_warmup_period"].any(), "warmup deaths present; filter needed"

    def round_of(tick: int) -> int:
        return 1 + sum(1 for b in boundaries if b < tick)

    kills = []
    for row in deaths.itertuples():
        atk, vic = row.attacker_steamid, row.user_steamid
        if row.weapon in WORLD_WEAPONS or atk is None or (isinstance(atk, float)):
            continue  # world/fall/bomb death: not a kill
        atk, vic = str(atk), str(vic)
        if atk == vic:
            continue  # suicide: not a kill
        assert atk in label and vic in label, f"non-roster steamid at tick {row.tick}"
        kills.append({
            "tick": int(row.tick),
            "round": round_of(int(row.tick)),
            "victim_sid": vic,
            "killer_sid": atk,
            "victim_team": int(row.user_team_num),
            "killer_team": int(row.attacker_team_num),
        })

    # a player dies at most once per round; guards the round derivation
    seen = set()
    for k in kills:
        key = (k["round"], k["victim_sid"])
        assert key not in seen, f"double death {key}"
        seen.add(key)

    window = TRADE_WINDOW_S * tickrate
    for k in kills:
        k["was_traded"], k["trader_sid"] = False, None
        for k2 in kills:
            if (k2["victim_sid"] == k["killer_sid"]
                    and 0 < k2["tick"] - k["tick"] <= window
                    and k2["round"] == k["round"]
                    and k2["killer_team"] == k["victim_team"]):
                k["was_traded"], k["trader_sid"] = True, k2["killer_sid"]
                break

    ledger = [{
        "t": round((k["tick"] - t0_tick) / tickrate, 2),
        "round": k["round"],
        "victim": label[k["victim_sid"]],
        "killer": label[k["killer_sid"]],
        "was_traded": k["was_traded"],
        "trader": label[k["trader_sid"]] if k["trader_sid"] else None,
    } for k in kills]

    # no two same-(victim,killer) kills may fall within judge tolerance of each other
    for i, a in enumerate(ledger):
        for b in ledger[i + 1:]:
            if a["victim"] == b["victim"] and a["killer"] == b["killer"]:
                assert abs(a["t"] - b["t"]) > 2 * JUDGE_TOL_S, "ambiguous match pair"

    meta = {
        "map": header.get("map_name"),
        "tickrate": tickrate,
        "t0_tick": t0_tick,
        "n_rounds": round_of(int(deaths["tick"].max())),
        "n_kills": len(ledger),
        "n_traded": sum(1 for e in ledger if e["was_traded"]),
        "trade_window_s": TRADE_WINDOW_S,
    }
    return {"meta": meta, "ledger": ledger}, label


def self_check(gt: dict):
    judge = TASK / "steps" / "solve" / "tests" / "judge.py"
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)

        def score(payload) -> float:
            (td / "solution.json").write_text(json.dumps(payload))
            subprocess.run([sys.executable, str(judge),
                            "--solution", str(td / "solution.json"),
                            "--reward-json", str(td / "reward.json"),
                            "--reward-txt", str(td / "reward.txt")], check=True)
            return json.loads((td / "reward.json").read_text())["reward"]

        oracle = score({"ledger": gt["ledger"]})
        empty = score({"ledger": []})
    assert oracle == 1.0, f"verifier(oracle) == {oracle}, expected 1.0"
    assert empty == 0.0, f"verifier(empty) == {empty}, expected 0.0"
    print(f"self-check: oracle={oracle} empty={empty}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", required=True, type=Path)
    ap.add_argument("--t0-tick", type=int, default=None,
                    help="tick that maps to video t=0 (default: round_announce_match_start); "
                         "re-run with the measured value once the render exists")
    args = ap.parse_args()

    gt, label = build(args.dem, args.t0_tick)
    print(json.dumps(gt["meta"], indent=2))

    (HERE / "gt_ledger.json").write_text(json.dumps(gt, indent=2))
    (HERE / "player_map.json").write_text(json.dumps(label, indent=2))  # PRIVATE
    (TASK / "steps/solve/tests/gt_ledger.json").write_text(json.dumps(gt, indent=2))
    (TASK / "steps/solve/solution/oracle_ledger.json").write_text(
        json.dumps({"ledger": gt["ledger"]}, indent=2))

    self_check(gt)


if __name__ == "__main__":
    main()
