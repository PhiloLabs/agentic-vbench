#!/usr/bin/env python3
"""Turn a SuperTuxKart profile-mode log into machine-exact race ground truth.

    parse_profile.py stk_stdout.log ground_truth.json [--expect N]

Columns are read from STK's own header line rather than positional guesswork:

  name start_position end_position time average_speed top_speed skid_time rescue_time
  rescue_count brake_count explosion_time explosion_count bonus_count banana_count
  small_nitro_count large_nitro_count bubblegum_count

(the data rows carry an extra AI-controller token, "Skidding", after the kart name, which is
dropped). An earlier hand-written regex silently mapped explosion_count to "items collected"
and bonus_count to "bananas hit" — plausible-looking numbers that were simply the wrong
columns, which is why parsing is now header-driven and asserted.

Only fields a viewer can verify from the video are exported: which kart started where, where
it finished, and the counts of things that visibly happen (rescues by the lift-back
animation, powerups collected, bananas hit, nitro picked up). `--expect N` asserts the field
size, because STK silently drops unknown kart names from --aiNP and backfills with a
duplicate kart, which would put two identical-looking karts on track.
"""
import json, re, sys
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
expect = int(sys.argv[sys.argv.index("--expect") + 1]) if "--expect" in sys.argv else None

lines = src.read_text(errors="replace").splitlines()
ANSI = re.compile(r"\x1b\[[0-9;]*m|\[[0-9;]+m")

def payload(line):
    if "profile: " not in line:
        return None
    return ANSI.sub("", line.split("profile: ", 1)[1]).strip()

header = None
for line in lines:
    p = payload(line)
    if p and p.startswith("name start_position"):
        header = p.split()
        break
if header is None:
    sys.exit("no profile header found — was --profile-laps used?")

KEEP = {"start_position": int, "end_position": int, "time": float, "top_speed": float,
        "rescue_count": int, "bonus_count": int, "banana_count": int,
        "explosion_count": int, "small_nitro_count": int, "large_nitro_count": int}

karts = []
for line in lines:
    p = payload(line)
    if p and p.startswith("min "):
        break              # end of the per-kart table; a second summary table follows in
                           # which the AI-controller name replaces the kart name
    if not p or p.startswith("name ") or p.startswith("-"):
        continue
    f = p.split()
    if len(f) < 3 or not f[0].replace("_", "").isalnum():
        continue
    if len(f) > 1 and not f[1].lstrip("-").replace(".", "").isdigit():
        f = [f[0]] + f[2:]            # drop the AI-controller token
    # rows carry one more column than the header (an untitled off-track counter)
    if len(f) < len(header) or not f[1].isdigit():
        continue
    row = dict(zip(header, f))
    try:
        k = {"kart": row["name"]}
        for col, cast in KEEP.items():
            k[col] = cast(row[col])
    except (KeyError, ValueError):
        continue
    k["nitro_collected"] = k.pop("small_nitro_count") + k.pop("large_nitro_count")
    k["items_collected"] = k.pop("bonus_count")
    k["times_exploded"] = k.pop("explosion_count")
    k["bananas_hit"] = k.pop("banana_count")
    k["finish_position"] = k.pop("end_position")
    karts.append(k)

if not karts:
    sys.exit("no kart rows parsed")
if expect is not None and len(karts) != expect:
    sys.exit(f"expected {expect} karts, parsed {len(karts)}")
names = [k["kart"] for k in karts]
dupes = sorted({n for n in names if names.count(n) > 1})
if dupes:
    sys.exit(f"duplicate karts on track: {dupes} — use exact kart ids in --aiNP")
finish = sorted(k["finish_position"] for k in karts)
if finish != list(range(1, len(karts) + 1)):
    sys.exit(f"finish positions are not a permutation: {finish}")
start = sorted(k["start_position"] for k in karts)
if start != list(range(1, len(karts) + 1)):
    sys.exit(f"start positions are not a permutation: {start}")

dst.write_text(json.dumps({"n_karts": len(karts), "karts": karts}, indent=2))
print(f"wrote {dst} — {len(karts)} karts")
for k in sorted(karts, key=lambda k: k["finish_position"]):
    print(f"  P{k['finish_position']}  {k['kart']:9s} (grid {k['start_position']})"
          f"  {k['time']:7.2f}s  items {k['items_collected']}  explosions {k['times_exploded']}"
          f"  nitro {k['nitro_collected']}  bananas {k['bananas_hit']}")
