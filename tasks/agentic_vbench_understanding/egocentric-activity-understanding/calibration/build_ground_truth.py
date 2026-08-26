#!/usr/bin/env python3
"""Build the answer key from the GTEA Gaze+ action annotation for Ahmad_American.

Single source of truth: steps/solve/tests/Ahmad_American.txt, the action-label file
published with the Georgia Tech Egocentric Activity Datasets (GTEA Gaze+). Each line is

    <verb><noun1,noun2,...> (start_frame-end_frame)

annotated at 24 Hz with the first frame numbered 0. This script parses it, sorts it
chronologically, and emits every derived artifact so the vocabulary the agent sees, the
answer key, and the oracle can never drift apart:

    steps/solve/tests/gt.json          answer key (verifier-side only)
    environment/vocabulary.json        closed label space, baked into the image
    steps/solve/solution/oracle.json   the oracle submission

The judge derives its own validation vocabulary from gt.json rather than reading a
second copy of this file, so there is exactly one vocabulary.json in the repo.

gt.json is NOT a verbatim copy of the published labels. Two transforms are applied here
and nowhere else, so this file is the only record of them:

1. NOUN_ALIASES folds `eggs` into `egg` (35 nouns instead of the published 36).
2. sort_key() reorders the file chronologically, breaking ties deterministically.

Both are explained at their definitions below. Anyone reading gt.json on its own cannot
recover either one, which is why this script and the published label file it reads must
stay in the repo together.

Finally it runs the frozen judge over the oracle and asserts reward == 1.0.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

LINE = re.compile(r"^<(?P<verb>[^>]+)><(?P<nouns>[^>]+)>\s*\((?P<start>\d+)-(?P<end>\d+)\)$")

EXPECTED_ACTIONS = 172
EXPECTED_VERBS = 15
EXPECTED_NOUNS = 35

# TRANSFORM 1 of 2 — noun aliasing.
#
# The published annotation spends two nouns on the same physical thing: `egg` for a
# whole egg in the shell, `eggs` for the cooking egg mass in the pan. Choosing between
# them is a judgement about cooking state, not about what is visible, so a correct
# reading of the video can still land on the wrong token. They are folded into one noun
# and the vocabulary drops from the published 36 to 35.
#
# egg_container (the carton), egg_mixture (beaten egg, pre-pan) and egg_shells (the
# discards) are deliberately NOT aliased: each is a distinct physical object, not a
# different state of the same one.
#
# Applied in parse_labels() AFTER the repeated-noun integrity check, because aliasing is
# the one thing that may legitimately collapse two published nouns within a single
# action. No published action names both `egg` and `eggs`, so today nothing collapses;
# the post-alias dedupe is there so that a future alias cannot silently emit a duplicate.
# 11 of the 172 actions carry `egg` after this step.
NOUN_ALIASES = {"eggs": "egg"}

# Matroska container scan of the published media: 25692 video frames at 24.000 fps.
VIDEO_FRAMES = 25692
FPS = 24


def parse_labels(path):
    actions = []
    for number, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        match = LINE.match(line)
        if match is None:
            raise ValueError(f"{path.name}:{number}: unparsable annotation {line!r}")
        nouns = [noun.strip() for noun in match.group("nouns").split(",") if noun.strip()]
        if not nouns:
            raise ValueError(f"{path.name}:{number}: no nouns")
        if len(set(nouns)) != len(nouns):
            raise ValueError(f"{path.name}:{number}: repeated noun")
        # Alias after the integrity check, then dedupe: aliasing is what may legitimately
        # collapse two published nouns onto one within a single action.
        nouns = {NOUN_ALIASES.get(noun, noun) for noun in nouns}
        start = int(match.group("start"))
        end = int(match.group("end"))
        if not 0 <= start < end < VIDEO_FRAMES:
            raise ValueError(f"{path.name}:{number}: frame span outside the video")
        actions.append(
            {
                "verb": match.group("verb").strip(),
                "nouns": sorted(nouns),
                "start_frame": start,
                "end_frame": end,
            }
        )
    return actions


def sort_key(action):
    """TRANSFORM 2 of 2 — chronological reordering with a deterministic tie-break.

    The published file is grouped by action class, not by time: line 1 is at frame 1042,
    line 2 at 3728, line 3 at 24212. Across its 46 verb blocks the start frame goes
    backwards 9 times.

    The judge aligns predictions to the key with an order-preserving LCS, which is only
    meaningful if the key is in time order, so the file is sorted here. (Submitting the
    oracle in reverse scores 0.0058 rather than 1.0 — the ordering is load-bearing, not
    cosmetic.)

    Sorting on start_frame alone is not enough. Two actions share frame 10150:

        take<orange_juice_container> (10150-10171)
        put<cup>                     (10150-10177)

    Their relative order would otherwise depend on the input file's line order, so a
    reordering of the source would silently produce a different gt.json. Adding
    end_frame, verb and nouns makes the sort total: no two actions in the key compare
    equal, and the build is byte-reproducible. end_frame alone resolves today's single
    tie; verb and nouns are the backstop for a future identical-span pair.
    """
    return (
        action["start_frame"],
        action["end_frame"],
        action["verb"],
        tuple(action["nouns"]),
    )


def build_vocabulary(actions):
    return {
        "fps": FPS,
        "verbs": sorted({action["verb"] for action in actions}),
        "nouns": sorted({noun for action in actions for noun in action["nouns"]}),
    }


def dump(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=False) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_oracle(judge, oracle):
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        reward_json = scratch / "reward.json"
        reward_txt = scratch / "reward.txt"
        subprocess.run(
            [
                sys.executable,
                str(judge),
                "--solution",
                str(oracle),
                "--reward-json",
                str(reward_json),
                "--reward-txt",
                str(reward_txt),
            ],
            check=True,
        )
        return json.loads(reward_json.read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    tests = args.task_dir / "steps" / "solve" / "tests"
    actions = sorted(parse_labels(tests / "Ahmad_American.txt"), key=sort_key)
    vocabulary = build_vocabulary(actions)

    if len(actions) != EXPECTED_ACTIONS:
        raise ValueError(f"expected {EXPECTED_ACTIONS} actions, parsed {len(actions)}")
    if len(vocabulary["verbs"]) != EXPECTED_VERBS:
        raise ValueError(f"expected {EXPECTED_VERBS} verbs, found {len(vocabulary['verbs'])}")
    if len(vocabulary["nouns"]) != EXPECTED_NOUNS:
        raise ValueError(f"expected {EXPECTED_NOUNS} nouns, found {len(vocabulary['nouns'])}")

    gt_sha = dump(tests / "gt.json", {"actions": actions})
    vocabulary_sha = dump(args.task_dir / "environment" / "vocabulary.json", vocabulary)

    oracle = args.task_dir / "steps" / "solve" / "solution" / "oracle.json"
    oracle_sha = dump(oracle, {"actions": actions})

    reward = verify_oracle(tests / "judge.py", oracle)
    if reward["reward"] != 1.0:
        raise ValueError(f"oracle scored {reward['reward']}, expected 1.0")

    print(json.dumps(
        {
            "actions": len(actions),
            "verbs": len(vocabulary["verbs"]),
            "nouns": len(vocabulary["nouns"]),
            "first_frame": actions[0]["start_frame"],
            "last_frame": actions[-1]["end_frame"],
            "gt_sha256": gt_sha,
            "vocabulary_sha256": vocabulary_sha,
            "oracle_sha256": oracle_sha,
            "oracle_reward": reward["reward"],
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
