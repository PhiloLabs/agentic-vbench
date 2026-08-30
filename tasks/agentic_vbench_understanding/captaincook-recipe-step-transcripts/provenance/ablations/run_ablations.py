#!/usr/bin/env python3
"""Score the submissions a lazy agent could produce without watching anything.

    python3 provenance/ablations/run_ablations.py

Every number the SPEC and the judge's docstring claim about guessing is produced here,
against the shipped judge and the shipped key, so a reviewer can rerun it rather than
take the claim. Three families are covered: the oracle and the empty submission, which
bound the metric; the recipe-order priors, which are what an agent that recognises the
dish would write down; and spam, which is the standard attack on an order-preserving
alignment.

The frequency spam is handed information a real attacker could not have, namely the
labels that actually occur most often in each specific recording. It is an upper bound
on any frequency-prior attack rather than a realistic strategy.
"""
from __future__ import annotations

import json
import random
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "steps" / "solve" / "tests"))
import judge  # noqa: E402

DERIVED = json.loads((ROOT / "provenance" / "step-derived.json").read_text())

# The judge carries its own copy of the key, so it can be a rebuild behind the derived
# file, and then every number below is measured against a corpus that is not the shipped
# one. That happened once during development and the numbers looked entirely plausible.
_want = {L: [(i["id"], i["t_start"], i["t_end"], i["tau"]) for i in v]
         for L, v in DERIVED["instances"].items()}
_have = {L: [(g["id"], g["t_start"], g["t_end"], g["tau"]) for g in v]
         for L, v in judge.GROUND_TRUTH.items()}
assert _want == _have, (
    "judge.py is not built from the current step-derived.json; run make_judge.py first")
assert {int(k): v for k, v in DERIVED["vocabulary"].items()} == judge.VOCABULARY, \
    "judge.py's vocabulary is not the current one; run make_judge.py first"
CANONICAL = {k: list(v) for k, v in DERIVED["canonical_order"].items()}
DURATIONS = {v["letter"]: v["duration_sec"] for v in DERIVED["videos"]}
MEDIAN_DUR = round(statistics.median(
    g["t_end"] - g["t_start"] for gt in judge.GROUND_TRUTH.values() for g in gt), 2)
RANDOM_DRAWS = 400
SEED = 20260827
# The jitter curve: an agent with perfect labels and perfect ordering whose boundaries
# carry Gaussian noise. It says where the family's 0.10 gate actually sits in seconds,
# which is the only reading of the gate that transfers to another corpus.
JITTER_SIGMAS = (1.0, 2.0, 3.0, 5.0, 8.0, 10.0, 15.0)
# 10 and 15 are here for SPEC open item 6: they bracket the timing precision an
# attacker reading the on-camera tablet could plausibly get from its scroll
# position, so the cost of that cue can be looked up rather than argued.
JITTER_DRAWS = 1000


def jitter_curve(guess_error: bool = False) -> list[tuple[float, float, float]]:
    """(sigma, mean F1, seed-to-seed spread) for perfect labels with noisy boundaries.

    Two versions are wanted now that an entry also has to say how the step was performed.
    With `guess_error=False` the hypothetical agent gets that field right, which isolates
    boundary noise. With `guess_error=True` it answers the key's largest single class
    every time, which is the best an agent that has not judged the performances can do,
    and that is the curve a shortcut has to be measured against.

    This is a Monte Carlo estimate and it is reported as one. An earlier draft printed
    these to four decimals, which claimed a precision the estimate does not have: at
    sigma = 3 s the mean moves by about 0.003 between disjoint blocks of 1000 draws. The
    spread is measured here, over five blocks, and printed beside every value so nobody
    reads the fourth digit as meaningful. The seed is pinned, so the numbers in the
    documents are reproducible even though they are not exact.
    """
    base = oracle()
    out = []
    for sigma in JITTER_SIGMAS:
        blocks = []
        for b in range(5):
            vals = []
            for k in range(JITTER_DRAWS):
                r = random.Random(SEED + b * 1_000_003 + k)
                sub = [{**e,
                        "t_start": max(0.0, e["t_start"] + r.gauss(0, sigma)),
                        "t_end": e["t_end"] + r.gauss(0, sigma),
                        **({"error": GUESS} if guess_error else {})} for e in base]
                vals.append(judge.grade(sub)["f1"])
            blocks.append(statistics.mean(vals))
        out.append((sigma, statistics.mean(blocks), max(blocks) - min(blocks)))
    return out


# The strongest value an unwatched submission can put in the error field: the key's
# largest single class. Named rather than inlined so the deterministic attacks below and
# the contract test agree about what "a guess" means.
GUESS = "none"


def oracle() -> list[dict]:
    return [{"video": letter, "id": g["id"], "t_start": g["t_start"], "t_end": g["t_end"],
             "error": g["error"][0]}
            for letter, gt in judge.GROUND_TRUTH.items() for g in gt]


def spread(order_for: dict[str, list[int]]) -> list[dict]:
    """Lay each video's label sequence out evenly across that video, the best a
    guesser can do with no idea when anything happens."""
    out = []
    for letter, seq in order_for.items():
        if not seq:
            continue
        step = DURATIONS[letter] / len(seq)
        for k, label in enumerate(seq):
            t0 = round((k + 0.5) * step, 2)
            out.append({"video": letter, "id": label, "t_start": t0,
                        "t_end": round(t0 + MEDIAN_DUR, 2), "error": GUESS})
    return out


def cyclic(labels_for: dict[str, list[int]], stride: float) -> list[dict]:
    """Repeat a label cycle across each video at a fixed stride. This is the shape of
    every spam attack on an order-preserving alignment: the alignment will happily pick
    a matching entry out of each cycle, so the only defense is that F1 charges for every
    entry that does not match."""
    out = []
    for letter, labels in labels_for.items():
        t = 0.0
        while t < DURATIONS[letter]:
            for label in labels:
                out.append({"video": letter, "id": label, "t_start": round(t, 2),
                            "t_end": round(t + MEDIAN_DUR, 2), "error": GUESS})
            t += stride
    return out


def frequent_labels(top: int) -> dict[str, list[int]]:
    out = {}
    for letter, gt in judge.GROUND_TRUTH.items():
        counts: dict[int, int] = {}
        for g in gt:
            counts[g["id"]] = counts.get(g["id"], 0) + 1
        order = CANONICAL[letter]
        ranked = sorted(order, key=lambda l: (-counts.get(l, 0), order.index(l)))
        out[letter] = ranked[:top]
    return out


def main() -> int:
    rng = random.Random(SEED)
    labels = sorted({g["id"] for gt in judge.GROUND_TRUTH.values() for g in gt})
    draws = []
    for _ in range(RANDOM_DRAWS):
        sub = []
        for letter, gt in judge.GROUND_TRUTH.items():
            for _ in range(len(gt)):
                t0 = round(rng.uniform(0, DURATIONS[letter]), 2)
                sub.append({"video": letter, "id": rng.choice(labels), "error": GUESS,
                            "t_start": t0,
                            "t_end": round(t0 + MEDIAN_DUR, 2)})
        sub.sort(key=lambda e: (e["video"], e["t_start"]))
        draws.append(judge.grade(sub)["f1"])

    occurring = {letter: [l for l in CANONICAL[letter]
                          if any(g["id"] == l for g in judge.GROUND_TRUTH[letter])]
                 for letter in judge.GROUND_TRUTH}
    packed = cyclic(CANONICAL, 0.5)[: judge.MAX_ENTRIES]
    # The oracle's own entries, every one filed under the next video instead of its own.
    # If this scored, the video field would be decorative and 22 recordings would be one
    # long recording with 22 chapters.
    order = sorted(judge.GROUND_TRUTH)
    nxt = {L: order[(i + 1) % len(order)] for i, L in enumerate(order)}
    shifted = [{**e, "video": nxt[e["video"]]} for e in oracle()]
    rows = [
        ("oracle, the key itself", judge.grade(oracle())["f1"]),
        ("empty submission", judge.grade([])["f1"]),
        ("canonical recipe prior, full activity order", judge.grade(spread(CANONICAL))["f1"]),
        ("canonical recipe prior, labels that occur only", judge.grade(spread(occurring))["f1"]),
        (f"random submission, mean of {RANDOM_DRAWS} draws",
         round(sum(draws) / len(draws), 4)),
        (f"random submission, best of {RANDOM_DRAWS} draws", round(max(draws), 4)),
        ("spam, canonical cycle at 0.5 s stride", judge.grade(cyclic(CANONICAL, 0.5))["f1"]),
        ("spam, canonical cycle at 2 s stride", judge.grade(cyclic(CANONICAL, 2.0))["f1"]),
        (f"spam, entry-cap pack of {judge.MAX_ENTRIES} at 0.5 s stride",
         judge.grade(packed)["f1"]),
        ("spam, top-5 per-recording labels at 2 s stride (upper bound)",
         judge.grade(cyclic(frequent_labels(5), 2.0))["f1"]),
        ("oracle answers filed under the wrong video", judge.grade(shifted)["f1"]),
    ]
    width = max(len(r[0]) for r in rows)
    for name, val in rows:
        print(f"  {name:<{width}}  {val}")

    out = {"oracle": rows[0][1], "empty": rows[1][1],
           "canonical_recipe_prior": rows[2][1],
           "canonical_recipe_prior_occurring_labels_only": rows[3][1],
           "n_random_draws": RANDOM_DRAWS,
           "random_mean": rows[4][1], "random_best": rows[5][1],
           "spam_best_of_four": round(max(r[1] for r in rows[6:10]), 4),
           "oracle_under_wrong_video": rows[10][1]}
    assert out["oracle"] == 1.0, "the judge does not return 1.0 on its own key"
    assert out["empty"] == 0.0
    # The judge's docstring quotes these numbers, so they are written back into the
    # derived key and make_judge.py reads them from there. Running the chain in order
    # (build_gt, make_judge, run_ablations, make_judge) is what keeps the prose in the
    # shipped judge equal to what this script measures.
    path = ROOT / "provenance" / "step-derived.json"
    d = json.loads(path.read_text())
    d["baselines"] = out
    path.write_text(json.dumps(d, indent=1, sort_keys=False) + "\n")
    print(f"\nwrote baselines into {path.name}")
    print(json.dumps(out, indent=1))

    if "--jitter" in sys.argv:
        print(f"\n  perfect labels and order, Gaussian boundary noise "
              f"({JITTER_DRAWS} draws x 5 blocks):")
        # not named `spread`: that is a module-level function, and binding it here
        # would make every earlier reference to it in this scope a local.
        for sigma, mean_f1, block_spread in jitter_curve():
            print(f"    sigma = {sigma:.0f} s   F1 = {mean_f1:.3f}   "
                  f"(spread across blocks {block_spread:.3f})")
        print(f"\n  same, but the error field answered {GUESS!r} every time, which is the "
              f"best\n  an agent that has not judged the performances can do:")
        for sigma, mean_f1, block_spread in jitter_curve(guess_error=True):
            print(f"    sigma = {sigma:.0f} s   F1 = {mean_f1:.3f}   "
                  f"(spread across blocks {block_spread:.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
