#!/usr/bin/env python3
"""Build the answer key from the TenniSet annotation for V006 (2012 Olympic final).

Single source of truth: steps/solve/tests/annotation.json, the label file published
with the TenniSet dataset, alongside its schema in steps/solve/tests/classes.txt.
The file is a flat map of event tracks; this task scores one of them:

    Hit   {Player, Side, Type}   220 annotated swings
    Serve {Player, Result}       112 serves          } read for validation only,
    Game  {Server, Winner, Score} 13 games           } never scored (see transform 1)

Every event carries `start`/`end` frame numbers at the video's 25 fps, with the first
frame numbered 0. This script turns the Hit track into a chronological stroke ledger
and emits every derived artifact so the vocabulary the agent sees, the answer key, and
the oracle can never drift apart:

    steps/solve/tests/gt.json          answer key (verifier-side only)
    environment/vocabulary.json        closed label space, baked into the image
    steps/solve/solution/oracle.json   the oracle submission

The judge derives its own validation vocabulary from gt.json rather than reading a
second copy of this file, so there is exactly one vocabulary.json in the repo.

gt.json is NOT a verbatim copy of the published labels. Five transforms are applied
here and nowhere else, so this file is the only record of them. Each is explained at
its definition below:

1. live_hits()     9 Hit rows inside Fault/Let windows are excluded.
2. drop of Serve   serves are excluded from the scored ledger.
3. drop of `end`   only the `start` frame is scored.
4. STROKE_CLASS    Hit.Type is dropped; only Hit.Side survives.
5. sort_key()      chronological reordering with a deterministic tie-break.

It then runs structural and completeness cross-checks that the published labels have
to survive before the key is accepted, and finally runs the frozen judge over the
oracle and asserts reward == 1.0.
"""
import argparse
import bisect
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED_STROKES = 211
EXPECTED_SERVES = 112
EXPECTED_GAMES = 13
EXPECTED_EXCLUDED_HIT_FRAMES = (
    42918, 47955, 49327, 67765, 70297, 82623, 100428, 102106, 109149,
)

# Container scan of the published media: 123875 frames at 25.000 fps, 1280x720.
VIDEO_FRAMES = 123875
FPS = 25

PLAYERS = ("Sharapova", "Williams")

# TRANSFORM 4 of 5 — Hit.Type is dropped.
#
# The published Hit track carries a stroke Type alongside the Side: Topspin 189,
# Unsure 12, Slice 9, Flat 4, Smash 3, Volley 3. Two things make it unusable as a
# scored field. 86% of it is one value, so it carries almost no signal but would
# multiply the label space fivefold; and 12 strokes are labelled `Unsure`, which is
# the annotator recording that the footage does not settle the question — there is
# no answer for the agent to find. Side is decided by what the video plainly shows, so
# it is the only Hit attribute kept.
STROKE_CLASS = {"Forehand": "forehand", "Backhand": "backhand"}


def load_annotation(path):
    return json.loads(path.read_text())["classes"]


def frame(value):
    """13 of the published events carry a float frame number (e.g. 27954.0). They are
    all integral; anything else would be a new failure mode and is rejected."""
    number = int(value)
    if number != value:
        raise ValueError(f"non-integral frame number {value!r}")
    return number


def by_start(events):
    return sorted(events, key=lambda event: frame(event["start"]))


def live_hits(annotation):
    """TRANSFORM 1 of 5 — exclude Hit rows that annotate non-live serve swings.

    Nine rows in the published Hit track fall inside a Serve window whose Result is
    Fault or Let. They are the server's swing, not a rally stroke. Two happen to sit
    inside broad Point windows for double faults, so Point containment alone cannot
    identify them; the explicit cross-event overlap can.
    """
    non_live_serves = [
        serve for serve in annotation["Serve"]
        if serve["custom"]["Result"] != "In"
    ]
    retained = []
    excluded = []
    for hit in annotation["Hit"]:
        start = frame(hit["start"])
        overlaps = [
            serve for serve in non_live_serves
            if frame(serve["start"]) <= start <= frame(serve["end"])
        ]
        if len(overlaps) > 1:
            raise ValueError(f"Hit at {start} overlaps multiple non-live serves")
        (excluded if overlaps else retained).append(hit)

    excluded_frames = tuple(frame(hit["start"]) for hit in by_start(excluded))
    if excluded_frames != EXPECTED_EXCLUDED_HIT_FRAMES:
        raise ValueError(
            "unexpected Hit rows overlapping Fault/Let serves: "
            f"{excluded_frames!r}"
        )
    return retained, excluded


def build_strokes(hits):
    # TRANSFORM 2 of 5 — the 112 serves are excluded from the scored ledger.
    #
    # A serve is a stroke, and the published Serve track carries both the player and a
    # usable outcome (In 74 / Fault 36 / Let 2). It is left out anyway, because
    # Serve.start is not a repeatable physical instant and so cannot be scored against
    # a tight tolerance.
    #
    # The evidence is in the file itself. Measure the interval from Serve.start to the
    # start of the return it draws: median 55 frames but sd 15.9, spanning 22 to 95.
    # A serve's ball flight is near-constant, so essentially all of that spread is the
    # annotator choosing where the serve "begins" — sometimes as the tossing arm rises,
    # sometimes as the server is still walking to the baseline (frame 36045 is the
    # latter; frame 30700 is the former). The same spread shows in the window lengths:
    # sd 15.9, range 26 to 103.
    #
    # Compare the rally strokes: interval from one Hit.start to the next inside a rally
    # is median 31 with sd 6.6, and window length sd 6.8. Hit.start is a real event —
    # the take-back — placed consistently, and it survives a +/-10-frame tolerance.
    # Serve.start does not: with an annotator-side spread of +/-16 frames, even a
    # perfect viewer applying a fixed rule would land outside the tolerance on most
    # serves, so scoring them would charge the agent for guessing an annotator's habit.
    # Serves stay in annotation.json and are used by live_hits above; they are simply
    # not part of the answer.
    strokes = []
    for hit in hits:
        player = hit["custom"]["Player"]
        if player not in PLAYERS:
            raise ValueError(f"unknown player {player!r}")
        strokes.append(
            {
                "player": player,
                "stroke": STROKE_CLASS[hit["custom"]["Side"]],
                # TRANSFORM 3 of 5 — the published `end` frame is dropped.
                #
                # `start` is a crisp physical instant a viewer can find: the first frame
                # of the take-back, about 10 frames before the racquet strikes the ball.
                # Checked frame by frame against the video at both ends of the court.
                #
                # `end` is not an event of the stroke at all. A Hit window ends a median
                # of 3 frames before the OPPONENT's next window begins (min 1, max 20,
                # never overlapping), so it marks where the annotator handed the ball to
                # the next event. Scoring it would charge the agent for reproducing a
                # bookkeeping convention rather than for reading the match.
                "start_frame": frame(hit["start"]),
            }
        )
    return sorted(strokes, key=sort_key)


def sort_key(stroke):
    """TRANSFORM 5 of 5 — chronological reordering with a deterministic tie-break.

    The published Hit track is not in time order (its `name` sequence runs backwards in
    places), and the judge aligns predictions to the key with an order-preserving LCS,
    which is only meaningful if the key is in time order.

    No two strokes in this match share a start frame — the closest pair is 17 frames
    apart — so start_frame alone is already a total order today. player and stroke are
    appended as a backstop so that a future annotation revision introducing a tie cannot
    silently produce a different gt.json depending on input file order.
    """
    return (stroke["start_frame"], stroke["player"], stroke["stroke"])


def containing_index(events, start, kind):
    matches = [
        index for index, event in enumerate(events)
        if frame(event["start"]) <= start <= frame(event["end"])
    ]
    if len(matches) != 1:
        raise ValueError(f"frame {start} belongs to {len(matches)} {kind} intervals")
    return matches[0]


def check_point_structure(annotation, hits):
    """CROSS-CHECK 1 — retained hits form physical rallies inside points.

    Every retained hit must belong to exactly one Point. Within each non-empty point,
    the receiver strikes first and players alternate strictly thereafter.
    """
    points = by_start(annotation["Point"])
    games = by_start(annotation["Game"])
    rallies = {}
    for hit in by_start(hits):
        start = frame(hit["start"])
        point_index = containing_index(points, start, "Point")
        rallies.setdefault(point_index, []).append(hit["custom"]["Player"])

    for point_index, players in rallies.items():
        point_start = frame(points[point_index]["start"])
        game_index = containing_index(games, point_start, "Game")
        server = games[game_index]["custom"]["Server"]
        receiver = next(player for player in PLAYERS if player != server)
        if players[0] != receiver:
            raise ValueError(
                f"point {point_index} starts with {players[0]}, expected {receiver}"
            )
        for first, second in zip(players, players[1:]):
            if first == second:
                raise ValueError(
                    f"point {point_index} has {first} striking twice in a row"
                )
    return len(rallies)


def check_completeness(annotation, hits):
    """CROSS-CHECK 2 — sanity-check points with no retained rally stroke.

    Points with no retained rally stroke must all be shorter than the median point.
    This is a coarse annotation sanity check, not proof of exhaustive completeness.
    """
    points = by_start(annotation["Point"])
    hit_starts = [frame(hit["start"]) for hit in by_start(hits)]
    durations = sorted(frame(point["end"]) - frame(point["start"]) for point in points)
    median = durations[len(durations) // 2]

    longest = 0
    empty = 0
    for point in points:
        start, end = frame(point["start"]), frame(point["end"])
        index = bisect.bisect_left(hit_starts, start)
        if index < len(hit_starts) and hit_starts[index] <= end:
            continue
        empty += 1
        longest = max(longest, end - start)
    if longest >= median:
        raise ValueError(
            f"a point with no rally stroke lasts {longest} frames, at or above the "
            f"median point of {median}: a rally may be missing from the annotation"
        )
    return empty, longest, median


def check_scorability(strokes):
    if len(strokes) != EXPECTED_STROKES:
        raise ValueError(f"expected {EXPECTED_STROKES} strokes, built {len(strokes)}")
    for stroke in strokes:
        if not 0 <= stroke["start_frame"] < VIDEO_FRAMES:
            raise ValueError(f"stroke at {stroke['start_frame']} is outside the video")
    starts = [stroke["start_frame"] for stroke in strokes]
    if len(set(starts)) != len(starts):
        raise ValueError("two strokes share a start frame")

    tolerance = judge_tolerance()
    closest_pair = min(second - first for first, second in zip(starts, starts[1:]))
    if closest_pair <= tolerance:
        raise ValueError(
            f"two consecutive strokes are {closest_pair} frames apart, within the "
            f"{tolerance}-frame tolerance"
        )

    # The alignment the judge computes is only well defined if no two strokes of the
    # same class sit within the scored tolerance of each other. Assert it here rather
    # than trusting the frozen tolerance in judge.py.
    closest = None
    for index, stroke in enumerate(strokes):
        for other in strokes[index + 1:]:
            gap = other["start_frame"] - stroke["start_frame"]
            if (other["player"], other["stroke"]) != (stroke["player"], stroke["stroke"]):
                continue
            closest = gap if closest is None else min(closest, gap)
            break
    if closest is None or closest <= tolerance:
        raise ValueError(
            f"two strokes of the same class are {closest} frames apart, within the "
            f"{tolerance}-frame tolerance: the alignment would be ambiguous"
        )
    return closest_pair, closest


def judge_tolerance():
    namespace = {}
    source = JUDGE.read_text().split("def ", 1)[0]
    exec(compile(source, str(JUDGE), "exec"), namespace)  # noqa: S102 - our own file
    return namespace["TOLERANCE_FRAMES"]


def dump(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, sort_keys=False) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_oracle(oracle):
    with tempfile.TemporaryDirectory() as scratch:
        scratch = Path(scratch)
        reward_json = scratch / "reward.json"
        subprocess.run(
            [sys.executable, str(JUDGE), "--solution", str(oracle),
             "--reward-json", str(reward_json),
             "--reward-txt", str(scratch / "reward.txt")],
            check=True,
        )
        return json.loads(reward_json.read_text())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-dir", type=Path,
                        default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    tests = args.task_dir / "steps" / "solve" / "tests"
    global JUDGE
    JUDGE = tests / "judge.py"

    annotation = load_annotation(tests / "annotation.json")
    if len(annotation["Game"]) != EXPECTED_GAMES:
        raise ValueError(f"expected {EXPECTED_GAMES} games")
    if len(annotation["Serve"]) != EXPECTED_SERVES:
        raise ValueError(f"expected {EXPECTED_SERVES} serves")

    hits, excluded = live_hits(annotation)
    rallies = check_point_structure(annotation, hits)
    empty_points, longest_strokeless, median_point = check_completeness(annotation, hits)

    strokes = build_strokes(hits)
    closest_pair, closest_same_class = check_scorability(strokes)

    vocabulary = {
        "fps": FPS,
        "video_frames": VIDEO_FRAMES,
        "players": sorted({stroke["player"] for stroke in strokes}),
        "strokes": sorted({stroke["stroke"] for stroke in strokes}),
    }

    gt_sha = dump(tests / "gt.json", {"strokes": strokes})
    vocabulary_sha = dump(args.task_dir / "environment" / "vocabulary.json", vocabulary)

    oracle = args.task_dir / "steps" / "solve" / "solution" / "oracle.json"
    oracle_sha = dump(oracle, {"strokes": strokes})

    reward = verify_oracle(oracle)
    if reward["reward"] != 1.0:
        raise ValueError(f"oracle scored {reward['reward']}, expected 1.0")

    counts = {}
    for stroke in strokes:
        key = f"{stroke['player']}/{stroke['stroke']}"
        counts[key] = counts.get(key, 0) + 1

    print(json.dumps(
        {
            "strokes": len(strokes),
            "by_player_and_class": counts,
            "first_frame": strokes[0]["start_frame"],
            "last_frame": strokes[-1]["start_frame"],
            "frame_tolerance": judge_tolerance(),
            "checks": {
                "excluded_non_live_hits": len(excluded),
                "empty_points": empty_points,
                "rallies_with_strict_alternation": rallies,
                "longest_strokeless_point": longest_strokeless,
                "median_point_duration": median_point,
                "closest_consecutive_pair": closest_pair,
                "closest_same_class_pair": closest_same_class,
            },
            "gt_sha256": gt_sha,
            "vocabulary_sha256": vocabulary_sha,
            "oracle_sha256": oracle_sha,
            "oracle_reward": reward["reward"],
        },
        indent=2,
    ))


JUDGE = None

if __name__ == "__main__":
    main()
