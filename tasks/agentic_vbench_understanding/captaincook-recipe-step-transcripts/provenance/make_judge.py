#!/usr/bin/env python3
"""Emit steps/solve/tests/judge.py from the derived key.

    python3 provenance/make_judge.py --derived provenance/step-derived.json \
        --core provenance/_judge_core.py.part --out steps/solve/tests/judge.py

The shipped judge carries its own copy of the answer key so that grading needs nothing
but the stdlib and no network. Writing that copy by hand is how a judge and a key drift
apart, so it is generated here and `verify_key.py` re-derives it and compares.

The scoring code itself is not generated: it is the same file the Ego-Exo4D version of
this task ships, copied in verbatim from --core, so that the two tasks in this family are
graded by identical logic and a reader can diff them.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

HEAD = '''#!/usr/bin/env python3
"""Grade {n_videos} egocentric recipe-step transcripts. Pure Python stdlib, deterministic.

The agent watches {n_videos} continuous head-mounted GoPro recordings, {minutes:.0f} minutes of
video in total, and must return the transcript of each one: every recipe step as it
was actually performed in that recording, in order, with the span of each step.
{n_inst} steps across the {n_videos}, drawn from {n_act} different recipes.

A predicted step is a true positive only when it names the right video, its label
matches, and BOTH of its boundaries fall inside that step's own tolerance, under an
order-preserving one-to-one alignment within that video. Misses and false positives
both hurt, and the reward is the F1 over the totals.

Requiring the whole span is what makes this a transcript rather than a list of
timestamps.

The tolerance travels with the ground-truth step: a quarter of that step's annotated
duration, floored at {tau_min} s and capped at {tau_max} s, and the same tolerance applies to
both boundaries. Short steps are graded strictly and long ones leniently, and no step
is graded outside [{tau_min:.0f}, {tau_max:.0f}] seconds. The prompt states the same rule to the agent.

Why the metric is safe against guessing. The canonical order of a recipe is common
knowledge, and these {n_videos} recordings cover only {n_act} recipes, so an agent that recognised
the dish could try to recite it. It does not work, because these are not clean
executions: {n_err} of the {n_inst} steps are annotated by the dataset as performed with an
error, and the recordings depart from the order induced by the other recordings of the
same recipe {n_inv} times. Every step also needs a span, not just a name. Reciting the
canonical order of each recipe, derived from the other recordings of that recipe,
scores {b_canon} on the real key; {n_draws} random submissions average {b_rand_mean}
and the best of them reaches {b_rand_best}. Only watching what these particular people
did, in which order, and where, converts into score. All of it is reproduced by
../../../provenance/ablations/run_ablations.py.

Ground truth is a deterministic transform of the released CaptainCook4D step
annotations, produced by ../../../provenance/build_gt.py. The agent never sees this
file.
"""
import argparse
import json
from pathlib import Path

# Bound the alignment cost against a spam submission. Anything past this many
# entries is ignored; a submission that long is already far below the bar.
MAX_ENTRIES = 20000

'''


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--derived", required=True, type=Path)
    ap.add_argument("--core", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    d = json.loads(args.derived.read_text())
    b = d.get("baselines") or {}

    inst = d["instances"]
    n_inst = sum(len(v) for v in inst.values())
    head = HEAD.format(
        n_videos=len(inst), minutes=d["total_duration_sec"] / 60.0, n_inst=n_inst,
        n_act=len({v["activity_id"] for v in d["videos"]}),
        tau_min=d["tolerance_rule"]["min_sec"], tau_max=d["tolerance_rule"]["max_sec"],
        n_err=sum(e["n_error_steps"] for e in d["eligibility"].values()),
        n_inv=sum(e["n_order_inversions"] for e in d["eligibility"].values()),
        b_canon=b.get("canonical_recipe_prior", "TBD"),
        n_draws=b.get("n_random_draws", 400),
        b_rand_mean=b.get("random_mean", "TBD"), b_rand_best=b.get("random_best", "TBD"),
    )

    lines = [head, "VOCABULARY = {"]
    for k in sorted(d["vocabulary"], key=int):
        lines.append(f"    {int(k)}: {json.dumps(d['vocabulary'][k])},")
    lines.append("}\n")
    lines.append("# letter -> chronological ground truth, each with the tolerance for both bounds")
    lines.append("GROUND_TRUTH = {")
    for letter in sorted(inst):
        lines.append(f'    "{letter}": [')
        for i in inst[letter]:
            lines.append(f'        {{"id": {i["id"]}, "t_start": {i["t_start"]}, '
                         f'"t_end": {i["t_end"]}, "tau": {i["tau"]}}},')
        lines.append("    ],")
    lines.append("}\n\n")
    lines.append(args.core.read_text().rstrip() + "\n")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines))
    print(f"wrote {args.out} : {len(inst)} videos, {n_inst} instances, "
          f"{len(d['vocabulary'])} labels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
