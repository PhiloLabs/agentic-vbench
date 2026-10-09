#!/usr/bin/env python3
"""Build the ground truth for `soccer-restart-outcome-chains` MECHANICALLY from a
SoccerNet-v2 `Labels-v2.json`. No human annotation, no judgment calls: every field is a
deterministic transform of the published, multi-annotator labels.

    python3 provenance/build_gt.py --labels Labels-v2.json --alignment provenance/alignment.json \\
        --clip-duration-sec 6426.52 --out provenance/dortmund_leverkusen.labels-derived.json [--write-key]

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

The baked clip is the Bundesliga's own full-game upload of the match, a different
recording of the same broadcast than SoccerNet's half videos. Each half is placed on the
clip's timeline by one offset, measured from SoccerNet's public shot-change annotations by
provenance/align_halves.py:
    clip_t = half_offset[half] + position / 1000

Derivation (all mechanical):
  t      = the annotation's clip time (above)
  action = the annotation's label, one of judge.ACTIONS
  team   = the annotation's team, with "not applicable" written "none"
Only visibility == "visible" annotations enter the key. Ties break on (t, action, team).

--write-key writes the key literal into steps/solve/tests/judge.py and
steps/solve/solution/solve.sh. Without it the script asserts that both already hold exactly
this derivation. Either way it then proves four things: the key scores 1.0 and an empty
submission 0.0 under the shipped judge, the judge's greedy matcher equals brute force on
random cases, and the two examples in instruction.md match nothing in the key.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import random
import re
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # provenance/..
JUDGE = os.path.join(ROOT, "steps", "solve", "tests", "judge.py")
SOLVE = os.path.join(ROOT, "steps", "solve", "solution", "solve.sh")
PROMPT = os.path.join(ROOT, "steps", "solve", "instruction.md")
TEAMS = {"home": "home", "away": "away", "not applicable": "none"}


def _half_and_pos(ann: dict) -> tuple[int, float]:
    half = int(str(ann["gameTime"]).split("-")[0].strip())
    return half, float(ann["position"]) / 1000.0  # ms -> s within the half


def _load_judge():
    spec = importlib.util.spec_from_file_location("judge", JUDGE)
    judge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(judge)
    return judge


def build(labels_path: str, half_offsets: tuple[float, float],
          clip_duration_sec: float | None = None) -> dict:
    judge = _load_judge()
    with open(labels_path, "r", encoding="utf-8") as f:
        labels = json.load(f)
    anns = labels["annotations"]

    def clip_t(ann: dict) -> float:
        half, pos = _half_and_pos(ann)
        return half_offsets[half - 1] + pos

    # The two halves must not overlap on the clip, and every event must be on it.
    last_h1 = max(clip_t(a) for a in anns if _half_and_pos(a)[0] == 1)
    first_h2 = min(clip_t(a) for a in anns if _half_and_pos(a)[0] == 2)
    assert last_h1 < first_h2, f"half 1 runs into half 2 on the clip ({last_h1} >= {first_h2})"
    if clip_duration_sec is not None:
        span = [clip_t(a) for a in anns]
        assert min(span) >= 0.0 and max(span) <= clip_duration_sec, (
            f"annotations fall outside the clip: [{min(span)}, {max(span)}] vs {clip_duration_sec}")
    unknown = sorted({a["label"] for a in anns} - set(judge.ACTIONS))
    assert not unknown, f"labels the judge does not know: {unknown}"

    instances = []
    for a in anns:
        if a.get("visibility") != "visible":
            continue
        instances.append({"t": round(clip_t(a), 3), "action": a["label"], "team": TEAMS[a["team"]]})
    instances.sort(key=lambda x: (x["t"], x["action"], x["team"]))
    # The prompt tells the agent that only "Ball out of play" has no team. Hold the key to it.
    for x in instances:
        assert (x["team"] == "none") == (x["action"] == "Ball out of play"), (
            f"{x} breaks the prompt's rule that only Ball out of play has no team")

    return {
        "match_id": labels.get("UrlLocal", "unknown"),
        "half_offsets_sec": list(half_offsets),
        "clip_duration_sec": clip_duration_sec,
        "time_tolerance_sec": judge.TOL,
        "n_instances": len(instances),
        "per_action": dict(Counter(i["action"] for i in instances).most_common()),
        "source": "SoccerNet-v2 Labels-v2.json, every visible annotation (mechanical derivation, no hand labeling)",
        "instances": instances,
    }


def _literal(instances: list[dict]) -> str:
    return "\n".join(f'  {{"t": {i["t"]}, "action": {json.dumps(i["action"])}, "team": {json.dumps(i["team"])}}},'
                     for i in instances)


def write_key(instances: list[dict]) -> None:
    lit = _literal(instances)
    for path, name in ((JUDGE, "GROUND_TRUTH"), (SOLVE, "ACTIONS_KEY")):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        text, n = re.subn(rf"^{name} = \[\n.*?^\]\n", f"{name} = [\n{lit}\n]\n", text, flags=re.S | re.M)
        assert n == 1, f"{path} holds no single {name} literal to rewrite"
        if path == SOLVE:
            text, n = re.subn(r"\(\d+ actions\)", f"({len(instances)} actions)", text)
            assert n == 1, "solve.sh has no action count to rewrite"
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def _brute(p: list[float], g: list[float], tol: float) -> int:
    """Maximum bipartite matching by augmenting paths, for small lists."""
    owner = [-1] * len(g)

    def augment(i: int, seen: set) -> bool:
        for j in range(len(g)):
            if j not in seen and abs(p[i] - g[j]) <= tol:
                seen.add(j)
                if owner[j] < 0 or augment(owner[j], seen):
                    owner[j] = i
                    return True
        return False

    return sum(augment(i, set()) for i in range(len(p)))


def prove(gt: dict) -> None:
    judge = _load_judge()
    derived = [{"t": i["t"], "action": i["action"], "team": i["team"]} for i in gt["instances"]]
    assert derived == judge.GROUND_TRUTH, (
        "derived key != judge.py GROUND_TRUTH; run with --write-key to regenerate it")
    with open(SOLVE, encoding="utf-8") as f:
        m = re.search(r"^ACTIONS_KEY = \[\n(.*?)^\]\n", f.read(), re.S | re.M)
    assert m and json.loads("[" + m.group(1).rstrip().rstrip(",") + "]") == derived, (
        "solve.sh does not write the derived key")
    print(f"provenance: derived key == judge.py GROUND_TRUTH == solve.sh ({len(derived)} entries)")

    assert judge.score(derived)["f1"] == 1.0, "verifier(oracle) != 1.0"
    assert judge.score([])["f1"] == 0.0, "an empty submission does not score 0.0"
    print("provenance: verifier(oracle) == 1.0 and verifier(empty) == 0.0 CONFIRMED")

    rng = random.Random(11)
    for _ in range(3000):
        p = sorted(round(rng.uniform(0, 20), 1) for _ in range(rng.randint(0, 7)))
        g = sorted(round(rng.uniform(0, 20), 1) for _ in range(rng.randint(0, 7)))
        assert judge._matches(p, g) == _brute(p, g, judge.TOL), (p, g)
    print("provenance: the judge's greedy matcher equals brute force on 3000 random cases")

    with open(PROMPT, encoding="utf-8") as f:
        block = re.search(r"```json\n(.*?)\n```", f.read(), re.S)
    examples = json.loads(block.group(1))["sequence"]
    hits = judge.score(examples)["true_positives"]
    assert hits == 0, f"an example in instruction.md matches {hits} key entries"
    # Not matching is not enough: an example next to a real event still points at it.
    gap = min(abs(x["t"] - k["t"]) for x in examples for k in derived)
    assert gap >= 20, f"an example in instruction.md sits {gap:.1f} s from a key entry"
    print(f"provenance: the {len(examples)} examples in instruction.md match nothing and sit "
          f"at least {gap:.0f} s from every key entry")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the key mechanically from SoccerNet-v2 Labels-v2.json.")
    ap.add_argument("--labels", required=True, help="path to Labels-v2.json")
    ap.add_argument("--alignment", help="alignment.json from align_halves.py (supplies both half offsets)")
    ap.add_argument("--half1-offset-sec", type=float, help="clip time of SoccerNet half-1 position 0")
    ap.add_argument("--half2-offset-sec", type=float, help="clip time of SoccerNet half-2 position 0")
    ap.add_argument("--clip-duration-sec", type=float, default=None, help="assert every event lies on the clip")
    ap.add_argument("--out", required=True)
    ap.add_argument("--write-key", action="store_true",
                    help="write the derived key into judge.py and solve.sh before proving it")
    args = ap.parse_args(argv)

    if args.alignment:
        with open(args.alignment, encoding="utf-8") as f:
            halves = json.load(f)["halves"]
        offsets = (halves["1"]["offset_sec"], halves["2"]["offset_sec"])
    else:
        assert args.half1_offset_sec is not None and args.half2_offset_sec is not None, (
            "pass --alignment or both --half1-offset-sec and --half2-offset-sec")
        offsets = (args.half1_offset_sec, args.half2_offset_sec)

    gt = build(args.labels, offsets, args.clip_duration_sec)
    if args.write_key:
        write_key(gt["instances"])
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(gt, f, ensure_ascii=False, indent=2)
    print(f"wrote {args.out}: {gt['n_instances']} visible actions | half offsets {offsets}")
    print("per action:", gt["per_action"])
    prove(gt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
