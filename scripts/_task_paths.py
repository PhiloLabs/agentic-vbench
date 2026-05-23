"""Lookup helper for task dirs under `tasks/<family>/<task>`.

Tasks live under one of four family subdirectories — `agentic_vbench_repair`,
`agentic_vbench_assembly`, `agentic_vbench_sequencing`, `agentic_vbench_repurpose`
— but downstream tooling generally only knows the task name, not the family.
This module resolves names → paths and lists tasks by family.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_ROOT = REPO_ROOT / "tasks"
FAMILIES = (
    "agentic_vbench_repair",
    "agentic_vbench_assembly",
    "agentic_vbench_sequencing",
    "agentic_vbench_repurpose",
)


def task_dir(name: str) -> Path:
    """Return the path to task `name`, searching all family subdirs.

    Backward-compatible: a flat `tasks/<name>` is checked first, so callers
    don't need to know whether the move has been applied yet.
    """
    direct = TASKS_ROOT / name
    if direct.is_dir():
        return direct
    for fam in FAMILIES:
        p = TASKS_ROOT / fam / name
        if p.is_dir():
            return p
    raise FileNotFoundError(f"task not found in any family: {name}")


def family_dir(name: str) -> Path:
    """Return the parent dir of task `name` (= the family subdir, or
    `tasks/` itself in the flat fallback)."""
    direct = TASKS_ROOT / name
    if direct.is_dir():
        return TASKS_ROOT
    for fam in FAMILIES:
        if (TASKS_ROOT / fam / name).is_dir():
            return TASKS_ROOT / fam
    raise FileNotFoundError(f"task family not found: {name}")


def all_tasks(family: str | None = None) -> list[Path]:
    """Return sorted task dirs. With `family`, restrict to that subdir.
    Without, walk all four families."""
    if family is not None:
        sub = TASKS_ROOT / family
        if not sub.is_dir():
            return []
        return sorted(p for p in sub.iterdir() if p.is_dir())
    out: list[Path] = []
    for fam in FAMILIES:
        sub = TASKS_ROOT / fam
        if sub.is_dir():
            out.extend(sorted(p for p in sub.iterdir() if p.is_dir()))
    return out
