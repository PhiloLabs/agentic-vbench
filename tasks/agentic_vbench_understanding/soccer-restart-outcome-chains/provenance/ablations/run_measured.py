#!/usr/bin/env python3
"""Run one degraded-input ablation and keep what it produced.

    python3 provenance/ablations/run_measured.py --mode no_media     --image <image>
    python3 provenance/ablations/run_measured.py --mode single_frame --image <image>
    python3 provenance/ablations/run_measured.py --mode frame_dump   --image <image>

The family's ablation gate asks what a strong model scores when the video is taken away.
Three degraded inputs are measured: none at all, one still, and eight contact sheets of
128 frames spread evenly across the clip, with no way to ask for another. All three are
forced to answer, because a zero from a model that declined to guess says nothing about
whether the degraded input was enough, which is the question.

The still and the sheets are cut from the baked media inside a container built from the
task image, so what the model sees came from the file the agent sees and not from a copy
that has drifted. The prompt is derived by make_ablation_prompt.py from the shipped
instruction.md, which asserts that the question is carried over unchanged. Two things are
checked afterwards rather than assumed: the run made no shell calls, since "no tools" is
an instruction a model could ignore, and the answer was not empty.

Ported from the CaptainCook4D task's ablation runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE.parent.parent
sys.path.insert(0, str(TASK / "steps" / "solve" / "tests"))
sys.path.insert(0, str(HERE))
import judge  # noqa: E402
import make_ablation_prompt as mp  # noqa: E402

MODEL, EFFORT = "gpt-5.6-sol", "xhigh"
OUT_NAME = {"no_media": "no_media", "single_frame": "single_frame",
            "frame_dump": "frame_dump_no_tools"}
BAKED = "/baked/game.mp4"
DURATION = 6426.52


def sh(*a, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(list(a), capture_output=True, text=True, **kw)


def grade(entries: list) -> dict:
    """judge.py's own scoring, applied to a list of entries."""
    return judge.score(entries)


def cut_media(mode: str, image: str, dest: Path) -> list[Path]:
    """Cut the still or the sheets out of the image's own baked media."""
    if mode == "no_media":
        return []
    # One CPU is plenty for cutting a few frames, and a limit keeps this short-lived
    # container from counting as the whole engine in an arm's capacity check.
    cid = sh("docker", "run", "-d", "--platform", "linux/arm64", "--cpus", "1", image,
             "sleep", "infinity", check=True).stdout.strip()
    try:
        if mode == "single_frame":
            names = ["still.jpg"]
            cmds = [f"ffmpeg -nostdin -loglevel error -ss {mp.SINGLE_FRAME_T} -i {BAKED} "
                    f"-frames:v 1 -vf scale=1024:-2 -q:v 3 -y /tmp/still.jpg"]
        else:
            names, cmds = [], []
            n = mp.SHEETS * mp.PER_SHEET
            for s in range(mp.SHEETS):
                parts = []
                for k in range(mp.PER_SHEET):
                    t = DURATION * (s * mp.PER_SHEET + k + 0.5) / n  # midpoint of its span
                    parts.append(
                        f"ffmpeg -nostdin -loglevel error -ss {t:.3f} -i {BAKED} -frames:v 1 "
                        f"-vf \"scale=480:-2,drawtext=text='t={t:.0f}':x=8:y=8:fontsize=28:"
                        f"fontcolor=yellow:box=1:boxcolor=black@0.6:boxborderw=4\" "
                        f"-q:v 3 -y /tmp/s{s}_{k:02d}.jpg")
                ins = " ".join(f"-i /tmp/s{s}_{k:02d}.jpg" for k in range(mp.PER_SHEET))
                chain = "".join(f"[{k}:v]" for k in range(mp.PER_SHEET))
                parts.append(
                    f"ffmpeg -nostdin -loglevel error {ins} -filter_complex "
                    f"\"{chain}concat=n={mp.PER_SHEET}:v=1:a=0[c];[c]tile=4x4:margin=4:padding=4\" "
                    f"-frames:v 1 -q:v 3 -y /tmp/sheet_{s}.jpg")
                names.append(f"sheet_{s}.jpg")
                cmds.append(" && ".join(parts))
        for name, cmd in zip(names, cmds):
            r = sh("docker", "exec", cid, "sh", "-lc", cmd)
            assert r.returncode == 0, f"{name}: {(r.stderr or r.stdout)[-300:]}"
            sh("docker", "cp", f"{cid}:/tmp/{name}", str(dest / name), check=True)
    finally:
        sh("docker", "rm", "-f", cid)
    made = [dest / name for name in names]
    for f in made:
        assert f.is_file() and f.stat().st_size > 5000, f"{f.name} is missing or not an image"
    return made


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=sorted(OUT_NAME))
    ap.add_argument("--image", required=True)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    out = args.out or (HERE / "measured" / OUT_NAME[args.mode])
    out.mkdir(parents=True, exist_ok=True)

    oracle = [dict(g) for g in judge.GROUND_TRUTH]
    assert grade(oracle)["f1"] == 1.0 and grade([])["f1"] == 0.0, "grade() is not judge.py's arithmetic"

    prompt = mp.build(args.mode)
    (out / "prompt.md").write_text(prompt)
    version = " ".join(sh("codex", "--version").stdout.split()) or "unknown"

    with tempfile.TemporaryDirectory() as td:
        work, media = Path(td) / "work", Path(td) / "media"
        work.mkdir()
        media.mkdir()
        images = cut_media(args.mode, args.image, media)
        # The frames are broadcast footage, so they are not committed. Their digests are,
        # and cut_media reproduces them from the digest-checked baked file.
        image_digests = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in images}
        argv = ["codex", "exec", "--json", "-m", MODEL, "-c", f'model_reasoning_effort="{EFFORT}"',
                "--sandbox", "read-only", "--skip-git-repo-check", "--cd", str(work)]
        for f in images:
            argv += ["-i", str(f)]
        print(f"{args.mode}: {len(images)} image(s), running {MODEL} at {EFFORT}")
        run = subprocess.run(argv, input=prompt, capture_output=True, text=True, timeout=7200)
        text = run.stdout.replace(td, "/tmp/ablation").replace(str(Path.home()), "/home/user")
        (out / "transcript.jsonl").write_text(text)

    seq = None
    for line in reversed(text.splitlines()):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        item = rec.get("item") or {}
        if rec.get("type") != "item.completed" or item.get("type") != "agent_message":
            continue
        body = item.get("text") or ""
        start, end = body.find("{"), body.rfind("}")
        if start < 0 or end <= start:
            continue
        try:
            seq = json.loads(body[start:end + 1]).get("sequence")
        except Exception:
            seq = None
        if seq:
            break
    assert seq, (f"no sequence could be read out of the run's final message; the transcript "
                 f"is kept at {out / 'transcript.jsonl'}")
    (out / "answer.json").write_text(json.dumps({"sequence": seq}, indent=1) + "\n")

    # "No tools" is an instruction the model could ignore, so it is checked.
    shells = text.count('"type":"command_execution"')
    details = grade(seq)
    (out / "reward.json").write_text(json.dumps({"reward": details["f1"]}, indent=2) + "\n")
    (out / "details.json").write_text(json.dumps({
        **details,
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": MODEL, "reasoning_effort": EFFORT, "harness_version": version,
        "mode": args.mode, "exit_code": run.returncode,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "shipped_prompt_sha256": hashlib.sha256(mp.SHIPPED.read_bytes()).hexdigest(),
        "images": len(images), "image_sha256": image_digests, "shell_calls": shells,
    }, indent=2) + "\n")

    print(f"  reward {details['f1']:.4f}  entries {len(seq)}  true positives {details['true_positives']}  "
          f"action+time {details['action_time_matches']}  shell calls {shells}")
    assert shells == 0, f"the run made {shells} shell calls; it was told it had no tools"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
