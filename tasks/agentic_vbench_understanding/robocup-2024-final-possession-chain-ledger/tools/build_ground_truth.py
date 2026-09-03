#!/usr/bin/env python3
"""Build the scored possession-chain ledger from an official RoboCup SSL log."""

from __future__ import annotations

import argparse
import bisect
import gzip
import json
import math
import statistics
import struct
import sys
import types
from dataclasses import dataclass
from pathlib import Path


TASK_DIR = Path(__file__).resolve().parents[1]
PB_DIR = Path(__file__).resolve().parent / "pb"

# The upstream proto path is named "gc", which collides with Python's built-in gc
# module. Register a package pointing at the generated files before importing them.
gc_package = types.ModuleType("gc")
gc_package.__path__ = [str(PB_DIR / "gc")]
sys.modules["gc"] = gc_package
sys.path.insert(0, str(PB_DIR))

from gc import ssl_gc_referee_message_pb2 as referee_pb  # noqa: E402
from tracked import ssl_vision_wrapper_tracked_pb2 as tracker_pb  # noqa: E402


TRACKER_SOURCE = "TIGERs"
MATCH_TEAMS = {"TIGERs Mannheim", "ZJUNlict"}
TEAM_LABEL = {"TIGERs Mannheim": "white", "ZJUNlict": "black"}
ACTIVE_COMMANDS = {
    referee_pb.Referee.NORMAL_START,
    referee_pb.Referee.FORCE_START,
    referee_pb.Referee.DIRECT_FREE_YELLOW,
    referee_pb.Referee.DIRECT_FREE_BLUE,
}
SCORED_STAGES = {
    referee_pb.Referee.NORMAL_FIRST_HALF: 1,
    referee_pb.Referee.NORMAL_SECOND_HALF: 2,
}
KICK_CLUSTER_WINDOW_S = 0.25
PHYSICAL_KICK_MERGE_WINDOW_S = 0.10
PHYSICAL_KICK_MERGE_DISTANCE_M = 0.20
MIN_KICK_SPEED_MPS = 0.5
ZONE_BOUNDARY_M = 2.0
MIN_CHAIN_KICKS = 2


@dataclass(frozen=True)
class RefState:
    time_s: float
    stage: int
    command: int
    yellow_name: str
    blue_name: str
    yellow_score: int
    blue_score: int
    blue_goal_positive_x: bool | None


@dataclass(frozen=True)
class KickObservation:
    start_s: float
    raw_team: int
    robot_id: int
    x_m: float
    y_m: float
    speed_mps: float


@dataclass(frozen=True)
class Kick:
    time_s: float
    half: int
    play_segment: int
    team_name: str
    team_label: str
    robot_id: int
    x_m: float
    y_m: float
    speed_mps: float
    zone: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=TASK_DIR / "steps/solve/tests/ground_truth.json",
    )
    parser.add_argument(
        "--oracle",
        type=Path,
        default=TASK_DIR / "steps/solve/solution/solution.json",
    )
    parser.add_argument(
        "--audit",
        type=Path,
        default=TASK_DIR / "tools/ground_truth_audit.json",
    )
    return parser.parse_args()


def read_log(path: Path) -> tuple[list[RefState], list[KickObservation], list[tuple[float, str, int]]]:
    states: list[RefState] = []
    observations: list[KickObservation] = []
    score_changes: list[tuple[float, str, int]] = []
    last_state_key: tuple[object, ...] | None = None
    last_scores: dict[str, int] = {}

    with gzip.open(path, "rb") as stream:
        if stream.read(12) != b"SSL_LOG_FILE":
            raise ValueError("not an SSL_LOG_FILE")
        if struct.unpack(">i", stream.read(4))[0] != 1:
            raise ValueError("unsupported SSL log version")

        while header := stream.read(16):
            if len(header) != 16:
                raise EOFError("truncated message header")
            _log_timestamp_ns, message_type, size = struct.unpack(">qii", header)
            payload = stream.read(size)
            if len(payload) != size:
                raise EOFError("truncated message payload")

            if message_type == 3:
                message = referee_pb.Referee()
                message.ParseFromString(payload)
                blue_positive = (
                    message.blue_team_on_positive_half
                    if message.HasField("blue_team_on_positive_half")
                    else None
                )
                state = RefState(
                    time_s=message.packet_timestamp / 1_000_000,
                    stage=message.stage,
                    command=message.command,
                    yellow_name=message.yellow.name,
                    blue_name=message.blue.name,
                    yellow_score=message.yellow.score,
                    blue_score=message.blue.score,
                    blue_goal_positive_x=blue_positive,
                )
                state_key = (
                    state.stage,
                    state.command,
                    state.yellow_name,
                    state.blue_name,
                    state.yellow_score,
                    state.blue_score,
                    state.blue_goal_positive_x,
                )
                if state_key != last_state_key:
                    states.append(state)
                    last_state_key = state_key

                for name, score in (
                    (state.yellow_name, state.yellow_score),
                    (state.blue_name, state.blue_score),
                ):
                    if not name:
                        continue
                    previous = last_scores.get(name)
                    if previous is not None and score > previous:
                        score_changes.append((state.time_s, name, score))
                    last_scores[name] = score

            elif message_type == 5:
                message = tracker_pb.TrackerWrapperPacket()
                message.ParseFromString(payload)
                if (
                    message.source_name != TRACKER_SOURCE
                    or not message.HasField("tracked_frame")
                ):
                    continue
                frame = message.tracked_frame
                if not (
                    frame.HasField("kicked_ball")
                    and frame.kicked_ball.HasField("robot_id")
                ):
                    continue
                kicked = frame.kicked_ball
                robot = kicked.robot_id
                observations.append(
                    KickObservation(
                        start_s=kicked.start_timestamp,
                        raw_team=robot.team,
                        robot_id=robot.id,
                        x_m=kicked.pos.x,
                        y_m=kicked.pos.y,
                        speed_mps=math.hypot(kicked.vel.x, kicked.vel.y),
                    )
                )

    if not states or not observations:
        raise ValueError("log does not contain the expected referee and tracker streams")
    return states, observations, score_changes


def cluster_identity_observations(
    observations: list[KickObservation],
) -> list[list[KickObservation]]:
    clusters: list[list[KickObservation]] = []
    for observation in sorted(observations, key=lambda item: item.start_s):
        if (
            clusters
            and observation.raw_team == clusters[-1][-1].raw_team
            and observation.robot_id == clusters[-1][-1].robot_id
            and observation.start_s - clusters[-1][-1].start_s <= KICK_CLUSTER_WINDOW_S
        ):
            clusters[-1].append(observation)
        else:
            clusters.append([observation])
    return clusters


def cluster_center(cluster: list[KickObservation]) -> tuple[float, float, float]:
    return (
        statistics.median(item.start_s for item in cluster),
        statistics.median(item.x_m for item in cluster),
        statistics.median(item.y_m for item in cluster),
    )


def cluster_observations(observations: list[KickObservation]) -> list[list[KickObservation]]:
    """Collapse tracker identity jitter around one physical ball launch."""
    identity_clusters = cluster_identity_observations(observations)
    physical_groups: list[list[list[KickObservation]]] = []
    for cluster in identity_clusters:
        time_s, x_m, y_m = cluster_center(cluster)
        if physical_groups:
            previous = physical_groups[-1]
            same_launch = any(
                abs(time_s - other_time_s) <= PHYSICAL_KICK_MERGE_WINDOW_S
                and math.hypot(x_m - other_x_m, y_m - other_y_m)
                <= PHYSICAL_KICK_MERGE_DISTANCE_M
                for other_time_s, other_x_m, other_y_m in map(cluster_center, previous)
            )
            if same_launch:
                previous.append(cluster)
                continue
        physical_groups.append([cluster])

    # Persistence across tracker frames is the strongest available identity signal.
    return [max(group, key=len) for group in physical_groups]


def build_segments(states: list[RefState]) -> list[tuple[float, int | None, RefState]]:
    segments: list[tuple[float, int | None, RefState]] = []
    segment_id = 0
    was_active = False
    for state in states:
        active = state.stage in SCORED_STAGES and state.command in ACTIVE_COMMANDS
        if active and not was_active:
            segment_id += 1
        segments.append((state.time_s, segment_id if active else None, state))
        was_active = active
    return segments


def build_segment_end_times(states: list[RefState]) -> dict[int, float]:
    end_times: dict[int, float] = {}
    previous_segment: int | None = None
    for time_s, segment_id, _state in build_segments(states):
        if previous_segment is not None and segment_id != previous_segment:
            end_times[previous_segment] = time_s
        previous_segment = segment_id
    return end_times


def classify_zone(x_m: float, raw_team: int, blue_positive: bool) -> str:
    # blue_positive says the blue team's own goal is at +x. Teams attack away
    # from their own goal, so convert x into progress toward the opponent goal.
    if raw_team == 2:  # BLUE
        attack_sign = -1 if blue_positive else 1
    elif raw_team == 1:  # YELLOW
        attack_sign = 1 if blue_positive else -1
    else:
        raise ValueError(f"unknown raw team: {raw_team}")
    progress = attack_sign * x_m
    if progress < -ZONE_BOUNDARY_M:
        return "defensive"
    if progress > ZONE_BOUNDARY_M:
        return "attacking"
    return "middle"


def build_kicks(
    states: list[RefState], observations: list[KickObservation], first_goal_s: float
) -> tuple[list[Kick], int]:
    segments = build_segments(states)
    segment_times = [entry[0] for entry in segments]
    kicks: list[Kick] = []
    rejected = 0

    for cluster in cluster_observations(observations):
        start_s = statistics.median(item.start_s for item in cluster)
        representative = cluster[len(cluster) // 2]
        index = bisect.bisect_right(segment_times, start_s) - 1
        if index < 0 or segments[index][1] is None or start_s <= first_goal_s:
            rejected += 1
            continue
        _, segment_id, state = segments[index]
        assert segment_id is not None
        team_name = (
            state.yellow_name
            if representative.raw_team == 1
            else state.blue_name
            if representative.raw_team == 2
            else ""
        )
        speed = statistics.median(item.speed_mps for item in cluster)
        if team_name not in MATCH_TEAMS or speed < MIN_KICK_SPEED_MPS:
            rejected += 1
            continue
        if state.blue_goal_positive_x is None:
            raise ValueError("direction-of-play flag is missing")
        x_m = statistics.median(item.x_m for item in cluster)
        y_m = statistics.median(item.y_m for item in cluster)
        kicks.append(
            Kick(
                time_s=start_s,
                half=SCORED_STAGES[state.stage],
                play_segment=segment_id,
                team_name=team_name,
                team_label=TEAM_LABEL[team_name],
                robot_id=representative.robot_id,
                x_m=x_m,
                y_m=y_m,
                speed_mps=speed,
                zone=classify_zone(x_m, representative.raw_team, state.blue_goal_positive_x),
            )
        )
    return kicks, rejected


def compress_zones(kicks: list[Kick]) -> list[str]:
    zones: list[str] = []
    for kick in kicks:
        if not zones or zones[-1] != kick.zone:
            zones.append(kick.zone)
    return zones


def build_chains(
    kicks: list[Kick],
    score_changes: list[tuple[float, str, int]],
    segment_end_times: dict[int, float],
    epoch_s: float,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    raw_chains: list[dict[str, object]] = []
    for kick in kicks:
        if (
            raw_chains
            and raw_chains[-1]["play_segment"] == kick.play_segment
            and raw_chains[-1]["team"] == kick.team_label
        ):
            raw_chains[-1]["kicks"].append(kick)
        else:
            raw_chains.append(
                {
                    "play_segment": kick.play_segment,
                    "half": kick.half,
                    "team": kick.team_label,
                    "team_name": kick.team_name,
                    "kicks": [kick],
                }
            )

    for index, chain in enumerate(raw_chains):
        next_chain = raw_chains[index + 1] if index + 1 < len(raw_chains) else None
        if next_chain and next_chain["play_segment"] == chain["play_segment"]:
            chain["terminal"] = "turnover"
            continue
        chain_kicks = chain["kicks"]
        end_s = chain_kicks[-1].time_s
        segment_end_s = segment_end_times.get(chain["play_segment"], math.inf)
        scored = any(
            end_s - 1 <= time_s <= segment_end_s + 1 and name == chain["team_name"]
            for time_s, name, _score in score_changes
        )
        chain["terminal"] = "goal" if scored else "stoppage"

    scored_chains: list[dict[str, object]] = []
    audit_chains: list[dict[str, object]] = []
    for chain in raw_chains:
        chain_kicks = chain["kicks"]
        if len(chain_kicks) < MIN_CHAIN_KICKS:
            continue
        public = {
            "half": chain["half"],
            "team": chain["team"],
            "kick_count": len(chain_kicks),
            "zone_path": compress_zones(chain_kicks),
            "terminal": chain["terminal"],
        }
        scored_chains.append(public)
        audit_chains.append(
            {
                **public,
                "play_segment": chain["play_segment"],
                "log_start_s": round(chain_kicks[0].time_s - epoch_s, 3),
                "log_end_s": round(chain_kicks[-1].time_s - epoch_s, 3),
                "segment_end_log_s": round(
                    segment_end_times.get(chain["play_segment"], math.inf) - epoch_s,
                    3,
                ),
                "kick_log_times_s": [
                    round(kick.time_s - epoch_s, 3) for kick in chain_kicks
                ],
                "robot_ids": [kick.robot_id for kick in chain_kicks],
                "kick_positions_m": [
                    [round(kick.x_m, 3), round(kick.y_m, 3)] for kick in chain_kicks
                ],
                "kick_speeds_mps": [round(kick.speed_mps, 3) for kick in chain_kicks],
            }
        )
    return scored_chains, audit_chains


def main() -> None:
    args = parse_args()
    states, observations, score_changes = read_log(args.log)
    states_epoch = states[0].time_s
    if not score_changes:
        raise ValueError("no goals found")
    first_goal_s = score_changes[0][0]
    kicks, rejected = build_kicks(states, observations, first_goal_s)
    scored_chains, audit_chains = build_chains(
        kicks, score_changes, build_segment_end_times(states), states_epoch
    )
    if len(scored_chains) < 10:
        raise ValueError(f"unexpectedly sparse ground truth: {len(scored_chains)} chains")

    result = {"chains": scored_chains}
    audit = {
        "source_log": args.log.name,
        "tracker_source": TRACKER_SOURCE,
        "first_goal_log_s": round(first_goal_s - states_epoch, 3),
        "score_changes": [
            {
                "log_s": round(time_s - states_epoch, 3),
                "team_name": name,
                "score": score,
            }
            for time_s, name, score in score_changes
        ],
        "observation_count": len(observations),
        "identity_cluster_count": len(cluster_identity_observations(observations)),
        "cluster_count": len(cluster_observations(observations)),
        "accepted_active_kicks": len(kicks),
        "rejected_clusters": rejected,
        "scored_chain_count": len(scored_chains),
        "constants": {
            "kick_cluster_window_s": KICK_CLUSTER_WINDOW_S,
            "physical_kick_merge_window_s": PHYSICAL_KICK_MERGE_WINDOW_S,
            "physical_kick_merge_distance_m": PHYSICAL_KICK_MERGE_DISTANCE_M,
            "min_kick_speed_mps": MIN_KICK_SPEED_MPS,
            "zone_boundary_m": ZONE_BOUNDARY_M,
            "min_chain_kicks": MIN_CHAIN_KICKS,
        },
        "chains": audit_chains,
    }
    for path, payload in (
        (args.ground_truth, result),
        (args.oracle, result),
        (args.audit, audit),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {len(scored_chains)} chains from {len(kicks)} accepted kicks "
        f"({len(observations)} tracker observations)"
    )


if __name__ == "__main__":
    main()
