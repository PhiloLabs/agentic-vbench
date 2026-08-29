#!/usr/bin/env python3
"""Emit instruction.md, task.toml and the oracle solve.sh from the derived key.

    python3 provenance/make_task_files.py --derived provenance/step-derived.json \
        --media provenance/media_manifest.json --root .

Everything the agent reads about the corpus (how many videos, how long each one is, the
closed vocabulary) and everything the harness reads about it (the storage estimate, the
per-video listing) is a function of the key, so it is generated rather than typed. A
prompt that says twenty-one videos when the image holds twenty-two is the failure this
removes.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

PROMPT = """# Egocentric Recipe-Step Transcripts Across {n} Recordings

You are given {word} videos in `/workspace/materials/`. Each is a single continuous
recording from a camera worn on the head of one person preparing one dish from
start to finish, in a real kitchen. The clips have no audio track. They were
recorded by different people in different kitchens, and **several of them are the
same dish prepared by different people**, so recognising the dish does not tell
you what happened in a particular clip. Part of the work is deciding, from what
you see, which dish each recording is and which of its steps this person actually
carried out. Time `t` is seconds from the start of whichever clip an entry refers
to.

{table}

For **each** of the {word} videos, reconstruct the **complete chronological transcript
of the recipe steps that person actually performed in that recording**, and when
each one started and ended.

Nobody here follows the recipe cleanly. Steps are performed out of order, some are
performed incorrectly, and some are skipped entirely. Report each recording as it
happened, not as the recipe says it should go. A step the person never performed is
not an entry, however clearly the recipe calls for it. A step performed twice is two
entries. A step performed out of the usual order belongs where it actually happened.

Use any tools in the image, for example `ffmpeg` and `ffprobe`, to seek through and
sample the videos.

## What to submit

Write `/workspace/output/solution.json` in exactly this shape:

```json
{{
  "sequence": [
    {ex0},
    {ex1},
    {ex2}
  ]
}}
```

One entry per step performed. Within each video, order the entries by the moment
the step begins; if two steps begin at the same second, put the smaller `id` first.
The videos themselves may come in any order. Fields:

- `video`: one of `"A"` through `"{last}"`, the clip this entry belongs to.
- `id`: the step's label, an integer from the closed vocabulary below.
- `t_start`: the second at which that step begins, in that clip.
- `t_end`: the second at which that same step ends, in that clip.

An entry counts only if it names the right video and **both** of its boundaries
land inside the tolerance of the true step. That tolerance is a quarter of the
step's duration, never tighter than {tmin:.0f} second and never looser than {tmax:.0f} seconds, and
the same tolerance applies to the start and to the end. Short steps are therefore
graded strictly at both ends, so watch each action begin and watch it stop.

## The closed vocabulary

One vocabulary covers all {word} videos, and it spans {n_act} different dishes, so most of
it belongs to dishes you will not see in any given clip. Use only these labels.
Several labels name similar actions on different ingredients, so pick the one that
names what the person actually handles.

{vocab}

## Rules

- Rewrite the complete `/workspace/output/solution.json` after every ten or so
  samples you take, not only at the end. Your run can end at any moment and only
  what is on disk counts, so an incomplete answer saved early beats a complete one
  you never got to write.
- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online, and do not rely on any memory of these recordings
  or of the dataset they may come from. Every answer must come from watching these
  videos.
- Use only labels from the vocabulary above.
- Report every step you find, in every video, including a step performed more than
  once.
"""

WORDS = {17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty",
         21: "twenty-one", 22: "twenty-two", 23: "twenty-three", 24: "twenty-four"}

SOLVE = '''#!/bin/bash
# Oracle: write the verified recipe-step transcripts as solution.json.
#
# The reference answer is a deterministic transform of CaptainCook4D's released step
# annotations for the {n} recordings (see ../../../provenance/build_gt.py): every
# annotated step that was actually performed, in chronological order, with its span.
# This is the verified answer key, not an echo of the input, and the agent never sees
# this file. The entries mirror judge.py's GROUND_TRUTH.
set -euo pipefail

mkdir -p /workspace/output

python3 - <<'{marker}'
import json
from pathlib import Path

SEQUENCE = [
{body}
]

Path("/workspace/output/solution.json").write_text(
    json.dumps({{"sequence": SEQUENCE}}, indent=1) + "\\n")
print(f"wrote {{len(SEQUENCE)}} entries")
{marker}
'''


def schema_examples(inst, letters):
    """Three JSON rows that show the schema and CANNOT be correct answers.

    An earlier version selected these straight out of `inst`, so the shipped prompt
    carried three exact ground-truth events. Submitting nothing but the prompt's own
    examples scored 3 true positives and 0.0189 without watching a frame. Each example
    here names a label that does not occur ANYWHERE in the video it is filed under, which
    makes a match impossible whatever the times are, and the assertion below refuses to
    write a prompt where that has stopped being true.
    """
    all_labels = sorted({e["id"] for v in inst.values() for e in v})
    out = []
    for L in (letters[0], letters[0], letters[-1]):
        used = {json.loads(o)["id"] for o in out if json.loads(o)["video"] == L}
        absent = [i for i in all_labels
                  if all(g["id"] != i for g in inst[L]) and i not in used]
        assert absent, f"every label occurs in {L}, so no impossible example exists"
        label = absent[(len(out) * 7) % len(absent)]
        t0 = 10.0 + 25.0 * len(out)
        out.append(json.dumps({"video": L, "id": label,
                               "t_start": round(t0, 3), "t_end": round(t0 + 12.0, 3)}))
    for o in out:
        e = json.loads(o)
        assert all(g["id"] != e["id"] for g in inst[e["video"]]), (
            f"schema example {o} names a label that DOES occur in {e['video']}, so the "
            f"prompt would be leaking an answer")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--derived", required=True, type=Path)
    ap.add_argument("--media", type=Path)
    ap.add_argument("--root", required=True, type=Path)
    args = ap.parse_args()
    d = json.loads(args.derived.read_text())
    vids, inst = d["videos"], d["instances"]
    n = len(vids)
    letters = [v["letter"] for v in vids]

    rows = ["| video | path | length | time range |", "|---|---|---|---|"]
    for v in vids:
        rows.append(f"| `{v['letter']}` | `/workspace/materials/{v['letter']}.mp4` | "
                    f"{v['duration_sec']/60:.1f} min | `t = 0` to `t = {v['duration_sec']:.1f}` |")
    first, last = letters[0], letters[-1]
    ex = schema_examples(inst, letters)
    prompt = PROMPT.format(
        n=n, word=WORDS.get(n, str(n)), table="\n".join(rows), last=last,
        ex0=ex[0], ex1=ex[1], ex2=ex[2],
        tmin=d["tolerance_rule"]["min_sec"], tmax=d["tolerance_rule"]["max_sec"],
        n_act=len({v["activity_id"] for v in vids}),
        vocab="\n".join(f"- `{k}` {d['vocabulary'][k]}"
                        for k in sorted(d["vocabulary"], key=int)))
    (args.root / "steps" / "solve" / "instruction.md").write_text(prompt)

    acts = Counter(v["activity_name"] for v in vids)
    listing = "\n".join(
        f"#   {v['letter']}  {v['recording_id']:<8} {v['activity_name']:<22} "
        f"{v['duration_sec']/60:5.1f} min" for v in vids)
    media = json.loads(args.media.read_text()) if args.media and args.media.exists() else {}
    baked_mb = sum(m["derivative_bytes"] for m in media.values()) / 2**20 if media else 0.0
    storage = int(max(8192, (round(baked_mb * 2.5 / 1024) + 8) * 1024))
    n_inst = sum(len(v) for v in inst.values())
    dishes = ", ".join(f"{c} {k}" for k, c in acts.most_common())
    toml = f"""version = "1.0"

[task]
name = "agentic-vbench/captaincook-recipe-step-transcripts"

[metadata]
difficulty = "hard"
category = "video-understanding"
tags = [
    "video-understanding",
    "egocentric",
    "multi-video",
    "procedural-activity",
    "step-recognition",
    "event-timeline",
    "agentic-vbench-understanding",
]
# {n} continuous head-mounted GoPro recordings, {d['total_duration_sec']/60:.1f} minutes in total, from the
# CaptainCook4D release (arXiv:2312.14556, Apache 2.0): every annotated recording of at
# least 10 minutes whose 4K stream was published and which clears the eligibility gate,
# in recording_id order, until the family's own 300-minute ceiling binds. Breakdown by
# dish: {dishes}.
# Ground truth: the release's step annotations, transformed mechanically by
# provenance/build_gt.py. The pool is reproduced, and the rule that produced it
# re-checked, by provenance/take_selection.py.
#
{listing}
source = "CaptainCook4D, {n} recordings, 4K GoPro streams downscaled to 1080p, see provenance/take_selection.py"

[environment]
build_timeout_sec = 10800.0
cpus = 4
memory_mb = 8192
# The {n} baked 1080p streams are {baked_mb/1024:.1f} GiB, and the bake is a stream copy of an
# already-transcoded file, so the source and the baked set are the same size. Measured
# after the media package was built, not guessed.
storage_mb = {storage}
# The recordings are baked at build time and the answer is not online: keep this false.
allow_internet = false

[[steps]]
name = "solve"

[steps.agent]
# {n_inst} steps across {d['total_duration_sec']/3600:.1f} hours of video, every span scored on both
# boundaries to within {d['tolerance_rule']['min_sec']:.0f} to {d['tolerance_rule']['max_sec']:.0f} seconds. A serious attempt samples each recording
# coarsely, then binary-searches the transitions it cares about, which is thousands of
# decodes. The measured calibration runs and their wall clock are in
# calibration/scores.md; this budget sits above the longest of them.
#
# This number is NOT a difficulty knob. If a future version wants to move it, say so in
# scores.md and say why.
timeout_sec = 21600.0

[steps.verifier]
timeout_sec = 900.0

# CANARY: agentic_vbench task - do not train on this file.
"""
    (args.root / "task.toml").write_text(toml)

    seq = [{"video": L, "id": i["id"], "t_start": i["t_start"], "t_end": i["t_end"]}
           for L in letters for i in inst[L]]
    body = "\n".join("  " + json.dumps(e) + "," for e in seq)
    p = args.root / "steps" / "solve" / "solution" / "solve.sh"
    p.write_text(SOLVE.format(n=n, body=body, marker="P" + "YEOF"))
    p.chmod(0o755)
    note = "" if media else ("  [media manifest absent: storage_mb is a placeholder, "
                             "rerun after the bake]")
    print(f"instruction.md {len(prompt.splitlines())} lines, task.toml, solve.sh "
          f"{len(seq)} entries{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
