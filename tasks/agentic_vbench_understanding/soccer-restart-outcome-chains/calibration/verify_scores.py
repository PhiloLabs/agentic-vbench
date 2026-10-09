#!/usr/bin/env python3
"""Recompute every number README.md, SPEC.md and scores.md assert, and fail on any that the
artifacts do not back.

    python3 calibration/verify_scores.py

A document is not evidence. Each claim below is recomputed from the artifact it describes,
and the document text is then searched for the recomputed value. Ported from the
CaptainCook4D task's checker, keeping the three fixes that file learned the hard way:

1. Numbers are matched as whole numbers. "0.0" is a substring of "0.0762", so a plain
   substring search passes any short or round value no matter what the document says.
2. Every arm and every measured ablation is regraded by the shipped judge, and the result
   must equal the reward.json shipped beside it, not merely appear somewhere in the prose.
3. Turn counts are recounted from the shipped rollout by the shipped auditor.

The superseded restart contract is checked the same way against its archived scorer,
provenance/superseded-restart-contract/judge.py, and every superseded run must carry the
digest of the archived prompt. Every 1 s run is also graded by the pooled scorer kept in
provenance/superseded-pooled-f1/, which must match its entries exactly as the shipped judge
does. An arm at or above the 0.10 ceiling is reported as a failed
gate rather than hidden: the documents can be accurate about a task that does not pass.

Two controls run at the end: a sentinel that must NOT be found, and a real value with one
digit corrupted that must ALSO not be found. If either turns up, this file says its own
pass is meaningless rather than reporting success.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
ABL = TASK / "provenance" / "ablations"
OLD = TASK / "provenance" / "superseded-restart-contract"
sys.path.insert(0, str(TASK / "steps" / "solve" / "tests"))
sys.path.insert(0, str(ABL))
import judge  # noqa: E402
import make_ablation_prompt as mp  # noqa: E402
import run_ablations  # noqa: E402
from run_measured import OUT_NAME  # noqa: E402

DOCS = {p.name: p.read_text() for p in (TASK / "README.md", TASK / "SPEC.md", HERE / "scores.md")
        if p.exists()}
ROLLOUTS = HERE / "rollouts"
SUPERSEDED = ROLLOUTS / "superseded-restart-contract"
SHIPPED_SHA = hashlib.sha256((TASK / "steps" / "solve" / "instruction.md").read_bytes()).hexdigest()
OLD_SHA = hashlib.sha256((OLD / "instruction.md").read_bytes()).hexdigest()

checks: list[tuple[str, str, str]] = []


def claim(label: str, value, *docs: str) -> None:
    for doc in docs:
        checks.append((label, str(value), doc))


def found(value: str, text: str) -> bool:
    """Whole-number match: not flanked by a digit, nor by a decimal point inside a number."""
    return re.search(rf"(?<!\d)(?<!\d\.){re.escape(value)}(?!\d)(?!\.\d)", text) is not None


def corrupt(value: str) -> str:
    digits = [c for c in value if c.isdigit()]
    if not digits:
        return value + "9"
    last = len(value) - 1 - value[::-1].index(digits[-1])
    return value[:last] + str((int(value[last]) + 5) % 10) + value[last + 1:]


def turn_count(rollout: Path) -> int:
    """The shipped auditor's count. Exit 2 means a control failed and no count is trustworthy."""
    r = subprocess.run([sys.executable, str(HERE / "audit_trajectory.py"),
                        "--run-dir", "/workspace", "--rollout", str(rollout)],
                       capture_output=True, text=True)
    if r.returncode == 2:
        raise SystemExit(f"{rollout.name}: the auditor's controls failed\n{r.stdout}{r.stderr}")
    m = re.search(r"^tool calls: (\d+)", r.stdout, re.M)
    assert m, f"{rollout.name}: the auditor printed no turn count\n{r.stdout}{r.stderr}"
    return int(m.group(1))


def old_judge():
    spec = importlib.util.spec_from_file_location("old_judge", OLD / "judge.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def old_grade(oj, entries: list) -> float:
    preds = [oj._norm(e) for e in entries]
    tp = oj._max_monotonic(preds, oj._match)
    n_pred, n_gt = len(preds), len(oj.GROUND_TRUTH)
    p = tp / n_pred if n_pred else 0.0
    r = tp / n_gt if n_gt else 0.0
    return round(2 * p * r / (p + r), 4) if p + r else 0.0


def main() -> int:
    notes: list[str] = []
    pending: list[str] = []
    gates: list[str] = []

    # ---- the key --------------------------------------------------------------
    derived = json.loads((TASK / "provenance" / "dortmund_leverkusen.labels-derived.json").read_text())
    key = [{k: i[k] for k in ("t", "action", "team")} for i in derived["instances"]]
    assert key == judge.GROUND_TRUTH, "the derived key and judge.py's key have come apart"
    claim("actions in the key", len(key), "SPEC.md", "README.md")
    claim("Ball out of play in the key", derived["per_action"]["Ball out of play"], "SPEC.md")
    claim("clip length, minutes", f"{derived['clip_duration_sec'] / 60:.1f}", "SPEC.md")

    align = json.loads((TASK / "provenance" / "alignment.json").read_text())
    offsets = [align["halves"][h]["offset_sec"] for h in ("1", "2")]
    assert offsets == derived["half_offsets_sec"], "the key was built from other offsets"
    for h, off in zip((1, 2), offsets):
        claim(f"half {h} offset", f"{off:.3f}", "SPEC.md", "README.md")
    diag = align["diagnostics"]
    at012 = next(r for r in diag["threshold_sweep"] if r["threshold"] == 0.12)
    logo = [at012["halves"][h]["by_change_type"]["logo"] for h in ("1", "2")]
    assert all(x["matched"] == x["anchors"] for x in logo), "not every logo transition matched at 0.12"
    claim("logo transitions matched at 0.12", sum(x["matched"] for x in logo), "SPEC.md")
    worst = max(abs(t["median_residual_sec"]) for h in ("1", "2") for t in at012["halves"][h]["thirds"])
    assert worst <= 0.02, f"a third's median residual is {worst} s"
    for c in diag["chance_control"]:
        s = c["matched_by_offset_shift_sec"]
        claim(f"half {c['half']} matches at the offset", s["+0.0"], "SPEC.md")
        assert max(s["-2.0"], s["+2.0"]) <= 4 and min(s["-2.0"], s["+2.0"]) >= 1, s
    ab = diag["abrupt_peak_offsets"]
    claim("abrupt cut lag, low", f"{ab['min_sec']:.2f}", "SPEC.md")
    claim("abrupt cut lag, high", f"{ab['max_sec']:.2f}", "SPEC.md")

    # ---- the oracle that ships, and the empty submission ------------------------
    solve = (TASK / "steps" / "solve" / "solution" / "solve.sh").read_text()
    m = re.search(r"^ACTIONS_KEY = \[\n(.*?)^\]\n", solve, re.S | re.M)
    assert m, "solve.sh has no ACTIONS_KEY literal to grade"
    shipped = json.loads("[" + m.group(1).rstrip().rstrip(",") + "]")
    assert shipped == key and judge.score(shipped)["f1"] == 1.0, "the oracle that ships does not score 1.0"
    assert judge.score([])["f1"] == 0.0, "an empty submission no longer scores 0.0"
    for name, expected in (("oracle", 1.0), ("empty", 0.0)):
        path = ROLLOUTS / f"{name}-reward.json"
        if not path.exists():
            pending.append(f"{name} graded inside the image")
            continue
        got = json.loads(path.read_text())
        assert got["reward"] == expected and got["details"]["n_ground_truth"] == len(key), (
            f"{name} inside the image scored {got['reward']} against {got['details']['n_ground_truth']} entries")
        notes.append(f"  ok      {name} inside the image  {got['reward']}")

    # ---- deterministic baselines ------------------------------------------------
    det = run_ablations.run(str(TASK / "provenance" / "dortmund_leverkusen.labels-derived.json"))
    assert det["PASS_deterministic"], det
    claim("most common pair, spread evenly", f"{det['no_media']:.4f}", "SPEC.md", "README.md", "scores.md")
    claim("class mix, spread evenly", f"{det['class_mix']:.4f}", "scores.md")
    claim("random, mean", f"{det['random_mean']:.4f}", "SPEC.md", "README.md", "scores.md")
    claim("random, best", f"{det['random_max']:.4f}", "scores.md")

    # ---- measured ablations -------------------------------------------------------
    for mode, name in sorted(OUT_NAME.items()):
        d = ABL / "measured" / name
        if not (d / "answer.json").exists():
            pending.append(f"ablation {name}")
            continue
        details = json.loads((d / "details.json").read_text())
        assert (d / "prompt.md").read_text() == mp.build(mode), f"{name}: the prompt is not the derived one"
        assert details["shipped_prompt_sha256"] == SHIPPED_SHA, f"{name}: ran against a different shipped prompt"
        r = judge.score(json.loads((d / "answer.json").read_text())["sequence"])
        assert r["f1"] == json.loads((d / "reward.json").read_text())["reward"], f"{name}: regrade differs"
        assert details["shell_calls"] == 0, f"{name}: the run used shell calls"
        assert r["f1"] <= 0.15, f"{name}: {r['f1']} breaks the 0.15 ablation gate"
        claim(f"ablation {name}", f"{r['f1']:.4f}", "SPEC.md", "README.md", "scores.md")
        claim(f"ablation {name} entries", r["n_predicted"], "scores.md")
        notes.append(f"  ok      ablation {name:<20} {r['f1']:.4f}")

    # ---- the arms -----------------------------------------------------------------
    for arm in ("codex", "claude", "antigravity"):
        man_path = ROLLOUTS / f"{arm}-manifest.json"
        if not man_path.exists():
            pending.append(f"arm {arm}")
            continue
        man = json.loads(man_path.read_text())
        assert man["prompt_sha256"] == SHIPPED_SHA, f"{arm}: ran against a different prompt"
        assert man.get("one_session") is True, f"{arm}: not one agent in one session"
        sol = ROLLOUTS / f"{arm}-solution.json"
        assert hashlib.sha256(sol.read_bytes()).hexdigest() == man["solution_sha256"], (
            f"{arm}: the shipped solution is not the one the manifest recorded")
        r = judge.score(json.loads(sol.read_text())["sequence"])
        assert r["f1"] == json.loads((ROLLOUTS / f"{arm}-reward.json").read_text())["reward"], (
            f"{arm}: regrading the shipped solution disagrees with its reward.json")
        turns = turn_count(ROLLOUTS / man["trajectory"])
        assert turns > 50, f"{arm} ran {turns} tool calls, at or below the floor of 50"
        if r["f1"] >= 0.10:
            gates.append(f"{arm} scored {r['f1']:.4f}, at or above the 0.10 ceiling")
        claim(f"{arm} reward", f"{r['f1']:.4f}", "scores.md", "README.md")
        claim(f"{arm} entries", r["n_predicted"], "scores.md")
        claim(f"{arm} true positives", r["true_positives"], "scores.md")
        claim(f"{arm} tool calls", turns, "scores.md")
        notes.append(f"  ok      arm {arm:<12} {r['f1']:.4f} over {turns} tool calls")

    # ---- the pooled scorer the 1 s runs were made under -------------------------------
    pooled = TASK / "provenance" / "superseded-pooled-f1"
    if pooled.exists():
        spec = importlib.util.spec_from_file_location("judge_pooled", pooled / "judge.py")
        jp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(jp)
        assert jp.GROUND_TRUTH == judge.GROUND_TRUTH and jp.TOL == judge.TOL, (
            "the pooled scorer holds another key or tolerance")
        for arm in ("codex", "claude", "antigravity"):
            sol = ROLLOUTS / f"{arm}-solution.json"
            if not sol.exists():
                continue
            seq = json.loads(sol.read_text())["sequence"]
            old, new = jp.score(seq), judge.score(seq)
            assert (old["true_positives"], old["n_predicted"]) == (new["true_positives"], new["n_predicted"]), (
                f"{arm}: the pooled scorer matches entries differently from the shipped judge")
        notes.append("  ok      pooled scorer: matches every 1 s run's entries exactly as the shipped judge does")

    # ---- the superseded restart contract -------------------------------------------
    oj = old_judge()
    runs = [p for p in sorted(SUPERSEDED.rglob("*manifest*.json")) if "arm" in json.loads(p.read_text())]
    assert len(runs) >= 7, f"expected the seven superseded run manifests, found {len(runs)}"
    for p in runs:
        assert json.loads(p.read_text())["prompt_sha256"] == OLD_SHA, (
            f"{p.relative_to(ROLLOUTS)} was not run against the archived prompt")
    r = old_grade(oj, json.loads((SUPERSEDED / "codex-solution.json").read_text())["sequence"])
    assert r == json.loads((SUPERSEDED / "codex-reward.json").read_text())["reward"], "superseded Codex regrade differs"
    claim("superseded contract, Codex reward", f"{r:.4f}", "scores.md")
    claim("superseded contract, Codex tool calls", turn_count(SUPERSEDED / "codex.jsonl"), "scores.md")
    for name in ("no_media", "single_frame", "frame_dump_no_tools"):
        d = OLD / "ablations" / "measured" / name
        assert json.loads((d / "details.json").read_text())["shipped_prompt_sha256"] == OLD_SHA, name
        r = old_grade(oj, json.loads((d / "answer.json").read_text())["sequence"])
        assert r == json.loads((d / "reward.json").read_text())["reward"], f"superseded {name} regrade differs"
    for run, trajectory in (("first-budget/claude-1", "claude.jsonl"), ("first-budget/codex-2", "codex.jsonl"),
                            ("first-budget/claude-2", "claude.jsonl"), ("claude-3h-stopped", "claude.jsonl")):
        d = SUPERSEDED / run
        man = json.loads((d / "manifest.json").read_text())
        assert not man["solution_written"], f"{run} is filed as a run with no answer"
        assert json.loads((d / "reward.json").read_text())["reward"] == 0.0, f"{run}: no answer must score 0.0"
        turns = turn_count(d / trajectory)
        assert turns > 50, f"{run} ran {turns} tool calls"
        claim(f"superseded {run}, tool calls", turns, "scores.md")
    claim("superseded Codex first attempt, tool calls",
          turn_count(SUPERSEDED / "not-reported" / "codex-attempt-1.jsonl"), "scores.md")
    agy = sorted((SUPERSEDED / "not-reported" / "antigravity-attempt-1").glob("main-*.jsonl"))
    claim("superseded Antigravity first attempt, tool calls", turn_count(agy[0]), "scores.md")
    notes.append("  ok      superseded contract: prompt digest, Codex and ablation regrades, no-answer runs")

    # ---- the superseded 2 s ledger ------------------------------------------------
    two_rollouts = ROLLOUTS / "superseded-2s-tolerance"
    two_src = TASK / "provenance" / "superseded-2s-tolerance"
    if two_src.exists():
        two_sha = hashlib.sha256((two_src / "instruction.md").read_bytes()).hexdigest()
        spec = importlib.util.spec_from_file_location("judge_2s", two_src / "judge.py")
        j2 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(j2)
        assert j2.TOL == 2 and judge.TOL == 1, f"the archived scorer is {j2.TOL} s and the shipped one {judge.TOL} s"
        for p in sorted(two_rollouts.glob("*manifest*.json")):
            man = json.loads(p.read_text())
            if "arm" not in man:
                continue
            arm = man["arm"]
            assert man["prompt_sha256"] == two_sha, f"2 s {arm} was not run against the archived 2 s prompt"
            sol = two_rollouts / f"{arm}-solution.json"
            if not sol.exists():
                continue
            r = j2.score(json.loads(sol.read_text())["sequence"])["f1"]
            assert r == json.loads((two_rollouts / f"{arm}-reward.json").read_text())["reward"], (
                f"2 s {arm}: regrade differs")
            turn_count(two_rollouts / f"{arm}.jsonl")  # the auditor must still be able to read it
        for name in ("no_media", "single_frame", "frame_dump_no_tools"):
            d = two_src / "ablations" / "measured" / name
            if not (d / "answer.json").exists():
                continue
            assert json.loads((d / "details.json").read_text())["shipped_prompt_sha256"] == two_sha, name
            r = j2.score(json.loads((d / "answer.json").read_text())["sequence"])["f1"]
            assert r == json.loads((d / "reward.json").read_text())["reward"], f"2 s {name}: regrade differs"
        notes.append("  ok      2 s ledger: prompt digest, run and ablation regrades under the archived scorer")

    # ---- controls -------------------------------------------------------------
    sentinel = "0.deadbeef-not-in-any-document"
    assert not any(sentinel in t for t in DOCS.values()), "the sentinel is not a sentinel"
    real = [(lbl, val, doc) for lbl, val, doc in checks if any(c.isdigit() for c in val)]
    neg_label, neg_value, neg_doc = next(x for x in real if len(x[1]) >= 4)
    negative = corrupt(neg_value)
    if found(negative, DOCS.get(neg_doc, "")):
        raise SystemExit(f"CONTROL FAILED: the corrupted value {negative} was found in {neg_doc}, "
                         f"so a wrong number would have passed here")

    missing = []
    for label, value, doc in checks:
        if doc in DOCS and found(value, DOCS[doc]):
            print(f"  ok      {label:<48} = {value}   ({doc})")
        else:
            missing.append(f"  WRONG   {label:<48} = {value}   not found in {doc}")
    print("\n".join(notes))
    if pending:
        print("  NOT MEASURED YET: " + ", ".join(pending))
    for g in gates:
        print(f"  GATE FAILED  {g}")
    if missing:
        print("\n".join(missing))
        raise SystemExit(f"{len(missing)} claim(s) the artifacts do not back")
    print(f"\n{len(checks)} claims recomputed and found; controls held "
          f"({neg_label} corrupted to {negative} was not found).")
    return 1 if (pending or gates) else 0


if __name__ == "__main__":
    raise SystemExit(main())
