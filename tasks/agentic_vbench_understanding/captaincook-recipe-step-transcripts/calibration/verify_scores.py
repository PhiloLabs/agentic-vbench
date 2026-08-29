#!/usr/bin/env python3
"""Recompute every number README.md, SPEC.md and scores.md assert, and fail on any
that the artifacts do not back.

A document is not evidence. Each claim below is recomputed from the artifact it
describes, and the document text is then searched for the recomputed value. Run it from
the task directory:

    python3 calibration/verify_scores.py

Three defects in the version of this file inherited from the sibling task are worth
stating, because all three were the same shape, a checker that passed while unable to
fail:

1. It searched for the recomputed value as a plain substring. "0.0" is a substring of
   "0.0762", and "0" is a substring of almost everything, so any claim that recomputed to
   a short or round value passed no matter what the document said. Matching is bounded:
   a number must not be flanked by another digit or by a decimal point.

2. It graded rollouts with a key they had never been measured against. Every one scored
   zero, every zero was "found" in the text by defect 1, and the run exited green with
   twenty numbers silently wrong. Here every arm is graded by the shipped judge, which is
   the judge it was actually measured on, and the recomputed reward is required to equal
   the reward.json shipped beside it rather than merely to appear somewhere in the prose.

3. The turn counts were prose. They are the second of the family's two gates, so they are
   recounted here from the shipped rollout by the same reader that produced them.

Two controls run at the end: a sentinel that must NOT be found, and a real value with one
digit corrupted that must ALSO not be found. If either turns up, this file says its own
pass is meaningless rather than reporting success.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
sys.path.insert(0, str(TASK / "steps" / "solve" / "tests"))
sys.path.insert(0, str(HERE))
import judge  # noqa: E402
from make_prompts import base_prompt  # noqa: E402

DERIVED = json.loads((TASK / "provenance" / "step-derived.json").read_text())
DOCS = {p.name: p.read_text()
        for p in (TASK / "README.md", TASK / "SPEC.md", HERE / "scores.md")}
ROLLOUTS = HERE / "rollouts"

checks: list[tuple[str, str, str]] = []


def claim(label: str, value, doc: str) -> None:
    checks.append((label, str(value), doc))


def found(value: str, text: str) -> bool:
    """Whole-number match. A digit on either side, or a decimal point that is itself part
    of a number, means this is a different number that merely contains ours, which is
    what defect 1 above was. A period that ends a sentence is not part of a number, so
    the lookahead has to allow it."""
    return re.search(rf"(?<!\d)(?<!\d\.){re.escape(value)}(?!\d)(?!\.\d)", text) is not None


def corrupt(value: str) -> str:
    """A value that is definitely not the right one, for the negative control."""
    digits = [c for c in value if c.isdigit()]
    if not digits:
        return value + "9"
    last = len(value) - 1 - value[::-1].index(digits[-1])
    return value[:last] + str((int(value[last]) + 5) % 10) + value[last + 1:]


def arms() -> list[tuple[str, dict]]:
    """Every arm that has a manifest beside its rollout, newest gate first."""
    out = []
    for m in sorted(ROLLOUTS.glob("*-manifest.json")):
        out.append((m.name.split("-manifest")[0], json.loads(m.read_text())))
    return out


def turn_count(rollout: Path) -> int:
    """Recount tool calls with the shipped auditor rather than trusting scores.md.

    The auditor is run as a subprocess against /workspace, which is what the shipped
    rollout's paths were rewritten to, so this exercises the same code path a reviewer
    would. A non-zero exit is not fatal here: exit 1 means the audit found something to
    review, which scores.md discusses, while exit 2 means a control failed and the count
    would be meaningless, so only exit 2 raises.
    """
    r = subprocess.run(
        [sys.executable, str(HERE / "audit_trajectory.py"),
         "--run-dir", "/workspace", "--rollout", str(rollout)],
        capture_output=True, text=True)
    if r.returncode == 2:
        raise SystemExit(f"{rollout.name}: the auditor's controls failed, so no turn "
                         f"count can be trusted\n{r.stdout}{r.stderr}")
    m = re.search(r"^tool calls: (\d+)", r.stdout, re.M)
    assert m, f"{rollout.name}: the auditor printed no turn count\n{r.stdout}{r.stderr}"
    return int(m.group(1))


def main() -> int:
    gt = judge.GROUND_TRUTH
    letters = sorted(gt)
    vocab = DERIVED["vocabulary"]

    # ---- the key --------------------------------------------------------------
    claim("total instances", sum(len(v) for v in gt.values()), "SPEC.md")
    claim("vocabulary size", len(judge.VOCABULARY), "SPEC.md")
    claim("number of recordings", len(letters), "SPEC.md")
    claim("total minutes",
          f'{sum(v["duration_sec"] for v in DERIVED["videos"]) / 60:.1f}', "SPEC.md")
    elig = DERIVED["eligibility"]
    claim("total order inversions",
          sum(elig[l]["n_order_inversions"] for l in letters), "SPEC.md")
    claim("total error-annotated steps",
          sum(elig[l]["n_error_steps"] for l in letters), "SPEC.md")
    claim("distinct activities",
          len({v["activity_id"] for v in DERIVED["videos"]}), "SPEC.md")

    durs = sorted(v["duration_sec"] / 60 for v in DERIVED["videos"])
    claim("shortest recording, minutes", f"{durs[0]:.1f}", "SPEC.md")
    claim("longest recording, minutes", f"{durs[-1]:.1f}", "SPEC.md")

    step_lens = [g["t_end"] - g["t_start"] for v in gt.values() for g in v]
    claim("median step, seconds", f"{statistics.median(step_lens):.0f}", "SPEC.md")

    taus = [g["tau"] for v in gt.values() for g in v]
    claim("share of tau at the 3 s cap",
          f"{sum(t >= 2.9999 for t in taus) / len(taus):.0%}"[:-1], "SPEC.md")

    shares = sorted((len(v) / len(taus) for v in gt.values()), reverse=True)
    claim("largest single recording's share of the key", f"{shares[0]:.1%}"[:-1], "SPEC.md")
    claim("largest five recordings' share of the key", f"{sum(shares[:5]):.1%}"[:-1], "SPEC.md")

    # ---- the scorer's fixed points --------------------------------------------
    oracle = [{"video": l, **{k: g[k] for k in ("id", "t_start", "t_end")}}
              for l, v in gt.items() for g in v]
    assert judge.grade(oracle)["f1"] == 1.0, "the oracle no longer scores 1.0"
    assert judge.grade([])["f1"] == 0.0, "an empty submission no longer scores 0.0"

    # ---- the deterministic ablations ------------------------------------------
    spec = importlib.util.spec_from_file_location(
        "abl", TASK / "provenance" / "ablations" / "run_ablations.py")
    abl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(abl)
    recipe = judge.grade(abl.spread(abl.CANONICAL))["f1"]
    claim("recipe prior reward", f"{recipe:.4f}", "SPEC.md")
    best_spam = max(round(judge.grade(abl.cyclic(abl.frequent_labels(t), s))["f1"], 4)
                    for t in (5, 10, 20) for s in (2.0, 5.0))
    claim("best spam reward", f"{best_spam:.4f}", "SPEC.md")
    assert best_spam <= 0.15, "a no-video strategy broke the 0.15 gate"
    rotate = {a: b for a, b in zip(letters, letters[1:] + letters[:1])}
    misfiled = judge.grade([{**e, "video": rotate[e["video"]]} for e in oracle])["f1"]
    # Formatted the way the ablation table prints it, which is `0.0` and not `0.0000`.
    # The bounded matcher is what makes claiming a value this short safe: `0.0` inside
    # `0.0762` is followed by a digit and does not match.
    claim("misfiled-video reward", str(round(misfiled, 4)), "SPEC.md")
    assert misfiled <= 0.15, "filing the oracle under the wrong video broke the 0.15 gate"

    # ---- the arms -------------------------------------------------------------
    # Each arm is graded here, from its shipped solution, by the shipped judge. The
    # recomputed reward must equal the reward.json shipped beside it: a claim that only
    # has to appear somewhere in the prose is the hole defect 2 came through.
    measured = arms()
    notes: list[str] = []
    stale: list[str] = []
    for name, man in measured:
        sol_path = ROLLOUTS / f"{name}-solution.json"
        entries = json.loads(sol_path.read_text())["sequence"]
        r = judge.grade(entries)
        shipped = json.loads((ROLLOUTS / f"{name}-reward.json").read_text())
        assert abs(r["f1"] - shipped["reward"]) < 1e-12, (
            f"{name}: regrading the shipped solution gives {r['f1']}, but the shipped "
            f"reward.json says {shipped['reward']}")
        assert hashlib.sha256(sol_path.read_bytes()).hexdigest() == man["solution_sha256"], (
            f"{name}: the shipped solution is not the one the manifest recorded")
        claim(f"{name} reward", f'{r["f1"]:.4f}', "scores.md")
        claim(f"{name} entries", r["n_predicted"], "scores.md")
        claim(f"{name} true positives", r["true_positives"], "scores.md")
        claim(f"{name} label-and-order matches", r["label_and_order_only_matches"], "scores.md")
        claim(f"{name} onset-only matches", r["onset_only_matches"], "scores.md")
        assert r["f1"] < 0.10, (
            f"{name} scored {r['f1']:.4f}, at or above the family's 0.10 ceiling")

        turns = turn_count(ROLLOUTS / man["trajectory"])
        claim(f"{name} tool-call turns", turns, "scores.md")
        assert turns > 50, f"{name} ran {turns} turns, at or below the family's floor of 50"

        # The prompt each arm was handed must be the shipped prompt with paths moved.
        # A mismatch here does not mean the arm was cheated; the ordinary cause is that
        # the shipped prompt has been edited since the arm ran, which makes the arm stale
        # rather than invalid. Either way the calibration no longer speaks for the task as
        # it currently stands, so it is collected and reported instead of asserted, and
        # the run still exits non-zero.
        prompt = base_prompt(man["run_dir"])
        if hashlib.sha256(prompt.encode()).hexdigest() != man["prompt_sha256"]:
            stale.append(name)
            notes.append(f"  STALE   {name:<12} {r['f1']:.4f} / {turns} turns / ran "
                         f"against a different prompt than the one shipped now")
            continue
        notes.append(f"  ok      {name:<12} {r['f1']:.4f} / {turns} turns / prompt is the "
                     f"shipped prompt at {man['run_dir']}")

    # ---- controls -------------------------------------------------------------
    sentinel = "0.deadbeef-not-in-any-document"
    assert not any(sentinel in t for t in DOCS.values()), "sentinel is not a sentinel"
    real = [(lbl, val, doc) for lbl, val, doc in checks if any(c.isdigit() for c in val)]
    assert real, "no numeric claim to build a negative control from"
    neg_label, neg_value, neg_doc = real[0]
    negative = corrupt(neg_value)

    missing = []
    for label, value, doc in checks:
        if found(value, DOCS[doc]):
            print(f"  ok      {label:<44} = {value}   ({doc})")
        else:
            missing.append(f"  WRONG   {label:<44} = {value}   not found in {doc}")

    control_failures = []
    if any(sentinel in t for t in DOCS.values()):
        control_failures.append("the sentinel was found in the text")
    if found(negative, DOCS[neg_doc]):
        control_failures.append(
            f"the corrupted value {negative} (from {neg_label} = {neg_value}) was also "
            f"found in {neg_doc}, so a wrong number would have passed here")
    if control_failures:
        print("\n" + "\n".join("  CONTROL FAILED  " + c for c in control_failures))
        raise SystemExit("this checker cannot detect a wrong claim, so its pass means nothing")

    if missing:
        print("\n" + "\n".join(missing))
        raise SystemExit(f"\n{len(missing)} claim(s) the artifacts do not back")

    print(f"\n{len(checks)} document claims recomputed and found in the text.")
    print(f"  controls: the sentinel was not found, and corrupting {neg_label} to "
          f"{negative} was correctly not found either.")
    print(f"  key: oracle 1.0, empty 0.0, misfiled-video {misfiled:.4f}, every no-video "
          f"strategy at or under {best_spam:.4f}.")
    print("\n".join(notes))

    if stale:
        print(f"\n  {len(stale)} arm(s) ran against an older prompt: {', '.join(stale)}.")
        print("  The shipped question has changed since, so these scores do not speak")
        print("  for the task as it now stands and must be re-measured.")

    ran = {name for name, _ in measured if name not in stale}
    pending = [a for a in ("codex", "claude", "antigravity") if a not in ran]
    if pending:
        print(f"  NOT MEASURED AGAINST THE CURRENT PROMPT: {', '.join(pending)}. This "
              f"file cannot say the task\n  clears either gate, and does not.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
