#!/usr/bin/env python3
"""Grade the shipped oracle and an empty submission inside the task image.

    python3 calibration/run_oracle_empty.py --image <image>

Each case runs in a fresh container of the image. The oracle case runs
steps/solve/solution/solve.sh and then the shipped verifier, steps/solve/tests/test.sh.
The empty case writes {"sequence": []} and runs the same verifier. The reward.json each
verifier writes is copied out unchanged to calibration/rollouts/oracle-reward.json and
empty-reward.json, the files scripts/understanding/check_task.py reads, with a manifest
beside them. Neither case needs the video, so setup.sh is not run and each container takes
one CPU, after the same capacity check the arms use.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
ROLLOUTS = HERE / "rollouts"
sys.path.insert(0, str(HERE))
import arm_protocol  # noqa: E402

CASES = {
    "oracle": "bash /solution/solve.sh",
    "empty": "mkdir -p /workspace/output && printf '{\"sequence\": []}' > /workspace/output/solution.json",
}


def sh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    r = subprocess.run(list(args), capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit(f"{' '.join(args[:4])} ... failed ({r.returncode}):\n{(r.stderr or r.stdout)[-800:]}")
    return r


def run_case(image: str, name: str, prepare: str) -> float:
    cid = sh("docker", "run", "-d", "--platform", "linux/arm64", "--cpus", "1", "--memory", "1024m",
             image, "sleep", "infinity").stdout.strip()
    try:
        # Harbor places the tests and the solution at these paths; the image carries neither.
        sh("docker", "exec", cid, "sh", "-c", "test ! -e /tests && test ! -e /solution")
        sh("docker", "cp", str(TASK / "steps" / "solve" / "tests"), f"{cid}:/tests")
        sh("docker", "cp", str(TASK / "steps" / "solve" / "solution"), f"{cid}:/solution")
        sh("docker", "exec", cid, "sh", "-c", f"{prepare} && bash /tests/test.sh")
        out = ROLLOUTS / f"{name}-reward.json"
        sh("docker", "cp", f"{cid}:/logs/verifier/reward.json", str(out))
    finally:
        sh("docker", "rm", "-f", cid, check=False)
    return json.loads(out.read_text())["reward"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    args = ap.parse_args()
    blockers = arm_protocol.capacity_blockers(1)
    assert not blockers, f"no room for one CPU beside what is running: {blockers}"
    ROLLOUTS.mkdir(exist_ok=True)
    image_id = sh("docker", "image", "inspect", args.image, "--format", "{{.Id}}").stdout.strip()
    rewards = {name: run_case(args.image, name, prepare) for name, prepare in CASES.items()}
    (ROLLOUTS / "oracle-empty-manifest.json").write_text(json.dumps({
        "image": args.image, "image_id": image_id,
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cases": {name: {"prepare": CASES[name], "then": "bash /tests/test.sh",
                         "reward_json": f"{name}-reward.json", "reward": rewards[name]}
                  for name in CASES},
    }, indent=1) + "\n")
    print(f"oracle {rewards['oracle']}, empty {rewards['empty']}, image {image_id[:19]}")
    assert rewards["oracle"] == 1.0 and rewards["empty"] == 0.0, rewards
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
