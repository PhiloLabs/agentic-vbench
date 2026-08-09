#!/usr/bin/env python3
"""Assemble a hero-scoped race suite into the verifier ground truth.

    build_ground_truth.py SUITE_DIR ground_truth.json

SUITE_DIR holds race0/, race1/, ... each produced by run_race.sh: a per-race `gt.json`
(the full parsed profile table) and a `hero.txt` naming the camera-followed kart.

Only the HERO kart's counts are exported per race. The camera is a chase-cam locked to the
hero the entire race (run_race.sh passes `--kart=HERO`), so every scored quantity is on
screen by construction — this is the "scope the counts to what the camera sees" fix. The
rest of the field still races and is visible in the video, it is just not what is counted.

The final GT ranks races by the hero's counts (see judge.py), so what is stored per race is
the hero's row plus the track name and race order.
"""
import json, sys
from pathlib import Path

suite = Path(sys.argv[1])
dst = Path(sys.argv[2])

race_dirs = sorted([d for d in suite.iterdir() if d.is_dir() and d.name.startswith("race") and d.name[4:].isdigit()],
                   key=lambda d: int(d.name[4:]))
if not race_dirs:
    sys.exit(f"no race*/ dirs under {suite}")

hero_set, races = set(), []
for d in race_dirs:
    gt = json.loads((d / "gt.json").read_text())
    hero = (d / "hero.txt").read_text().strip()
    hero_set.add(hero)
    row = next((k for k in gt["karts"] if k["kart"] == hero), None)
    if row is None:
        sys.exit(f"{d}: hero '{hero}' not in parsed karts {[k['kart'] for k in gt['karts']]}")
    track = (d / "track.txt").read_text().strip() if (d / "track.txt").exists() else d.name
    races.append({
        "track": track,
        "hero": hero,
        "items_collected": row["items_collected"],
        "times_exploded": row["times_exploded"],
        "bananas_hit": row["bananas_hit"],
        "nitro_collected": row["nitro_collected"],
        "finish_position": row["finish_position"],
        "field_size": gt["n_karts"],
    })

if len(hero_set) != 1:
    sys.exit(f"hero must be constant across the suite for a clean cross-race ranking, got {hero_set}")

# The primary scored field (items) must vary across races, or the rank target is degenerate and
# the oracle cannot reach 1.0. Explosions may be flat (the judge renormalises around it).
item_vals = [r["items_collected"] for r in races]
if len(set(item_vals)) < 2:
    sys.exit(f"items_collected has no spread across races ({item_vals}) — vary tracks/laps so the "
             f"hero's pickups differ, else the cross-race ranking is degenerate")
if len(set(r["times_exploded"] for r in races)) < 2:
    print("NOTE: times_exploded is flat across races; judge will score items only (weights "
          "renormalise). Consider difficulty 3 / more races to get explosion spread.")

dst.write_text(json.dumps({"hero": hero_set.pop(), "n_races": len(races), "races": races}, indent=2))
print(f"wrote {dst} — {len(races)} races, hero-scoped")
for r in races:
    print(f"  {r['track']:22s} items {r['items_collected']:2d}  explosions {r['times_exploded']:2d}"
          f"  bananas {r['bananas_hit']:2d}  nitro {r['nitro_collected']:2d}  (P{r['finish_position']}/{r['field_size']})")
