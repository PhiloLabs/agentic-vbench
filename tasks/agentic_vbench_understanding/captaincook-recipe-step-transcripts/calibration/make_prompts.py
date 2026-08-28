#!/usr/bin/env python3
"""Derive the calibration prompt from the shipped one, and prove the derivation.

The calibration runs happen outside the task image, so the prompt each agent saw is not
byte-identical to steps/solve/instruction.md: /workspace has to point at a local run
directory. Rather than describe that difference in prose and ask a reviewer to trust it,
this module *is* the difference, and it asserts that substituting the path back
reproduces the shipped bytes exactly. Nothing else is touched: not the question, not the
schema, not the tolerance rule, not one of the 84 labels.

    python3 calibration/make_prompts.py --run-dir /abs/path/to/run --out /abs/prompt.md

Everything here is a function of the shipped prompt, including how many videos there
are, so this file does not need editing when the corpus changes.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
SHIPPED = TASK / "steps" / "solve" / "instruction.md"


def base_prompt(run_dir: str) -> str:
    """The shipped prompt with /workspace pointed at the local run directory."""
    ship = SHIPPED.read_text()
    out = ship.replace("/workspace", run_dir)
    assert out.replace(run_dir, "/workspace") == ship, (
        "the path substitution is not reversible, so it changed more than paths")
    return out


def video_table(text: str) -> list[tuple[str, str, str]]:
    """Pull (letter, length, time range) out of the prompt's own table.

    The letter class is derived from the table itself rather than hardcoded, so a
    corpus of a different size still parses and a truncated table still fails.
    """
    rows = re.findall(
        r"^\| `([A-Z])` \| `[^`]+` \| ([\d.]+ min) \| (`t = 0` to `t = [\d.]+`) \|$",
        text, flags=re.M)
    assert rows, "the prompt has no video table"
    letters = [r[0] for r in rows]
    expected = [chr(65 + i) for i in range(len(rows))]
    assert letters == expected, f"table letters are not A..{expected[-1]}: {letters}"
    return rows


def durations(text: str) -> dict[str, float]:
    return {r[0]: float(re.search(r"t = ([\d.]+)`$", r[2]).group(1))
            for r in video_table(text)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    prompt = base_prompt(args.run_dir.rstrip("/"))
    args.out.write_text(prompt)
    rows = video_table(prompt)
    print(f"wrote {args.out}: {len(prompt)} bytes, {len(rows)} videos, "
          f"{sum(durations(prompt).values())/60:.1f} min")


if __name__ == "__main__":
    main()
