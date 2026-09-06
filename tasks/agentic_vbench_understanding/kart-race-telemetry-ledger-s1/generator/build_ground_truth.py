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
import json, os, subprocess, sys
from pathlib import Path

suite = Path(sys.argv[1])
dst = Path(sys.argv[2])

FFPROBE = os.environ.get("FFPROBE", "/pkg/ffmpeg/4.2.2/bin/ffprobe")
def clip_duration(p):
    """Duration (s) of a race clip — used to tag each race with its window in the concatenated video."""
    try:
        return float(subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                                     "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip() or 0)
    except Exception:
        return 0.0

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
        # scored fields: items_collected, skid_time (spinouts is UNSCORED context; see steps/solve/tests/judge.py)
        "items_collected": row["items_collected"],
        "spinouts": row["bananas_hit"] + row["times_exploded"],   # banana + bomb hits look identical,
                                                                  # so their sum is kept as UNSCORED context (spinouts is not scored)
        # SCORED drift total, already in VIDEO seconds: the patched build integrates the real skid
        # state in WALL-CLOCK time, and the suite is captured by x11grab at a constant wall-clock
        # frame rate, so this needs NO game->video rescaling. The old per-race factor was not even
        # the right factor for this quantity: on hacienda the clip ran 1.224x longer than game time
        # while the drift's own wall/game ratio was 1.152, and across the suite the two disagree by
        # up to 0.241 (cocoa_temple 1.927 vs 1.686), so one factor mis-scaled what it meant to fix.
        "skid_time": round(row["actual_skid_wall"], 2),
        # context (unscored) - the three other drift readings, kept so the choice is auditable
        "skid_actual_game": round(row["actual_skid_time"], 2),
        "skid_input_game": round(row["skid_time"], 2),      # STK's stock stat: skid INPUT held
        "skid_showgfx_game": round(row["showgfx_skid_time"], 2),
        "_game_dur": round(max(k["time"] for k in gt["karts"]), 3),  # race length, GAME seconds
        # context (unscored): kept for reference / calibration
        "bananas_hit": row["bananas_hit"],
        "times_exploded": row["times_exploded"],
        "nitro_collected": row["nitro_collected"],
        "finish_position": row["finish_position"],
        "field_size": gt["n_karts"],
    })

# Tag each race with its window [t_start, t_end] in the concatenated video (seconds). The suite
# concatenates race0/race_raw.mp4, race1/..., in this order, so a race's start time is the running
# sum of the earlier clips' durations. The judge matches a predicted race to the GT race whose
# window contains the predicted time t (time-anchored, instead of positional).
_t = 0.0
for r, d in zip(races, race_dirs):
    cd = clip_duration(d / "race_raw.mp4")
    r["t_start"] = round(_t, 2)
    r["t_end"] = round(_t + cd, 2)
    _t += cd
    # No drift rescaling: skid_time already arrives in wall-clock (== video) seconds. The overall
    # render slowdown is still recorded per race for reference only.
    r["render_speed_factor"] = round((cd / r["_game_dur"]) if r["_game_dur"] else 1.0, 3)
    del r["_game_dur"]
    # Sanity: a drift total can never exceed the clip it happened in.
    if r["skid_time"] > cd:
        sys.exit(f"{r['track']}: skid_time {r['skid_time']}s exceeds clip duration {cd}s")

if len(hero_set) != 1:
    sys.exit(f"hero must be constant across the suite for a clean cross-race ranking, got {hero_set}")

# Every scored field must vary across races, or its rank target is degenerate and the oracle cannot
# reach 1.0. (The judge renormalises weights over the fields that do vary, but the suite should have
# spread in the scored fields.)
for field in ("items_collected", "skid_time"):   # scored dims (spinouts is unscored context now)
    if len({r[field] for r in races}) < 2:
        sys.exit(f"{field} has no spread across races ({[r[field] for r in races]}) — vary "
                 f"tracks/laps so the hero's values differ, else that dimension is degenerate")

dst.write_text(json.dumps({"hero": hero_set.pop(), "n_races": len(races), "races": races}, indent=2))
print(f"wrote {dst} — {len(races)} races, hero-scoped (scored: items_collected, skid_time; spinouts is context)")
for r in races:
    print(f"  {r['track']:22s} items {r['items_collected']:2d}  spinouts {r['spinouts']:2d}"
          f"  skid {r['skid_time']:6.1f}s  (P{r['finish_position']}/{r['field_size']})")
