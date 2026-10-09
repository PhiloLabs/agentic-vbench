#!/usr/bin/env python3
"""Derive the calibration prompt from the shipped one, and prove the derivation.

Every arm of this calibration runs inside the task image, where the prompt is the shipped
steps/solve/instruction.md byte for byte. This module is still the one place a prompt is
produced, so that a run outside the image cannot quietly hand an agent a different
question: it points /workspace at a run directory and asserts that substituting the path
back reproduces the shipped bytes exactly. Nothing else is touched.

    python3 calibration/make_prompts.py --run-dir /abs/path/to/run --out /abs/prompt.md
"""
from __future__ import annotations

import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
SHIPPED = TASK / "steps" / "solve" / "instruction.md"


def base_prompt(run_dir: str) -> str:
    """The shipped prompt with /workspace pointed at the run directory."""
    ship = SHIPPED.read_text()
    out = ship.replace("/workspace", run_dir)
    assert out.replace(run_dir, "/workspace") == ship, (
        "the path substitution is not reversible, so it changed more than paths")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    prompt = base_prompt(args.run_dir.rstrip("/"))
    args.out.write_text(prompt)
    print(f"wrote {args.out}: {len(prompt)} bytes")


if __name__ == "__main__":
    main()
