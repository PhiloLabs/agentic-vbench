"""Aggregate per-pillar judge JSONs into a Harbor-compliant reward.json.

Harbor parses reward.json as `dict[str, float|int]` — flat only, no nested
dicts, no string values. The rich per-pillar breakdown is written to a
side artifact for forensics.
"""
import json
import sys
from pathlib import Path


def main():
    results_dir = Path(sys.argv[1])
    run_id = sys.argv[2]
    reward_path = Path(sys.argv[3])
    breakdown_path = Path(sys.argv[4]) if len(sys.argv) > 4 else None

    total = 0
    ceiling = 0
    pillars = {}
    for f in sorted(results_dir.glob(f"{run_id}_p*.json")):
        d = json.loads(f.read_text())
        pillars[f"p{d['pillar']}"] = {
            "total": d["pillar_total"],
            "max": d["pillar_max"],
        }
        total += d["pillar_total"]
        ceiling += d["pillar_max"]

    reward = max(0.0, min(1.0, total / ceiling)) if ceiling > 0 else 0.0

    # Flat reward.json — strict Harbor schema (float/int values only).
    flat = {"reward": reward, "raw": total, "ceiling": ceiling}
    for pname, pdata in pillars.items():
        flat[f"{pname}_total"] = pdata["total"]
        flat[f"{pname}_max"] = pdata["max"]
    reward_path.parent.mkdir(parents=True, exist_ok=True)
    reward_path.write_text(json.dumps(flat, indent=2))

    # Rich breakdown for humans / debugging.
    if breakdown_path is not None:
        breakdown_path.parent.mkdir(parents=True, exist_ok=True)
        breakdown_path.write_text(json.dumps({
            "reward": reward,
            "raw": total,
            "ceiling": ceiling,
            "pillars": pillars,
            "run_id": run_id,
        }, indent=2))

    print(json.dumps(flat, indent=2))


if __name__ == "__main__":
    main()
