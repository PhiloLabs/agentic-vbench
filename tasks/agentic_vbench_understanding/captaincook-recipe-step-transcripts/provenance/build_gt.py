#!/usr/bin/env python3
"""Derive this task's answer key from the released CaptainCook4D step annotations.

    python3 provenance/build_gt.py --cc4d <dir from 01_download_annotations.sh> \
        --out provenance/step-derived.json

The key is a grounded transcript: for each selected recording, the chronological list of
recipe steps that were actually performed, each with a label out of a closed vocabulary
and a start and end time in seconds. Nothing here is authored. Every label, boundary and
activity name comes out of the released annotation files, and this script's job is to
select recordings under rules fixed in advance, drop the annotation rows that cannot
carry a ground truth, and refuse to emit a key if any of that goes wrong.

Three properties of the source cost real time to discover, so they are enforced here
rather than described in prose:

  1. A skipped step is annotated with start_time = end_time = -1. It did not happen, so
     it cannot appear in a transcript of what happened. 287 rows across 141 recordings
     look like this. Sorting them by start time would file them all before the first real
     step and hand the agent an unanswerable entry at t = -1.
  2. step_id is not a global label. Three ids are reused across activities for different
     steps, and step_idx_description.json stores only one text per id. The label is
     therefore (activity_id, step_id), and the text comes from the recording's own row.
  3. Even keyed that way, four activities annotate one (activity_id, step_id) with two
     different texts across recordings, which means the id does not identify the step
     within those activities either. Those activities are excluded whole.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

# ---- constants fixed before any recording was selected ------------------------------
# The first three carry over unchanged from the Ego-Exo4D version of this task, so they
# are not free parameters here. MIN_ERROR_STEPS replaces that version's
# MIN_REPEAT_INSTANCES at the same value; see SPEC.md for why the criterion changed and
# why the number did not.
# The release's own error taxonomy, from error_annotations.json. Eight tags plus the
# absence of one. This is not our vocabulary: it is read out of the annotations and
# asserted below to be exactly what the file contains, so it cannot drift.
ERROR_TAGS = ("Measurement Error", "Missing Step", "Order Error", "Other",
              "Preparation Error", "Technique Error", "Temperature Error",
              "Timing Error")
NO_ERROR = "none"

# What each tag means, for the prompt. The family requires task examples to be synthetic,
# so these are written here rather than quoted from the release: an example lifted from an
# annotator's own wording is a row of the source corpus reprinted in the prompt, even when
# the row belongs to a recording outside the selected corpus. They are set in a dish that
# CaptainCook4D does not contain, and build_gt asserts below that none of them reproduces
# any annotation the release ships.
SYNTHETIC_TAG_EXAMPLES = {
    "Measurement Error":  "two ladles of stock go into the pan where the recipe asks for one",
    "Missing Step":       "the barley is never rinsed and goes straight into the simmering pan",
    "Order Error":        "the stock is poured in before the lentils rather than after them",
    "Other":              "the pan boils over and its rim is wiped down partway through",
    "Preparation Error":  "a shallow frying pan stands in for the deep stockpot the recipe names",
    "Technique Error":    "the roux is beaten flat with a fork rather than folded with a spatula",
    "Temperature Error":  "the burner is left on its lowest setting when a high flame is called for",
    "Timing Error":       "the barley is left to simmer four minutes instead of the stated ten",
}

MIN_TAKE_SEC = 600.0            # the family's own floor for a single-video task
MIN_ORDER_INVERSIONS = 2
MIN_ERROR_STEPS = 3
ALPHA, TAU_MIN, TAU_MAX = 0.25, 1.0, 3.0
CORPUS_CAP_SEC = 300 * 60.0     # the family's own ceiling
SOURCE = ("CaptainCook4D step and error annotations (arXiv:2312.14556), released by the "
          "CaptainCook4D authors under the Apache License 2.0")


def load(cc4d: Path):
    ann = json.loads((cc4d / "complete_step_annotations.json").read_text())
    errs = {r["recording_id"]: r for r in
            json.loads((cc4d / "error_annotations.json").read_text())}
    dur = {r["recording_id"]: float(r["duration(sec)"])
           for r in csv.DictReader((cc4d / "video_information.csv").open())}
    links = json.loads((cc4d / "download_links.json").read_text())
    assert set(ann) == set(errs), "the two annotation files disagree on which recordings exist"
    return ann, errs, dur, links


def conflicted_activities(ann: dict) -> list[int]:
    """Activities where one (activity_id, step_id) carries more than one step text."""
    texts = defaultdict(set)
    for rec in ann.values():
        for s in rec["steps"]:
            texts[(rec["activity_id"], s["step_id"])].add(s["description"].strip())
    return sorted({key[0] for key, v in texts.items() if len(v) > 1})


def usable(step: dict) -> bool:
    """A row that can carry a ground truth: it happened, and it has a positive span."""
    return (step["start_time"] >= 0.0 and step["end_time"] >= 0.0
            and step["end_time"] > step["start_time"])


def error_tags(err_rec: dict) -> dict:
    """(step_id, start_time) -> the tags the release annotates for that step.

    The two files are separate and are joined on the pair, not on step_id alone: step_id
    repeats within a recording when a step is performed twice. The join is asserted to be
    total by the caller rather than assumed, because a silent miss here would read as
    'this step was performed correctly'.
    """
    return {(s["step_id"], round(float(s["start_time"]), 3)):
            sorted({e["tag"] for e in (s.get("errors") or [])})
            for s in err_rec.get("step_annotations", [])}


def performed(rec: dict) -> list[dict]:
    """The steps that actually happened, chronological, labelled by their own text.

    No error tags here: this is what canonical_order needs, and threading the error file
    through it would only create a second place for that join to go wrong.
    """
    out = [{"id": s["description"].strip(), "text": s["description"].strip(),
            "t_start": round(float(s["start_time"]), 3),
            "t_end": round(float(s["end_time"]), 3),
            "has_errors": bool(s.get("has_errors"))}
           for s in rec["steps"] if usable(s)]
    out.sort(key=lambda i: (i["t_start"], i["t_end"]))
    return out


def transcript(rec: dict, err_rec: dict) -> list[dict]:
    """One recording's performed steps in chronological order.

    The label is the step's own text, not its id. Two reasons, both measured. step_id is
    not unique across dishes, so it cannot be the label; and (activity_id, step_id) is
    unique but two of those keys carry byte-identical text, which would ask the agent to
    choose between two labels that read the same while the prompt withholds which dish
    the clip is. Keying on the text makes that choice not exist.
    """
    tags_of = error_tags(err_rec)
    out = []
    for s in rec["steps"]:
        if not usable(s):
            continue
        key = (s["step_id"], round(float(s["start_time"]), 3))
        assert key in tags_of, (
            f"{rec['recording_id']} step {key} has no row in error_annotations.json; a "
            f"missing join would silently read as 'performed correctly'")
        tags = tags_of[key]
        assert bool(tags) == bool(s.get("has_errors")), (
            f"{rec['recording_id']} step {key}: has_errors={s.get('has_errors')} but "
            f"error_annotations says {tags}")
        out.append({"id": s["description"].strip(),
                    "text": s["description"].strip(),
                    "t_start": round(float(s["start_time"]), 3),
                    "t_end": round(float(s["end_time"]), 3),
                    "has_errors": bool(s.get("has_errors")),
                    "error": tags or [NO_ERROR]})
    # `id` is still the step TEXT here; the integer label is assigned later, once the
    # vocabulary is numbered. The canonical (t_start, label) sort therefore happens at
    # emit time, not here.
    out.sort(key=lambda i: (i["t_start"], i["t_end"]))
    return out


def canonical_order(ann: dict, activity_id: int, held_out: str) -> list[tuple]:
    """Order an activity's labels by their median normalized first onset across every
    OTHER recording of that activity, with the scored recording left out. This is the
    strongest recipe-order prior an agent could build from the rest of the dataset."""
    pos, support = defaultdict(list), Counter()
    for rid, rec in ann.items():
        if rec["activity_id"] != activity_id or rid == held_out:
            continue
        inst = performed(rec)
        if not inst:
            continue
        span = max(i["t_end"] for i in inst) or 1.0
        seen = set()
        for i in inst:
            if i["id"] in seen:
                continue
            seen.add(i["id"])
            pos[i["id"]].append(i["t_start"] / span)
        support.update(seen)
    return sorted(pos, key=lambda l: (statistics.median(pos[l]), -support[l], l))


def eligibility(inst: list[dict], canon: list[tuple]) -> dict:
    ids = [i["id"] for i in inst]
    rank = {l: r for r, l in enumerate(canon)}
    ranks = [rank.get(i) for i in ids]
    inversions = sum(1 for a, b in zip(ranks, ranks[1:])
                     if a is not None and b is not None and b < a)
    n_err = sum(i["has_errors"] for i in inst)
    return {"n_instances": len(ids), "n_distinct_labels": len(set(ids)),
            "n_error_steps": n_err, "n_order_inversions": inversions,
            "eligible": n_err >= MIN_ERROR_STEPS and inversions >= MIN_ORDER_INVERSIONS}


def rid_key(rid: str) -> tuple[int, int]:
    a, b = rid.split("_")
    return int(a), int(b)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cc4d", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    ann, errs, dur, links = load(args.cc4d)

    # The per-step has_errors flag is what the eligibility gate reads, so check it
    # against the separate per-recording file before trusting it.
    disagree = [rid for rid, rec in ann.items()
                if bool(errs[rid]["is_error"]) != any(s.get("has_errors") for s in rec["steps"])]
    assert not disagree, f"has_errors disagrees with error_annotations on {disagree[:5]}"

    # ERROR_TAGS is written down above so the prompt and the judge can share it, which
    # makes it a place where our copy could drift from the release. Check it rather than
    # trust it: the set in the file must be exactly the set in the constant.
    seen_tags = {e["tag"] for rec in errs.values()
                 for s in rec.get("step_annotations", []) for e in (s.get("errors") or [])}
    assert seen_tags == set(ERROR_TAGS), (
        f"the release's error taxonomy is not what ERROR_TAGS says\n"
        f"  only in the file:     {sorted(seen_tags - set(ERROR_TAGS))}\n"
        f"  only in the constant: {sorted(set(ERROR_TAGS) - seen_tags)}")

    excluded = conflicted_activities(ann)
    dropped = sum(1 for rec in ann.values() for s in rec["steps"] if not usable(s))

    rows, no_media = [], []
    for rid, rec in sorted(ann.items(), key=lambda kv: rid_key(kv[0])):
        if rec["activity_id"] in excluded:                      # R2
            continue
        # R2b. 21 of the 384 recordings are annotated but their 4K stream was never
        # published. A recording with no media cannot be shown to an agent, so this is a
        # property of the release rather than a threshold, but it is counted and printed
        # rather than filtered silently.
        if "gopro_4k" not in links.get(rid, {}):
            no_media.append(rid)
            continue
        if rid not in dur or dur[rid] < MIN_TAKE_SEC:           # R1
            continue
        inst = transcript(rec, errs[rid])
        canon = canonical_order(ann, rec["activity_id"], rid)
        elig = eligibility(inst, canon)
        if not elig["eligible"]:                                # R3
            continue
        rows.append({"rid": rid, "rec": rec, "inst": inst, "canon": canon, "elig": elig,
                     "dur": dur[rid]})

    # R4: ascending recording_id, stop as soon as the next one would pass the ceiling.
    # break rather than continue: skipping a recording that does not fit and carrying on
    # with smaller ones would bias the corpus toward short recordings, which is a knob.
    sel, total = [], 0.0
    for r in rows:
        if total + r["dur"] > CORPUS_CAP_SEC:
            break
        sel.append(r)
        total += r["dur"]
    assert sel, "no recording survived the gate"

    # R5: present in that same ascending order, which is arbitrary with respect to
    # everything the task scores.
    letters = [chr(65 + i) for i in range(len(sel))]
    assert len(sel) <= 26, "more recordings than single-letter names"

    # Numbered in alphabetical order of the text, which interleaves the dishes. Numbering
    # them in (activity_id, step_id) order would block the vocabulary by dish and hand the
    # agent the grouping the prompt deliberately withholds.
    vocab_keys = sorted({i["id"] for r in sel for i in r["inst"]})
    label_of = {k: n + 1 for n, k in enumerate(vocab_keys)}
    text_of = {label_of[k]: k for k in vocab_keys}
    assert len(set(text_of.values())) == len(text_of), "two labels share a text"

    out = {
        "videos": [], "total_duration_sec": round(total, 3), "source": SOURCE,
        "vocabulary": {str(v): text_of[v] for v in sorted(text_of)},
        "tolerance_rule": {"alpha": ALPHA, "min_sec": TAU_MIN, "max_sec": TAU_MAX,
                           "applies_to": ["t_start", "t_end"]},
        "error_tags": [NO_ERROR, *ERROR_TAGS],
        "error_tag_examples": {},
        "eligibility": {}, "canonical_order": {}, "instances": {},
        "excluded_activities": excluded,
        "dropped_unperformed_steps": dropped,
    }
    for letter, r in zip(letters, sel):
        rec = r["rec"]
        out["videos"].append({
            "letter": letter, "recording_id": r["rid"], "activity_id": rec["activity_id"],
            "activity_name": rec["activity_name"], "person_id": rec["person_id"],
            "environment": rec["environment"], "duration_sec": round(r["dur"], 3),
            "source_url": links[r["rid"]]["gopro_4k"],
        })
        out["eligibility"][letter] = r["elig"]
        out["canonical_order"][letter] = [label_of[k] for k in r["canon"] if k in label_of]
        # Canonical order: by onset, ties broken by the integer label. The judge's
        # alignment is order-preserving, so any order chosen here among steps that share
        # an onset would become a hidden requirement on the agent. U has one such pair,
        # both starting at 455.647, and submitting them the other way round dropped a
        # perfect oracle to 0.9968. The prompt now states this rule and the judge applies
        # it to submissions, so the two sides agree by construction.
        out["instances"][letter] = sorted(
            ({"id": label_of[i["id"]], "t_start": i["t_start"], "t_end": i["t_end"],
              "tau": round(min(TAU_MAX, max(TAU_MIN, ALPHA * (i["t_end"] - i["t_start"]))), 3),
              "error": i["error"]}
             for i in r["inst"]),
            key=lambda e: (e["t_start"], e["id"]))

    # The prompt has to say what the eight tags mean or the field is a guessing game. The
    # examples are written by hand, not quoted from the release, and the guarantee that
    # they cannot reproduce an annotation is asserted here rather than intended: no
    # example may contain, or be contained by, any description the release ships, and none
    # may share a four-word run with one. The comparison is against EVERY recording, not
    # only the 22 in the corpus.
    assert set(SYNTHETIC_TAG_EXAMPLES) == set(ERROR_TAGS), \
        f"no synthetic example for {sorted(set(ERROR_TAGS) - set(SYNTHETIC_TAG_EXAMPLES))}"

    def words(t: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", t.lower())

    def shingles(t: str, k: int = 4) -> set:
        w = words(t)
        return {tuple(w[i:i + k]) for i in range(len(w) - k + 1)}

    released = []
    for rec in errs.values():
        for st in rec.get("step_annotations", []):
            if st.get("description"):
                released.append(st["description"])
            for e in (st.get("errors") or []):
                if e.get("description"):
                    released.append(e["description"])
    assert released, "read no descriptions out of error_annotations.json to compare against"
    released_norm = [" ".join(words(d)) for d in released]
    released_shingles = set().union(*(shingles(d) for d in released))

    for tag, ex in SYNTHETIC_TAG_EXAMPLES.items():
        n = " ".join(words(ex))
        assert n, f"{tag}: the example is empty"
        hit = next((d for d in released_norm if n in d or d in n), None)
        assert hit is None, f"{tag}: the example reproduces a released description: {hit!r}"
        shared = shingles(ex) & released_shingles
        assert not shared, (
            f"{tag}: the example shares a four-word run with a released description: "
            f"{sorted(' '.join(x) for x in shared)}")
    print(f"  examples: {len(SYNTHETIC_TAG_EXAMPLES)} synthetic, checked against "
          f"{len(released)} released descriptions for reuse and shared 4-grams")
    out["error_tag_examples"] = {t: [SYNTHETIC_TAG_EXAMPLES[t]] for t in ERROR_TAGS}

    # ---- refuse to emit a key that cannot be answered ----
    for letter, inst in out["instances"].items():
        d = dict(zip(letters, sel))[letter]["dur"]
        assert inst, f"{letter} has no instances"
        assert all(0 <= i["t_start"] < i["t_end"] <= d + 1.0 for i in inst), \
            f"{letter} has an instance outside its video"
        assert inst == sorted(inst, key=lambda i: (i["t_start"], i["t_end"])), \
            f"{letter} is not chronological"
        for i in inst:
            assert i["error"], f"{letter} has an instance with no error field"
            assert all(t == NO_ERROR or t in ERROR_TAGS for t in i["error"]), \
                f"{letter} has an instance tagged {i['error']}, which is not in the taxonomy"
            assert (NO_ERROR in i["error"]) == (len(i["error"]) == 1 and i["error"][0] == NO_ERROR), \
                f"{letter} mixes 'none' with a real tag: {i['error']}"
    args.out.write_text(json.dumps(out, indent=1, sort_keys=False) + "\n")

    n = sum(len(v) for v in out["instances"].values())
    sizes = sorted((len(v) for v in out["instances"].values()), reverse=True)
    taus = [i["tau"] for v in out["instances"].values() for i in v]
    print(f"excluded activities (step text is not a function of step_id): {excluded}")
    print(f"unperformed steps dropped corpus-wide (start = end = -1): {dropped}")
    print(f"annotated but never published at 4K, so unusable: {len(no_media)}")
    print(f"eligible pool {len(rows)} recordings, selected {len(sel)}")
    print(f"{len(sel)} recordings  {total/60:.1f} min  {n} instances  "
          f"{len(vocab_keys)} labels  {len({r['rec']['activity_id'] for r in sel})} activities")
    print(f"median tau {statistics.median(taus):.2f}  at the {TAU_MIN} floor "
          f"{100*sum(t <= TAU_MIN for t in taus)/len(taus):.0f}%  at the {TAU_MAX} cap "
          f"{100*sum(t >= TAU_MAX for t in taus)/len(taus):.0f}%")
    print(f"largest five recordings hold {100*sum(sizes[:5])/n:.1f}% of the key")
    for letter, r in zip(letters, sel):
        e = r["elig"]
        print(f"  {letter} {r['rid']:<7} {r['dur']/60:5.1f}m {e['n_instances']:3d} steps  "
              f"errors {e['n_error_steps']:2d}  inversions {e['n_order_inversions']:2d}  "
              f"{r['rec']['activity_name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
