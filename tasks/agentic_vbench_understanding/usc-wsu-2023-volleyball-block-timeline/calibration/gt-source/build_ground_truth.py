#!/usr/bin/env python3
"""Rebuild the 23-block ground truth from the archived play-by-play snapshot.

Input: pbp_rows_3252428.json — a canonical extract of stats.ncaa.org contest
3252428's five per-set rally tables (each row is the whitespace-normalized text of
the [visitor, score, home] cells; see the snapshot's meta block and README).

Derivation rules (all deterministic):
  * A row whose middle cell is "U-W" is a scoring row; comparing with the previous
    score tells which team scored (the score delta, never the cell side, decides).
  * A scoring row is a BLOCK POINT iff its rally text ends in "Block by <names>"
    AND an "Attack by <hitter>" occurs earlier in the same rally chain. Rows of the
    shape "Kill by X, Block by Y" (no Attack-chain) are attacker kills through a
    block touch — NOT block points — and are excluded; this exactly matches the
    official box score (Block Solos 3/3, Block Assists 14/20 -> team blocks 10/13).
  * blockers = the names after the LAST "Block by" (one or two, comma-separated);
    blocked = the hitter of the LAST "Attack by" before that block.
  * score_after is written USC-WSU (visitor-home), as on the broadcast graphic.

Run: python3 build_ground_truth.py [--judge path/to/judge.py]
Prints the rebuilt events with per-event source row indices and, when --judge is
given, asserts exact equality with judge.GROUND_TRUTH.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def clean(s):
    return re.sub(r"\s+", " ", s.replace("+", " ").replace("\x01", " ")).strip()


def rebuild(snapshot_path):
    data = json.loads(Path(snapshot_path).read_text())
    events = []
    for s in data["sets"]:
        set_no, prev_u, prev_w = s["set"], 0, 0
        for idx, row in enumerate(s["rows"]):
            cells = row + [""] * (3 - len(row))
            score = cells[1] or ""
            m = re.match(r"^(\d+)-(\d+)$", score)
            if not m:
                continue
            u, w = int(m.group(1)), int(m.group(2))
            txt = clean((cells[0] or "") + " || " + (cells[2] or ""))
            # terminal block: last "Block by", with an "Attack by" earlier in the chain
            bidx = txt.lower().rfind("block by")
            if bidx != -1:
                before = txt[:bidx]
                attacks = re.findall(
                    r"Attack by ([A-Za-z' .-]+?)(?:,|\|\||$| Block| Dig| Set| Kill)", before)
                if attacks:
                    seg = txt[bidx + len("block by"):].split("||")[0]
                    blockers = [p.strip() for p in re.split(r",| and ", seg)
                                if p.strip() and re.match(r"^[A-Za-z' .-]+$", p.strip())]
                    events.append({
                        "set": set_no,
                        "score_after": f"{u}-{w}",
                        "type": "block",
                        "players": blockers[:2],
                        "blocked": attacks[-1].strip(),
                        "_source_row": {"set": set_no, "row_index": idx},
                    })
            prev_u, prev_w = u, w
    return events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=str(HERE / "pbp_rows_3252428.json"))
    ap.add_argument("--judge", default=None,
                    help="path to judge.py; assert equality with its GROUND_TRUTH")
    args = ap.parse_args()

    events = rebuild(args.snapshot)
    print(f"rebuilt {len(events)} block points from the snapshot:")
    for e in events:
        src = e["_source_row"]
        print(f"  set{e['set']} {e['score_after']:>6}  blockers={e['players']}"
              f"  blocked={e['blocked']}  <- set table {src['set']}, row {src['row_index']}")

    if args.judge:
        sys.path.insert(0, str(Path(args.judge).resolve().parent))
        import judge  # noqa: E402
        stripped = [{k: v for k, v in e.items() if not k.startswith("_")} for e in events]
        assert stripped == judge.GROUND_TRUTH, "rebuilt events != judge.GROUND_TRUTH"
        print(f"\nOK: rebuilt events exactly match judge.GROUND_TRUTH ({len(stripped)}/23)")


if __name__ == "__main__":
    main()
