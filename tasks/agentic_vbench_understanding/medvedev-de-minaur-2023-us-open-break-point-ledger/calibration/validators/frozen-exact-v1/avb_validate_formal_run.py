#!/usr/bin/env python3
"""Validate and fingerprint one completed formal agentic-vbench calibration run."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

FINAL_TASK_FILES = (
    "steps/solve/instruction.md",
    "steps/solve/tests/judge.py",
    "steps/solve/tests/test_judge.py",
    "steps/solve/solution/solve.sh",
)
EXPECTED_FORMULA = "2 * exact_ordered_event_matches / (n_predicted + n_reference)"
VALIDATION_POLICY = "avb-formal-run-strict-v3"
ALLOW_LINE = re.compile(r"^\S+ ALLOW authority='chatgpt\.com:443' sni='chatgpt\.com'$")
START_LINE = re.compile(r"^(?P<timestamp>\S+) START allowlist=chatgpt\.com:443$")
CLOSE_LINE = re.compile(
    r"^(?P<timestamp>\S+) CLOSE authority='chatgpt\.com:443' "
    r"client_bytes=(?P<client_bytes>\d+) "
    r"upstream_bytes=(?P<upstream_bytes>-?\d+)$"
)
STARTUP_DNS_ERROR_LINE = re.compile(
    r"^(?P<timestamp>\S+) ERROR authority='chatgpt\.com:443' "
    r"error=gaierror\(-2, 'Name or service not known'\)$"
)
RECOVERABLE_RELAY_RESET_LINE = re.compile(
    r"^(?P<timestamp>\S+) RELAY_END direction=client-to-upstream "
    r"bytes=(?P<bytes>\d+) "
    r"error=ConnectionResetError\(104, 'Connection reset by peer'\)$"
)
RECOVERABLE_BROKEN_PIPE_LINE = re.compile(
    r"^(?P<timestamp>\S+) RELAY_END direction=client-to-upstream "
    r"bytes=(?P<bytes>\d+) error=BrokenPipeError\(32, 'Broken pipe'\)$"
)
DENY_AUTHORITY_LINE = re.compile(
    r"^(?P<timestamp>\S+) DENY authority='(?P<authority>[^'\r\n]+)'$"
)
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_native_events(path: Path) -> list[dict]:
    events = []
    for line in path.read_text(encoding="utf-8", errors="strict").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def parse_timestamp(value: str) -> dt.datetime:
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp has no timezone: {value!r}")
    return parsed


def validate_execution_envelope(
    trial_started: dt.datetime,
    trial_finished: dt.datetime,
    execution_started: dt.datetime,
    execution_finished: dt.datetime,
) -> None:
    if not (trial_started <= execution_started <= execution_finished <= trial_finished):
        raise ValueError("agent execution lies outside the completed trial window")


def validate_ordered_timestamps_within(
    label: str,
    timestamps: list[dt.datetime],
    lower: dt.datetime,
    upper: dt.datetime,
) -> None:
    if not timestamps:
        raise ValueError(f"{label} has no timestamps")
    if any(left > right for left, right in zip(timestamps, timestamps[1:])):
        raise ValueError(f"{label} timestamps are not ordered")
    if any(not (lower <= timestamp <= upper) for timestamp in timestamps):
        raise ValueError(f"{label} timestamp lies outside agent execution window")


def require_later_atif_step(
    label: str,
    event_timestamp: dt.datetime,
    atif_agent_timestamps: list[dt.datetime],
) -> None:
    if not any(timestamp > event_timestamp for timestamp in atif_agent_timestamps):
        raise ValueError(f"{label} has no later ATIF agent step")


def validate_reward_consistency(
    reward_payload: dict,
    expected_ground_truth_events: int,
) -> tuple[float | int, dict]:
    """Recompute exact-event F1 from verifier counts and reject contradictions."""
    if expected_ground_truth_events <= 0:
        raise ValueError("expected ground-truth event count must be positive")
    reward = reward_payload.get("reward")
    if (
        not isinstance(reward, (int, float))
        or isinstance(reward, bool)
        or not math.isfinite(reward)
    ):
        raise ValueError("verifier reward is not a finite number")
    details = reward_payload.get("details")
    if not isinstance(details, dict):
        raise ValueError("verifier details are absent or malformed")
    formula = details.get("formula")
    if formula != EXPECTED_FORMULA:
        raise ValueError(f"unexpected verifier formula: {formula!r}")
    names = (
        "n_predicted",
        "n_ground_truth",
        "exact_event_matches_ordered",
        "reward_denominator",
    )
    counts = {}
    for name in names:
        value = details.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"verifier detail {name!r} is not a nonnegative int")
        counts[name] = value
    n_predicted = counts["n_predicted"]
    n_ground_truth = counts["n_ground_truth"]
    exact_matches = counts["exact_event_matches_ordered"]
    denominator = n_predicted + n_ground_truth
    if n_ground_truth != expected_ground_truth_events:
        raise ValueError(
            f"ground-truth count {n_ground_truth} != pinned expected count "
            f"{expected_ground_truth_events}"
        )
    if denominator <= 0 or counts["reward_denominator"] != denominator:
        raise ValueError("verifier reward denominator is inconsistent")
    if exact_matches > min(n_predicted, n_ground_truth):
        raise ValueError("exact-event match count exceeds available events")
    recomputed_reward = round(2 * exact_matches / denominator, 4)
    if reward != recomputed_reward:
        raise ValueError(
            f"verifier reward {reward!r} != recomputed reward {recomputed_reward!r}"
        )
    return reward, details


def locate_session_file(trial: Path) -> Path:
    completed = trial / "steps" / "solve" / "agent" / "sessions"
    active = trial / "agent" / "sessions"
    root = completed if completed.exists() else active
    files = sorted(root.rglob("*.jsonl")) if root.exists() else []
    if len(files) != 1:
        raise ValueError(f"expected exactly one raw session JSONL, found {len(files)}")
    return files[0]


def productive_session_timestamps(path: Path) -> list[dt.datetime]:
    """Return timestamps for every model-produced reasoning/message/active item."""
    productive_types = {
        "reasoning",
        "function_call",
        "custom_tool_call",
        "web_search_call",
        "computer_initialize_state",
    }
    timestamps = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8", errors="strict").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"malformed session JSONL at line {line_number}: {exc}"
            ) from exc
        if not isinstance(event, dict) or event.get("type") != "response_item":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        payload_type = payload.get("type")
        productive = payload_type in productive_types or (
            payload_type == "message" and payload.get("role") == "assistant"
        )
        if productive:
            timestamp = event.get("timestamp")
            if not isinstance(timestamp, str):
                raise ValueError("productive session item has no timestamp")
            timestamps.append(parse_timestamp(timestamp))
    if not timestamps:
        raise ValueError("raw session has no productive model response item")
    if any(left > right for left, right in zip(timestamps, timestamps[1:])):
        raise ValueError("raw productive session timestamps are not ordered")
    return timestamps


def first_productive_session_timestamp(path: Path) -> dt.datetime:
    """Compatibility helper returning the first productive session timestamp."""
    return productive_session_timestamps(path)[0]


def recompute_harbor_task_checksum(task_dir: Path) -> str:
    """Recompute Harbor's authoritative whole-task checksum without network I/O."""
    try:
        from harbor.models.task.task import Task
    except ModuleNotFoundError:
        harbor_cli = shutil.which("harbor")
        if harbor_cli is None:
            raise RuntimeError(
                "cannot recompute overlay checksum: Harbor is not importable and "
                "the harbor executable is not on PATH"
            )
        harbor_python = Path(harbor_cli).resolve().parent / "python"
        if not harbor_python.is_file():
            raise RuntimeError(
                f"cannot locate Harbor's Python runtime beside {harbor_cli!r}"
            )
        completed = subprocess.run(
            [
                str(harbor_python),
                "-c",
                (
                    "from harbor.models.task.task import Task; import sys; "
                    "print(Task(sys.argv[1]).checksum)"
                ),
                str(task_dir.resolve()),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        checksum = completed.stdout.strip()
    else:
        checksum = Task(task_dir.resolve()).checksum
    if SHA256_HEX.fullmatch(checksum) is None:
        raise ValueError(f"Harbor returned a malformed task checksum: {checksum!r}")
    return checksum


def classify_gateway_lines(
    lines: list[str],
) -> tuple[list[str], list[dt.datetime]]:
    """Apply a closed-world grammar to every nonempty gateway audit line."""
    if not lines:
        raise ValueError("gateway log is empty")
    kinds = []
    timestamps = []
    patterns = (
        ("start", START_LINE),
        ("allow", ALLOW_LINE),
        ("close", CLOSE_LINE),
        ("startup_dns_error", STARTUP_DNS_ERROR_LINE),
        ("connection_reset", RECOVERABLE_RELAY_RESET_LINE),
        ("broken_pipe", RECOVERABLE_BROKEN_PIPE_LINE),
        ("deny_authority", DENY_AUTHORITY_LINE),
    )
    for index, line in enumerate(lines):
        kind = next(
            (name for name, pattern in patterns if pattern.fullmatch(line)),
            None,
        )
        if kind is None:
            raise ValueError(
                f"gateway line {index + 1} is outside the closed-world grammar"
            )
        kinds.append(kind)
        timestamps.append(parse_timestamp(line.split(" ", 1)[0]))
    if kinds[0] != "start" or kinds.count("start") != 1:
        raise ValueError("gateway START must be the unique first audit event")
    return kinds, timestamps


def validate_gateway_connection_conservation(
    allow_count: int,
    close_byte_counts: list[tuple[int, int]],
    error_count: int,
) -> None:
    if any(client <= 0 or upstream <= 0 for client, upstream in close_byte_counts):
        raise ValueError("gateway contains a nonpositive CLOSE byte count")
    if allow_count != len(close_byte_counts) + error_count:
        raise ValueError(
            "gateway connection conservation failed: ALLOW != CLOSE + ERROR"
        )


def locate_step_file(trial: Path, relative: str) -> Path:
    completed = trial / "steps" / "solve" / relative
    if completed.exists():
        return completed
    active = trial / relative
    if active.exists():
        return active
    raise FileNotFoundError(relative)


def inspect_image(reference: str) -> dict:
    completed = subprocess.run(
        ["docker", "image", "inspect", reference],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, list) or len(payload) != 1:
        raise ValueError("docker image inspect did not return exactly one image")
    return payload[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trial-dir", required=True, type=Path)
    parser.add_argument("--gateway-log", required=True, type=Path)
    parser.add_argument("--canonical-task", required=True, type=Path)
    parser.add_argument("--overlay-task", required=True, type=Path)
    parser.add_argument("--image", required=True)
    parser.add_argument("--expected-image-id", required=True)
    parser.add_argument("--expected-reward", required=True, type=float)
    parser.add_argument("--expected-ground-truth-events", required=True, type=int)
    parser.add_argument("--expected-task-checksum", required=True)
    parser.add_argument("--expected-model", required=True)
    parser.add_argument("--expected-agent-version", required=True)
    parser.add_argument("--expected-reasoning-effort", required=True)
    parser.add_argument("--expected-agent-import-path", required=True)
    parser.add_argument("--expected-manifest-line", action="append", required=True)
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--expected-startup-dns-errors", type=int, default=0)
    parser.add_argument("--expected-connection-resets", type=int, default=0)
    parser.add_argument("--expected-broken-pipes", type=int, default=0)
    parser.add_argument("--minimum-tool-calls", type=int, default=0)
    parser.add_argument("--require-solution", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    validator_path = Path(__file__).resolve()
    validator_sha256 = sha256(validator_path)

    trial = args.trial_dir.resolve()
    result = load_json(trial / "result.json")
    if not result.get("finished_at"):
        raise ValueError("trial result has no finished_at timestamp")
    trial_started_timestamp = parse_timestamp(result.get("started_at", ""))
    trial_finished_timestamp = parse_timestamp(result["finished_at"])
    if trial_started_timestamp > trial_finished_timestamp:
        raise ValueError("trial result timestamps are reversed")
    if SHA256_HEX.fullmatch(args.expected_task_checksum) is None:
        raise ValueError("expected task checksum is not lowercase SHA-256")
    if result.get("task_checksum") != args.expected_task_checksum:
        raise ValueError(
            f"task checksum {result.get('task_checksum')!r} != "
            f"{args.expected_task_checksum!r}"
        )
    recomputed_overlay_checksum = recompute_harbor_task_checksum(args.overlay_task)
    if recomputed_overlay_checksum != args.expected_task_checksum:
        raise ValueError(
            f"current overlay checksum {recomputed_overlay_checksum!r} != "
            f"run checksum {args.expected_task_checksum!r}"
        )
    if result.get("exception_info") is not None:
        raise ValueError(f"trial exception: {result['exception_info']!r}")
    step_results = result.get("step_results")
    if not isinstance(step_results, list) or len(step_results) != 1:
        raise ValueError("expected exactly one completed step")
    step_result = step_results[0]
    if step_result.get("exception_info") is not None:
        raise ValueError(f"step exception: {step_result['exception_info']!r}")
    execution = step_result.get("agent_execution") or {}
    if not execution.get("started_at") or not execution.get("finished_at"):
        raise ValueError("agent execution did not complete")
    execution_started_timestamp = parse_timestamp(execution["started_at"])
    execution_finished_timestamp = parse_timestamp(execution["finished_at"])
    validate_execution_envelope(
        trial_started_timestamp,
        trial_finished_timestamp,
        execution_started_timestamp,
        execution_finished_timestamp,
    )

    result_config = result.get("config") or {}
    configured_task = (result_config.get("task") or {}).get("path")
    if not isinstance(configured_task, str):
        raise ValueError("trial config has no task path")
    if Path(configured_task).resolve() != args.overlay_task.resolve():
        raise ValueError("trial config task path does not match overlay task")
    configured_agent = result_config.get("agent") or {}
    if configured_agent.get("import_path") != args.expected_agent_import_path:
        raise ValueError("unexpected configured agent import path")
    if configured_agent.get("model_name") != args.expected_model:
        raise ValueError("unexpected configured model")
    configured_kwargs = configured_agent.get("kwargs") or {}
    if configured_kwargs.get("version") != args.expected_agent_version:
        raise ValueError("unexpected configured agent version")
    if configured_kwargs.get("reasoning_effort") != args.expected_reasoning_effort:
        raise ValueError("unexpected configured reasoning effort")

    agent_info = result.get("agent_info") or {}
    if agent_info.get("name") != "codex":
        raise ValueError("unexpected result agent name")
    if agent_info.get("version") != args.expected_agent_version:
        raise ValueError("unexpected result agent version")
    if (agent_info.get("model_info") or {}).get("name") != args.expected_model:
        raise ValueError("unexpected result model")

    reward_path = locate_step_file(trial, "verifier/reward.json")
    reward_payload = load_json(reward_path)
    if not isinstance(reward_payload, dict):
        raise ValueError("verifier reward payload is not an object")
    reward, reward_details = validate_reward_consistency(
        reward_payload, args.expected_ground_truth_events
    )
    if reward != args.expected_reward:
        raise ValueError(f"reward {reward!r} != {args.expected_reward!r}")
    formula = reward_details["formula"]

    solution_candidates = (
        trial / "solution.json",
        trial / "steps" / "solve" / "solution.json",
        trial / "steps" / "solve" / "agent" / "solution.json",
        trial / "steps" / "solve" / "artifacts" / "solution.json",
    )
    solution_path = next(
        (candidate for candidate in solution_candidates if candidate.exists()), None
    )
    if args.require_solution and solution_path is None:
        raise ValueError("required submitted solution artifact is absent")

    codex_path = locate_step_file(trial, "agent/codex.txt")
    events = parse_native_events(codex_path)
    if sum(event.get("type") == "turn.completed" for event in events) != 1:
        raise ValueError("native Codex trajectory lacks exactly one completed turn")
    if any(event.get("type") == "turn.failed" for event in events):
        raise ValueError("native Codex trajectory contains a failed turn")
    native_lines = codex_path.read_text(encoding="utf-8", errors="strict").splitlines()
    native_tool_starts = sum(
        event.get("type") == "item.started"
        and isinstance(event.get("item"), dict)
        and event["item"].get("type")
        in {
            "command_execution",
            "mcp_tool_call",
            "web_search",
            "file_change",
            "todo_list",
            "collab_tool_call",
        }
        for event in events
    )
    if any(
        event.get("type") == "web_search"
        or (
            isinstance(event.get("item"), dict)
            and event["item"].get("type") == "web_search"
        )
        for event in events
    ):
        raise ValueError("native trajectory contains web search")

    trajectory_path = locate_step_file(trial, "agent/trajectory.json")
    trajectory = load_json(trajectory_path)
    if trajectory.get("schema_version") != "ATIF-v1.5":
        raise ValueError("unexpected ATIF schema version")
    trajectory_agent = trajectory.get("agent") or {}
    if trajectory_agent.get("name") != "codex":
        raise ValueError("unexpected ATIF agent name")
    if trajectory_agent.get("version") != args.expected_agent_version:
        raise ValueError("unexpected ATIF agent version")
    if trajectory_agent.get("model_name") != args.expected_model:
        raise ValueError("unexpected ATIF model")
    atif_agent_timestamps = []
    for step in trajectory.get("steps", []):
        if isinstance(step, dict) and step.get("source") == "agent":
            timestamp = step.get("timestamp")
            if not isinstance(timestamp, str):
                raise ValueError("ATIF agent step has no timestamp")
            atif_agent_timestamps.append(parse_timestamp(timestamp))
    if not atif_agent_timestamps:
        raise ValueError("ATIF trajectory has no agent steps")
    validate_ordered_timestamps_within(
        "ATIF agent",
        atif_agent_timestamps,
        execution_started_timestamp,
        execution_finished_timestamp,
    )
    first_atif_agent_timestamp = atif_agent_timestamps[0]
    last_atif_agent_timestamp = atif_agent_timestamps[-1]
    atif_call_ids = []
    atif_result_ids = []
    atif_tool_call_turns = 0
    for step in trajectory.get("steps", []):
        if not isinstance(step, dict):
            continue
        calls = step.get("tool_calls", [])
        if not isinstance(calls, list):
            raise ValueError("ATIF tool_calls is not a list")
        if not calls:
            continue
        if step.get("source") != "agent":
            raise ValueError("non-agent ATIF step contains tool calls")
        atif_tool_call_turns += 1
        results = (step.get("observation") or {}).get("results", [])
        if not isinstance(results, list):
            raise ValueError("ATIF observation results is not a list")
        step_call_ids = []
        for call in calls:
            if (
                not isinstance(call, dict)
                or not isinstance(call.get("tool_call_id"), str)
                or not isinstance(call.get("function_name"), str)
                or not isinstance(call.get("arguments"), dict)
            ):
                raise ValueError("malformed ATIF tool call")
            step_call_ids.append(call["tool_call_id"])
        step_result_ids = [
            result.get("source_call_id")
            for result in results
            if isinstance(result, dict)
        ]
        if sorted(step_call_ids) != sorted(step_result_ids):
            raise ValueError(
                f"ATIF tool calls/results disagree in step {step.get('step_id')!r}"
            )
        atif_call_ids.extend(step_call_ids)
        atif_result_ids.extend(step_result_ids)

    atif_tool_calls = len(atif_call_ids)
    if len(set(atif_call_ids)) != atif_tool_calls:
        raise ValueError("ATIF contains duplicate tool-call IDs")
    if atif_call_ids != atif_result_ids:
        raise ValueError("ATIF tool-call/result order differs")
    # ATIF counts outer unified-exec turns. The native log records nested Codex
    # operations, but intentionally omits media-view operations; one outer turn
    # may also contain several nested operations. The two counts therefore have
    # no valid ordering relationship and are independently reported.
    if atif_tool_calls and native_tool_starts == 0:
        raise ValueError("ATIF has tool calls but native trajectory has no operations")
    if atif_tool_call_turns < args.minimum_tool_calls:
        raise ValueError(
            f"only {atif_tool_call_turns} tool-call turns; need "
            f"{args.minimum_tool_calls}"
        )

    gateway_bytes = args.gateway_log.read_bytes()
    gateway_sha256 = hashlib.sha256(gateway_bytes).hexdigest()
    gateway_text = gateway_bytes.decode("utf-8", errors="strict")
    gateway_lines = [line for line in gateway_text.splitlines() if line.strip()]
    gateway_kinds, gateway_timestamps = classify_gateway_lines(gateway_lines)
    if any(
        not (trial_started_timestamp <= timestamp <= trial_finished_timestamp)
        for timestamp in gateway_timestamps
    ):
        raise ValueError("gateway audit event lies outside completed trial window")
    indexed_start_lines = [
        (index, START_LINE.fullmatch(line))
        for index, line in enumerate(gateway_lines)
        if " START " in line
    ]
    if len(indexed_start_lines) != 1 or indexed_start_lines[0][1] is None:
        raise ValueError("gateway must contain exactly one exact START line")
    start_index, start_match = indexed_start_lines[0]
    if start_index != 0:
        raise ValueError("gateway START is not the first audit event")
    start_timestamp = parse_timestamp(start_match.group("timestamp"))
    start_count = 1
    allow_lines = [line for line in gateway_lines if " ALLOW " in line]
    if not allow_lines or any(not ALLOW_LINE.fullmatch(line) for line in allow_lines):
        raise ValueError(
            "gateway ALLOW set is empty or includes a non-model hostname/SNI"
        )

    indexed_close_lines = []
    for index, line in enumerate(gateway_lines):
        if " CLOSE " not in line:
            continue
        match = CLOSE_LINE.fullmatch(line)
        if match is None:
            raise ValueError("gateway contains a malformed CLOSE line")
        indexed_close_lines.append((index, match))
    successful_close_lines = [
        (index, match)
        for index, match in indexed_close_lines
        if int(match.group("upstream_bytes")) > 0
    ]
    if not successful_close_lines:
        raise ValueError("gateway has no successful model connection CLOSE")
    first_close_index, first_close_match = successful_close_lines[0]
    first_close_timestamp = parse_timestamp(first_close_match.group("timestamp"))

    indexed_error_lines = [
        (index, line) for index, line in enumerate(gateway_lines) if " ERROR " in line
    ]
    validate_gateway_connection_conservation(
        len(allow_lines),
        [
            (
                int(match.group("client_bytes")),
                int(match.group("upstream_bytes")),
            )
            for _, match in indexed_close_lines
        ],
        len(indexed_error_lines),
    )
    if args.expected_startup_dns_errors < 0:
        raise ValueError("expected startup DNS error count cannot be negative")
    if len(indexed_error_lines) != args.expected_startup_dns_errors:
        raise ValueError(
            f"gateway ERROR count {len(indexed_error_lines)} != explicitly "
            f"expected {args.expected_startup_dns_errors}"
        )
    startup_dns_timestamps = []
    for index, line in indexed_error_lines:
        match = STARTUP_DNS_ERROR_LINE.fullmatch(line)
        if match is None:
            raise ValueError("gateway contains a non-whitelisted ERROR")
        timestamp = parse_timestamp(match.group("timestamp"))
        if not (start_index < index < first_close_index):
            raise ValueError("startup DNS ERROR occurred outside startup window")
        if not (start_timestamp <= timestamp < first_close_timestamp):
            raise ValueError("startup DNS ERROR timestamp is outside startup window")
        startup_dns_timestamps.append(timestamp)

    session_file = locate_session_file(trial)
    session_productive_timestamps = productive_session_timestamps(session_file)
    validate_ordered_timestamps_within(
        "raw productive session",
        session_productive_timestamps,
        execution_started_timestamp,
        execution_finished_timestamp,
    )
    first_session_productive_timestamp = session_productive_timestamps[0]
    last_session_productive_timestamp = session_productive_timestamps[-1]
    if first_session_productive_timestamp > first_atif_agent_timestamp:
        raise ValueError("raw session begins after the first ATIF agent step")
    if last_session_productive_timestamp < last_atif_agent_timestamp:
        raise ValueError("raw session ends before the final ATIF agent step")
    productive_native_indices = []
    startup_wait_native_indices = []
    fallback_native_indices = []
    for index, line in enumerate(native_lines):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            event = None
        if isinstance(event, dict):
            item = event.get("item")
            if (
                event.get("type") == "item.completed"
                and isinstance(item, dict)
                and item.get("type") == "agent_message"
            ) or (
                event.get("type") == "item.started"
                and isinstance(item, dict)
                and item.get("type")
                in {
                    "command_execution",
                    "mcp_tool_call",
                    "web_search",
                    "file_change",
                    "todo_list",
                    "collab_tool_call",
                }
            ):
                productive_native_indices.append(index)
        if (
            "Reconnecting... waiting for network" in line
            or "failed to refresh available models: Connection failed" in line
        ):
            startup_wait_native_indices.append(index)
        if "Falling back from WebSockets to HTTPS transport" in line:
            fallback_native_indices.append(index)
    if not productive_native_indices:
        raise ValueError("native stream has no productive model item")
    first_productive_native_index = productive_native_indices[0]

    if startup_dns_timestamps:
        if not (
            startup_dns_timestamps[-1]
            < first_close_timestamp
            < first_session_productive_timestamp
        ):
            raise ValueError(
                "startup DNS outage did not recover before the first productive "
                "session item"
            )
        if first_close_timestamp >= first_atif_agent_timestamp:
            raise ValueError(
                "startup DNS outage did not recover before the first ATIF agent step"
            )
        startup_native_recovery_indices = [
            index
            for index in startup_wait_native_indices + fallback_native_indices
            if index < first_productive_native_index
        ]
        if not startup_native_recovery_indices or any(
            index >= first_productive_native_index
            for index in startup_wait_native_indices
        ):
            raise ValueError(
                "native startup network recovery is absent or continued after the "
                "first productive item"
            )
    else:
        startup_native_recovery_indices = []

    relay_end_lines = [
        (index, line)
        for index, line in enumerate(gateway_lines)
        if " RELAY_END " in line
    ]
    relay_reset_lines = []
    broken_pipe_lines = []
    for index, line in relay_end_lines:
        reset_match = RECOVERABLE_RELAY_RESET_LINE.fullmatch(line)
        if reset_match:
            if index + 1 >= len(gateway_lines):
                raise ValueError("connection reset has no paired CLOSE")
            paired_close = CLOSE_LINE.fullmatch(gateway_lines[index + 1])
            if paired_close is None:
                raise ValueError("connection reset is not followed by CLOSE")
            if (
                paired_close.group("client_bytes") != reset_match.group("bytes")
                or int(paired_close.group("upstream_bytes")) < 0
            ):
                raise ValueError("connection reset CLOSE does not match")
            if not any(
                later_index > index + 1 for later_index, _ in successful_close_lines
            ):
                raise ValueError("connection reset has no later healthy CLOSE")
            reset_timestamp = parse_timestamp(reset_match.group("timestamp"))
            require_later_atif_step(
                "connection reset", reset_timestamp, atif_agent_timestamps
            )
            relay_reset_lines.append((index, line))
            continue
        broken_pipe_match = RECOVERABLE_BROKEN_PIPE_LINE.fullmatch(line)
        if broken_pipe_match is None:
            raise ValueError("gateway log contains a non-recoverable relay failure")
        if index + 1 >= len(gateway_lines):
            raise ValueError("BrokenPipe relay failure has no paired CLOSE")
        paired_close = CLOSE_LINE.fullmatch(gateway_lines[index + 1])
        if paired_close is None:
            raise ValueError("BrokenPipe relay failure is not followed by CLOSE")
        if (
            paired_close.group("client_bytes") != broken_pipe_match.group("bytes")
            or int(paired_close.group("upstream_bytes")) < 0
        ):
            raise ValueError("BrokenPipe relay failure CLOSE does not match")
        if not any(
            later_index > index + 1 for later_index, _ in successful_close_lines
        ):
            raise ValueError("BrokenPipe relay failure has no later healthy CLOSE")
        broken_pipe_timestamp = parse_timestamp(broken_pipe_match.group("timestamp"))
        require_later_atif_step(
            "BrokenPipe relay failure",
            broken_pipe_timestamp,
            atif_agent_timestamps,
        )
        broken_pipe_lines.append((index, line))
    if args.expected_connection_resets < 0 or args.expected_broken_pipes < 0:
        raise ValueError("expected relay failure counts cannot be negative")
    if len(relay_reset_lines) != args.expected_connection_resets:
        raise ValueError(
            f"connection reset count {len(relay_reset_lines)} != explicitly "
            f"expected {args.expected_connection_resets}"
        )
    if len(broken_pipe_lines) != args.expected_broken_pipes:
        raise ValueError(
            f"BrokenPipe count {len(broken_pipe_lines)} != explicitly expected "
            f"{args.expected_broken_pipes}"
        )
    recovery_events = [
        event
        for event in events
        if event.get("type") in {"error", "item.completed"}
        and "Falling back from WebSockets to HTTPS transport"
        in json.dumps(event, sort_keys=True)
    ]
    if relay_reset_lines and len(recovery_events) < len(relay_reset_lines):
        raise ValueError(
            "gateway reset has no matching native transport-recovery event"
        )
    post_productive_fallbacks = [
        index
        for index in fallback_native_indices
        if index > first_productive_native_index
    ]
    if len(post_productive_fallbacks) < len(relay_reset_lines):
        raise ValueError(
            "connection reset lacks a post-productive native HTTPS fallback"
        )

    last_successful_close_timestamp = parse_timestamp(
        successful_close_lines[-1][1].group("timestamp")
    )
    if start_timestamp > first_session_productive_timestamp:
        raise ValueError("gateway START occurs after the first productive response")
    if start_timestamp > first_atif_agent_timestamp:
        raise ValueError("gateway START occurs after the first ATIF agent step")
    final_productive_timestamp = max(
        last_atif_agent_timestamp, last_session_productive_timestamp
    )
    if last_successful_close_timestamp < final_productive_timestamp:
        raise ValueError(
            "gateway log does not cover the final raw/ATIF productive step"
        )

    image = inspect_image(args.image)
    if image.get("Id") != args.expected_image_id:
        raise ValueError(
            f"actual image {image.get('Id')!r} != {args.expected_image_id!r}"
        )

    task_hashes = {}
    for relative in FINAL_TASK_FILES:
        canonical_path = args.canonical_task / relative
        overlay_path = args.overlay_task / relative
        canonical_hash = sha256(canonical_path)
        overlay_hash = sha256(overlay_path)
        if canonical_hash != overlay_hash:
            raise ValueError(f"canonical/overlay mismatch: {relative}")
        task_hashes[relative] = canonical_hash

    final_overlay_checksum = recompute_harbor_task_checksum(args.overlay_task)
    if final_overlay_checksum != recomputed_overlay_checksum:
        raise ValueError("overlay task changed while validation was running")

    artifacts = (
        locate_step_file(trial, "artifacts/input-manifest.txt")
        if (
            (trial / "steps" / "solve" / "artifacts" / "input-manifest.txt").exists()
            or (trial / "artifacts" / "input-manifest.txt").exists()
        )
        else locate_step_file(trial, "artifacts/ablation-manifest.txt")
    )
    if SHA256_HEX.fullmatch(args.expected_manifest_sha256) is None:
        raise ValueError("expected manifest hash is not lowercase SHA-256")
    manifest_bytes = artifacts.read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    if manifest_sha256 != args.expected_manifest_sha256:
        raise ValueError(
            f"input manifest hash {manifest_sha256!r} != pinned expected hash "
            f"{args.expected_manifest_sha256!r}"
        )
    manifest_lines = manifest_bytes.decode("utf-8", errors="strict").splitlines()
    if "source_validation=passed" not in manifest_lines:
        raise ValueError("input manifest lacks passed source validation")
    for expected_line in args.expected_manifest_line:
        if expected_line not in manifest_lines:
            raise ValueError(
                f"input manifest lacks expected exact line: {expected_line!r}"
            )
    if sha256(validator_path) != validator_sha256:
        raise ValueError("validator changed while validation was running")

    report = {
        "schema_version": "avb-formal-run-validation-v2",
        "validation_policy": VALIDATION_POLICY,
        "validator_sha256": validator_sha256,
        "valid": True,
        "trial_name": result.get("trial_name"),
        "task_checksum": result.get("task_checksum"),
        "overlay_task_checksum_recomputed": recomputed_overlay_checksum,
        "model": ((result.get("agent_info") or {}).get("model_info") or {}).get("name"),
        "reasoning_effort": args.expected_reasoning_effort,
        "agent_import_path": args.expected_agent_import_path,
        "agent": {
            "name": (result.get("agent_info") or {}).get("name"),
            "version": (result.get("agent_info") or {}).get("version"),
        },
        "reward": reward,
        "reward_inputs": {
            "n_predicted": reward_details["n_predicted"],
            "n_ground_truth": reward_details["n_ground_truth"],
            "exact_event_matches_ordered": reward_details[
                "exact_event_matches_ordered"
            ],
            "reward_denominator": reward_details["reward_denominator"],
        },
        "soft_event_f1": reward_details.get("soft_event_f1"),
        "formula": formula,
        "tool_call_turns": atif_tool_call_turns,
        "atif_observed_tool_results": len(atif_result_ids),
        "native_tool_operations": native_tool_starts,
        "atif_tool_call_turns": atif_tool_call_turns,
        "atif_total_tool_calls": atif_tool_calls,
        "image": {
            "reference": args.image,
            "id": image.get("Id"),
            "os": image.get("Os"),
            "architecture": image.get("Architecture"),
            "size": image.get("Size"),
        },
        "gateway": {
            "sha256": gateway_sha256,
            "start_count": start_count,
            "allow_count": len(allow_lines),
            "deny_count": gateway_kinds.count("deny_authority"),
            "closed_world_line_count": len(gateway_lines),
            "error_count": len(indexed_error_lines),
            "startup_network_degraded": bool(startup_dns_timestamps),
            "startup_dns_error_count": len(startup_dns_timestamps),
            "startup_dns_first_timestamp": (
                startup_dns_timestamps[0].isoformat()
                if startup_dns_timestamps
                else None
            ),
            "startup_dns_last_timestamp": (
                startup_dns_timestamps[-1].isoformat()
                if startup_dns_timestamps
                else None
            ),
            "startup_dns_duration_seconds": (
                round(
                    (
                        startup_dns_timestamps[-1] - startup_dns_timestamps[0]
                    ).total_seconds(),
                    6,
                )
                if startup_dns_timestamps
                else 0.0
            ),
            "first_successful_close_timestamp": first_close_timestamp.isoformat(),
            "first_productive_session_timestamp": (
                first_session_productive_timestamp.isoformat()
            ),
            "first_atif_agent_timestamp": first_atif_agent_timestamp.isoformat(),
            "last_atif_agent_timestamp": last_atif_agent_timestamp.isoformat(),
            "last_productive_session_timestamp": (
                last_session_productive_timestamp.isoformat()
            ),
            "native_startup_recovery_count": len(startup_native_recovery_indices),
            "recoverable_connection_reset_count": len(relay_reset_lines),
            "recoverable_broken_pipe_count": len(broken_pipe_lines),
            "native_transport_recovery_count": len(recovery_events),
        },
        "hashes": {
            "final_task_files": task_hashes,
            "native_codex_jsonl": sha256(codex_path),
            "atif_trajectory": sha256(trajectory_path),
            "reward_json": sha256(reward_path),
            "input_manifest": manifest_sha256,
            "raw_session_jsonl": sha256(session_file),
            "submitted_solution": (
                sha256(solution_path) if solution_path is not None else None
            ),
        },
        "started_at": result.get("started_at"),
        "finished_at": result.get("finished_at"),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
