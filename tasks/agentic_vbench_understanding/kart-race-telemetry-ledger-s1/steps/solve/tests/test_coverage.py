#!/usr/bin/env python3
"""Regression tests for judge.py. Pure stdlib; runs judge.py exactly as the harness does.

Covers the coverage model and the reviewer-reported scorer bugs:
  * full oracle (mid-window t)                          -> 1.0
  * full oracle reporting every race at its t_start     -> 1.0   (assignment-safe matching: the
      prompt permits t at race start; overlapping +/-15 s windows must not strand a race)
  * a correct 2-of-12 subset                            -> ~2/12 (partial answers cannot score 1.0)
  * 2 real races + 10 time-matched {track,t} placeholders -> ~2/12 (placeholders carry no scored value)
  * PER-DIMENSION coverage: a correct items-only answer earns honest items credit (0.55) and skid 0;
      adding a dummy skid_time:0 neither raises nor lowers it (0.55), and a correct skid-only answer
      earns 0.45 -- an omitted field zeroes only its own dimension.
  * non-finite scored values (nan/inf) are not counted as that dimension's value (that dimension ->
      coverage 0, score 0); the other, honest field keeps its credit; both-fields-nonfinite -> 0.
  * malformed races (null / non-list) normalize to [] and score 0 without crashing.
  * empty answer -> 0.

Run: `python3 test_coverage.py` (exit 0 = pass).
"""
import json, os, re, subprocess, sys, tempfile, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
JUDGE = HERE / "judge.py"
TEST_SH = HERE / "test.sh"                       # the verifier: reads /workspace/output/solution.json
SOLVE_SH = HERE.parent / "solution" / "solve.sh"  # the oracle
GT = json.loads((HERE / "ground_truth.json").read_text())["races"]
N = len(GT)
W_ITEMS, W_SKID = 0.55, 0.45  # must match judge.DIMS


def score(sol):
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "sol.json").write_text(json.dumps(sol))
        p = subprocess.run([sys.executable, str(JUDGE), "--solution", str(d / "sol.json"),
                            "--reward-json", str(d / "r.json"), "--reward-txt", str(d / "r.txt")],
                           capture_output=True, text=True)
        if p.returncode != 0:
            raise AssertionError(f"judge.py CRASHED (rc={p.returncode}): {p.stderr.strip()[-300:]}")
        return json.loads((d / "r.json").read_text())


def _mid(r):
    return round((r["t_start"] + r["t_end"]) / 2, 1)


def oracle(times="mid", n=None):
    rows = GT if n is None else GT[:n]
    t_of = (lambda r: _mid(r)) if times == "mid" else (lambda r: r["t_start"])
    return {"races": [{"track": r["track"], "t": t_of(r),
                       "items_collected": r["items_collected"], "skid_time": r["skid_time"]} for r in rows]}


def placeholders(k=2):
    real = oracle("mid", k)["races"]
    ph = [{"track": r["track"], "t": _mid(r)} for r in GT[k:]]
    return {"races": real + ph}


def one_field(field):
    """Correct values for `field` only (the other scored field omitted)."""
    return {"races": [{"track": r["track"], "t": _mid(r), field: r[field]} for r in GT]}


def field_value(field, value):
    """Correct values everywhere, but `field` forced to `value` for every race."""
    def row(r):
        d = {"track": r["track"], "t": _mid(r),
             "items_collected": r["items_collected"], "skid_time": r["skid_time"]}
        d[field] = value
        return d
    return {"races": [row(r) for r in GT]}


def subset(idxs, times="mid"):
    """A partial answer: exactly the GT races at `idxs`, with correct values, placed at each race's
    mid-window or its permitted t_start."""
    t_of = (lambda r: _mid(r)) if times == "mid" else (lambda r: r["t_start"])
    return {"races": [{"track": GT[i]["track"], "t": t_of(GT[i]),
                       "items_collected": GT[i]["items_collected"], "skid_time": GT[i]["skid_time"]} for i in idxs]}


def solve_sh_default_path():
    """The default OUT path baked into solve.sh (SOLUTION_PATH fallback)."""
    m = re.search(r"SOLUTION_PATH:-([^}]+)\}", SOLVE_SH.read_text())
    return m.group(1).strip() if m else None


def verifier_read_path():
    """The --solution path the verifier (test.sh) reads."""
    m = re.search(r"--solution\s+(\S+)", TEST_SH.read_text())
    return m.group(1).strip() if m else None


def oracle_via_solve_sh():
    """End-to-end: run solve.sh (writing to a temp SOLUTION_PATH), score its output through judge.py."""
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "out" / "solution.json"
        env = dict(os.environ, SOLUTION_PATH=str(out))
        subprocess.run(["bash", str(SOLVE_SH)], env=env, check=True, capture_output=True)
        rj, rt = Path(d) / "r.json", Path(d) / "r.txt"
        subprocess.run([sys.executable, str(JUDGE), "--solution", str(out),
                        "--reward-json", str(rj), "--reward-txt", str(rt)], check=True, capture_output=True)
        return json.loads(rj.read_text())["reward"]


def main():
    full = score(oracle("mid"))
    tstart = score(oracle("tstart"))
    part = score(oracle("mid", 2))
    padded = score(placeholders(2))
    items_only = score(one_field("items_collected"))
    items_dummy = score({"races": [{"track": r["track"], "t": _mid(r),
                                    "items_collected": r["items_collected"], "skid_time": 0} for r in GT]})
    skid_only = score(one_field("skid_time"))
    nan_skid = score(field_value("skid_time", "nan"))
    inf_items = score(field_value("items_collected", float("inf")))
    both_nan = score({"races": [{"track": r["track"], "t": _mid(r),
                                 "items_collected": "nan", "skid_time": "inf"} for r in GT]})
    null_races = score({"races": None})
    malformed = score({"races": {"oops": 1}})
    empty = score({"races": []})

    # partial t_start (contiguous shared boundaries): an exact partial answer at t_start must land on
    # the SAME races as the mid-window answer, not shift backward onto the preceding race.
    part_tstart = score(subset([3, 4], "tstart"))
    part_mid = score(subset([3, 4], "mid"))
    part3_tstart = score(subset([3, 4, 5], "tstart"))
    part3_mid = score(subset([3, 4, 5], "mid"))

    # matcher must stay bounded under a flood of junk prediction rows.
    real = subset(list(range(N)))["races"]
    junk = [{"track": "x", "t": 100000 + i, "items_collected": i, "skid_time": i} for i in range(2000)]
    t0 = time.time()
    flood = score({"races": real + junk})
    flood_dt = time.time() - t0

    # end-to-end oracle path: solve.sh writes where the verifier reads, and that output scores 1.0.
    def_path, ver_path = solve_sh_default_path(), verifier_read_path()
    oracle_e2e = oracle_via_solve_sh()

    def dim(res, field, key):
        return res["details"]["dims"][field][key]

    checks = [
        ("full oracle (mid t) == 1.0", abs(full["reward"] - 1.0) < 1e-6, f"{full['reward']}"),
        ("oracle at t_start == 1.0 (assignment-safe)", abs(tstart["reward"] - 1.0) < 1e-6,
         f"reward={tstart['reward']} cov={tstart['details']['coverage']}"),
        ("2-of-%d subset ~= 2/%d" % (N, N), abs(part["reward"] - 2.0 / N) < 0.02, f"{part['reward']}"),
        ("2 real + %d placeholders ~= 2/%d" % (N - 2, N), abs(padded["reward"] - 2.0 / N) < 0.02,
         f"{padded['reward']}"),
        # per-dimension coverage
        ("items-only earns honest items credit (~0.55)", abs(items_only["reward"] - W_ITEMS) < 0.02,
         f"reward={items_only['reward']} items_cov={dim(items_only,'items_collected','coverage')} "
         f"skid_cov={dim(items_only,'skid_time','coverage')}"),
        ("dummy skid_time:0 does NOT change items-only", abs(items_dummy["reward"] - items_only["reward"]) < 1e-6,
         f"items_only={items_only['reward']} with_dummy={items_dummy['reward']}"),
        ("skid-only earns honest skid credit (~0.45)", abs(skid_only["reward"] - W_SKID) < 0.02,
         f"reward={skid_only['reward']}"),
        # non-finite: the bad field's dimension is zeroed, the honest field keeps credit
        ("skid='nan' -> skid dim coverage 0 & score 0", dim(nan_skid, "skid_time", "coverage") == 0.0
         and dim(nan_skid, "skid_time", "score") == 0.0, f"skid={nan_skid['details']['dims']['skid_time']}"),
        ("skid='nan' keeps honest items credit (~0.55)", abs(nan_skid["reward"] - W_ITEMS) < 0.02,
         f"{nan_skid['reward']}"),
        ("items=inf -> items dim coverage 0 & score 0", dim(inf_items, "items_collected", "coverage") == 0.0
         and dim(inf_items, "items_collected", "score") == 0.0,
         f"items={inf_items['details']['dims']['items_collected']}"),
        ("items=inf keeps honest skid credit (~0.45)", abs(inf_items["reward"] - W_SKID) < 0.02,
         f"{inf_items['reward']}"),
        ("both fields non-finite -> 0", both_nan["reward"] == 0.0, f"{both_nan['reward']}"),
        # malformed / empty do not crash and score 0
        ("races=null -> 0 (no crash)", null_races["reward"] == 0.0, f"{null_races['reward']}"),
        ("races={...} malformed -> 0 (no crash)", malformed["reward"] == 0.0, f"{malformed['reward']}"),
        ("empty == 0.0", empty["reward"] == 0.0, f"{empty['reward']}"),
        # partial t_start must not shift backward across shared boundaries (half-open segments)
        ("partial rows 4-5 at t_start > 0 (was 0.0)", part_tstart["reward"] > 0.05, f"{part_tstart['reward']}"),
        ("partial rows 4-5 at t_start == mid placement", abs(part_tstart["reward"] - part_mid["reward"]) < 1e-9,
         f"tstart={part_tstart['reward']} mid={part_mid['reward']}"),
        ("partial rows 4-6 at t_start == mid placement", abs(part3_tstart["reward"] - part3_mid["reward"]) < 1e-9,
         f"tstart={part3_tstart['reward']} mid={part3_mid['reward']}"),
        # bounded matcher: a flood of junk rows must not change the score or blow the timeout
        ("12 real + 2000 junk rows -> 1.0", abs(flood["reward"] - 1.0) < 1e-6, f"{flood['reward']}"),
        ("matcher bounded under flood (< 10 s)", flood_dt < 10.0, f"{flood_dt:.2f}s"),
        # end-to-end oracle path: solve.sh writes where the verifier reads, and it scores 1.0
        ("solve.sh default path == verifier read path", def_path == ver_path and def_path is not None,
         f"solve={def_path} verifier={ver_path}"),
        ("oracle via solve.sh output == 1.0", abs(oracle_e2e - 1.0) < 1e-6, f"{oracle_e2e}"),
    ]
    ok = True
    for name, passed, detail in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}  ({detail})")
        ok = ok and passed
    if not ok:
        sys.exit("REGRESSION FAILED")
    print(f"all {len(checks)} coverage/scorer regression checks passed")


if __name__ == "__main__":
    main()
