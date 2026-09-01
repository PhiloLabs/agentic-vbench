#!/usr/bin/env python3
"""Run one degraded-input ablation and keep what it produced.

    python3 provenance/ablations/run_measured.py --mode no_media     --image cc4d:pinned
    python3 provenance/ablations/run_measured.py --mode single_frame --image cc4d:pinned
    python3 provenance/ablations/run_measured.py --mode frame_dump   --image cc4d:pinned

The family's ablation gate asks what a strong model scores when the video is taken away.
Three degraded inputs are measured: none at all, one still per recording, and a contact
sheet of sixteen frames per recording with no way to ask for another. All three are forced
to answer, because a zero from a model that declined to guess says nothing about whether
the degraded input was enough, which is the question.

The stills and the sheets are cut from the same baked media the image ships, inside a
container built from that image, so what the model sees came from the recordings the agent
sees and not from a copy that has drifted. The prompt is derived by make_ablation_prompt.py
from the shipped instruction.md, which asserts that everything but the media paragraph is
carried over unchanged.

Two things are checked afterwards rather than assumed: the run made no shell calls, since
"no tools" is an instruction the model could ignore, and the answer was not empty.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import hashlib
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE.parent.parent
sys.path.insert(0, str(TASK / "steps" / "solve" / "tests"))
import judge  # noqa: E402

MODEL, EFFORT = "gpt-5.6-sol", "xhigh"
OUT_NAME = {"no_media": "no_media", "single_frame": "single_frame",
            "frame_dump": "frame_dump_no_tools"}


def sh(*a, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(list(a), capture_output=True, text=True, **kw)


def cut_media(mode: str, image: str, dest: Path) -> list[Path]:
    """Cut the stills or the sheets out of the image's own baked media."""
    if mode == "no_media":
        return []
    key = json.loads((TASK / "provenance" / "step-derived.json").read_text())
    spans = {v["letter"]: v["duration_sec"] for v in key["videos"]}
    cid = sh("docker", "run", "-d", "--platform", "linux/arm64", image,
             "sleep", "infinity", check=True).stdout.strip()
    try:
        for letter, dur in sorted(spans.items()):
            if mode == "single_frame":
                cmd = (f'ffmpeg -nostdin -loglevel error -ss {dur/2:.3f} -i /baked/{letter}.mp4 '
                       f'-frames:v 1 -vf scale=1024:-2 -q:v 3 -y /tmp/{letter}.jpg')
            else:
                # Sixteen frames evenly across the whole recording, timestamp burned into
                # each, tiled 4x4 and read left to right, exactly as the prompt says.
                parts = []
                for k in range(16):
                    t = dur * (k + 0.5) / 16.0   # midpoint of the k-th of 16 equal spans
                    parts.append(
                        f'ffmpeg -nostdin -loglevel error -ss {t:.3f} -i /baked/{letter}.mp4 '
                        f'-frames:v 1 -vf "scale=480:-2,drawtext=text=\'{t:.0f}s\':x=8:y=8:'
                        f'fontsize=28:fontcolor=yellow:box=1:boxcolor=black@0.6:boxborderw=4" '
                        f'-q:v 3 -y /tmp/{letter}_{k:02d}.jpg')
                ins = " ".join(f"-i /tmp/{letter}_{k:02d}.jpg" for k in range(16))
                chain = "".join(f"[{k}:v]" for k in range(16))
                parts.append(
                    f'ffmpeg -nostdin -loglevel error {ins} -filter_complex '
                    f'"{chain}concat=n=16:v=1:a=0[c];[c]tile=4x4:margin=4:padding=4" '
                    f'-frames:v 1 -q:v 3 -y /tmp/{letter}.jpg')
                cmd = " && ".join(parts)
            r = sh("docker", "exec", cid, "sh", "-lc", cmd)
            assert r.returncode == 0, f"{letter}: {(r.stderr or r.stdout)[-300:]}"
            sh("docker", "cp", f"{cid}:/tmp/{letter}.jpg", str(dest / f"{letter}.jpg"), check=True)
    finally:
        sh("docker", "rm", "-f", cid)
    made = sorted(dest.glob("*.jpg"))
    assert len(made) == len(spans), f"cut {len(made)} images for {len(spans)} recordings"
    for f in made:
        assert f.stat().st_size > 5000, f"{f.name} is {f.stat().st_size} bytes, not an image"
    return made


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True, choices=sorted(OUT_NAME))
    ap.add_argument("--image", default="cc4d:pinned")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    out = args.out or (HERE / "measured" / OUT_NAME[args.mode])
    out.mkdir(parents=True, exist_ok=True)

    prompt_path = out / "prompt.md"
    r = sh(sys.executable, str(HERE / "make_ablation_prompt.py"),
           "--mode", args.mode, "--out", str(prompt_path))
    assert r.returncode == 0, f"could not build the prompt: {r.stderr[-400:]}"
    prompt = prompt_path.read_text()

    with tempfile.TemporaryDirectory() as td:
        work, media = Path(td) / "work", Path(td) / "media"
        work.mkdir(); media.mkdir()
        images = cut_media(args.mode, args.image, media)
        argv = ["codex", "exec", "--json", "-m", MODEL,
                "-c", f'model_reasoning_effort="{EFFORT}"',
                "--skip-git-repo-check", "--cd", str(work)]
        for f in images:
            argv += ["-i", str(f)]
        print(f"{args.mode}: {len(images)} image(s), running {MODEL} at {EFFORT}")
        run = subprocess.run(argv, input=prompt, capture_output=True, text=True, timeout=7200)
        (out / "transcript.jsonl").write_text(run.stdout)

    text = run.stdout
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
    assert seq, (
        "no sequence could be read out of the run's agent_message; the transcript is "
        f"kept at {out / 'transcript.jsonl'}")
    (out / "answer.json").write_text(json.dumps({"sequence": seq}, indent=1) + "\n")

    # "No tools" is an instruction the model could ignore, so it is checked.
    shells = text.count('"type":"command_execution"') + text.count('"shell"')
    details = judge.grade(seq)
    # The run is stamped with when it happened and which prompt it answered. These
    # directories are rewritten in place across rounds, and a reader with no stamp cannot
    # tell a fresh result from one left over from the previous contract; a watcher keyed
    # on the file merely existing reported last round's numbers as this round's once.
    (out / "reward.json").write_text(json.dumps({"reward": details["f1"]}, indent=2) + "\n")
    (out / "details.json").write_text(json.dumps({
        **details,
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": MODEL, "reasoning_effort": EFFORT, "mode": args.mode,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "shipped_prompt_sha256": hashlib.sha256(
            (TASK / "steps" / "solve" / "instruction.md").read_bytes()).hexdigest(),
        "images": len(images), "shell_calls": shells,
    }, indent=2) + "\n")

    print(f"  reward {details['f1']:.4f}  entries {len(seq)}  "
          f"label+order {details['label_and_order_only_matches']}  shell calls {shells}")
    assert shells == 0, f"the run made {shells} shell calls; it was told it had no tools"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
