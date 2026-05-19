"""Shared core for duplicate-frame glitch injection task generators.

Both `build_glitch_dup_short.py` and `build_glitch_dup_long.py` call
`build_task()` with task-specific parameters (source mp4, dup length,
task name).

Pipeline:
  1. Sample 60 s from source at offset 5 s, scale to 480p, keep source fps.
  2. Decode to PNG frames, pick 2 random injection points (seed 42).
     At each point P, hold frame P for `dup_len` additional output frames
     (freeze / stuck-frame stutter).
  3. Re-encode to `corrupted.mp4`. Save GT freeze ranges (post-injection
     frame indices of the redundant copies) to `tests/cuts.json`.
  4. Write full Harbor task dir (task.toml, Dockerfile, instruction, judge,
     setup, oracle solve.sh with baked-in GT).
"""
from __future__ import annotations

import json
import random
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent  # experiment/
TASKS_DIR = REPO_ROOT / "tasks" / "agentic_vbench_repair"
SOURCES_DIR = REPO_ROOT / "sources"

CLIP_OFFSET_SEC = 5  # skip first 5 s (intro frame, fade-in, etc.)
CLIP_DURATION_SEC_DEFAULT = 60  # legacy default; per-task scripts override
TARGET_HEIGHT = 480  # 480p; width auto-scaled to preserve aspect
SEED = 42
N_INJECTIONS = 2


TASK_TOML = """\
version = "1.0"

[task]
name = "agentic-vbench/{task_name}"

[metadata]
difficulty = "medium"
category = "video-glitch-repair"
tags = ["glitch", "duplicated-frame", "video-restoration", "frame-detect"]
source = "{source_name}"
license = "unknown-research-use-only"
attribution = "see source URL"

[environment]
build_timeout_sec = 600.0
cpus = 2
memory_mb = 4096
storage_mb = 8192
allow_internet = true

[[steps]]
name = "solve"

[steps.agent]
timeout_sec = 1800.0

[steps.verifier]
timeout_sec = 600.0
"""


DOCKERFILE = """\
FROM --platform=linux/amd64 python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \\
        ffmpeg \\
        ca-certificates \\
    && rm -rf /var/lib/apt/lists/*

# Precision cut verifier deps: numpy + scikit-image (SSIM honesty gate);
# opencv-python-headless retained for agents that want frame I/O.
RUN pip install --no-cache-dir \\
        "numpy<3" \\
        "opencv-python-headless==4.13.*" \\
        "scikit-image>=0.22,<1.0"

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
"""


INSTRUCTION_MD = """\
# Frozen-Frame Fix

I have a video that stutters at a couple of spots — the picture freezes in
place for a stretch, the action stops, then it picks up again. Outside
those spots the playback is smooth. The audio may or may not stay in sync
through the stuck parts.

Find the frozen stretches and cut them out cleanly so the surrounding
content joins smoothly, with audio and video in sync from start to end.
Don't try to fill in motion that isn't there; just remove the redundant
frames.

## What to deliver

- `/workspace/output/output.mp4` — H.264 / yuv420p, same fps and
  dimensions as the input. Audio track (AAC) preserved. Length should
  equal the input length minus the duration of what you removed.
- `/workspace/output/cuts.json` — list of the frozen stretches you
  removed:
  ```json
  {{
    "glitches": [
      {{"type": "duplicated", "start_frame": S, "end_frame": E}}
    ]
  }}
  ```
  `start_frame` / `end_frame` are 0-indexed frame numbers in the **input**
  video; inclusive start, exclusive end (the range `[S, E)` is what you
  removed).

## Environment

- CPU only, ~30 min timeout. Internet available for `pip install`.
"""


SETUP_SH = """\
#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

mkdir -p /workspace/materials /workspace/output /workspace/work
cp "$HERE/corrupted.mp4" /workspace/materials/corrupted.mp4

if [ ! -s /workspace/materials/corrupted.mp4 ]; then
    echo "ERROR: corrupted.mp4 missing or empty" >&2
    exit 1
fi

mkdir -p /logs/artifacts
ffprobe -v error -show_entries stream=nb_read_frames,r_frame_rate,duration \\
        -count_frames -select_streams v:0 \\
        /workspace/materials/corrupted.mp4 \\
        > /logs/artifacts/input-probe.txt 2>&1 || true

rm -rf -- "$HERE/corrupted.mp4" "$0"
"""


TEST_SH = """\
#!/bin/bash
# Precision cut verifier: per-cut range gate + global SSIM honesty gate
# + audio xcorr gate. No transcription.
set -euo pipefail

mkdir -p /logs/verifier /logs/artifacts

if [ -d /workspace/output ]; then
    cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
fi

python3 -c "import skimage, numpy" 2>/dev/null || \\
    pip install --quiet --no-cache-dir "numpy<3" "scikit-image>=0.22,<1.0"

python3 /tests/judge.py \\
        --source-mp4 /workspace/materials/corrupted.mp4 \\
        --output-mp4 /workspace/output/output.mp4 \\
        --output-cuts /workspace/output/cuts.json \\
        --gt-cuts /tests/cuts.json \\
        --reward-json /logs/verifier/reward.json \\
        --reward-txt /logs/verifier/reward.txt
"""


JUDGE_PY_TEMPLATE = """\
#!/usr/bin/env python3
\"\"\"Precision cut judge for agentic-vbench glitch-dup tasks.

Generated by experiment/scripts/_glitch_dup_core.py. The verifier core is
embedded below; do not edit this file by hand.

GT and submission use frame indices (start_frame / end_frame). The
verifier converts them to seconds using GT.fps before applying the
range and honesty gates.
\"\"\"
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

# ---- BEGIN EMBEDDED VERIFIER CORE ----
{verifier_core_source}
# ---- END EMBEDDED VERIFIER CORE ----


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source-mp4", required=True, type=Path)
    p.add_argument("--output-mp4", required=True, type=Path)
    p.add_argument("--output-cuts", required=True, type=Path)
    p.add_argument("--gt-cuts", required=True, type=Path)
    p.add_argument("--reward-json", required=True, type=Path)
    p.add_argument("--reward-txt", required=True, type=Path)
    args = p.parse_args()

    if args.output_cuts.exists():
        try:
            sub_obj = json.loads(args.output_cuts.read_text())
        except Exception:
            sub_obj = {}
    else:
        sub_obj = {}

    if not args.output_mp4.exists():
        result = {
            "reward": 0.0,
            "details": {"reason": f"no output.mp4 at {args.output_mp4}"},
        }
    else:
        try:
            rep = verify_cuts(
                source_mp4=args.source_mp4,
                output_mp4=args.output_mp4,
                submission_json=sub_obj,
                gt_json=args.gt_cuts,
            )
            result = {"reward": float(rep.score), "details": asdict(rep)}
        except Exception as e:
            result = {
                "reward": 0.0,
                "details": {"reason": f"verifier error: {e!r}"},
            }

    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps(result, indent=2))
    args.reward_txt.write_text(f"{result[\'reward\']:.6f}\\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""


# Oracle: GT injection points are baked into solve.sh via heredoc.
# Oracle uses ffmpeg `select` filter to drop the duplicate frames, then
# emits the agent's two-file contract (output.mp4 + cuts.json).
SOLVE_SH_TEMPLATE = '''\
#!/bin/bash
# Oracle solver: baked-in GT cut points. Uses ffmpeg select filter to
# drop the duplicate copy of each GT glitch block, then writes
# output.mp4 + cuts.json.
set -euo pipefail

mkdir -p /workspace/output /workspace/work

INPUT=/workspace/materials/corrupted.mp4
OUTPUT=/workspace/output/output.mp4
OUTPUT_CUTS=/workspace/output/cuts.json

# Baked-in GT (post-injection frame indices in corrupted.mp4):
cat > "$OUTPUT_CUTS" <<'JSONEOF'
{cuts_json_payload}
JSONEOF

# Source fps as a rational; pass through to -r and use a guarded
# `setpts=N/(FPS)/TB` (parens so fractional FPS like 24000/1001 isn't
# parsed as `N/24000/1001/TB`).
FPS={fps_expr}

# Build ffmpeg select expression: keep frame n iff n not in any [s, e).
# Each glitch contributes a sub-expr "between(n,s,e-1)"; we OR them and negate.
SELECT_EXPR='not({select_or})'

# Audio cut spans (time, in seconds, in input). Each freeze block at
# post-injection frames [s, e) corresponds to audio span
# [s/FPS, e/FPS). We drop those audio samples so audio stays in sync
# with the cleaned video.
ASELECT_EXPR='not({aselect_or})'

ffmpeg -y -i "$INPUT" \\
    -vf "select=${{SELECT_EXPR}},setpts=N/(${{FPS}})/TB" \\
    -af "aselect=${{ASELECT_EXPR}},asetpts=N/SR/TB" \\
    -r "${{FPS}}" \\
    -c:v libx264 -pix_fmt yuv420p -preset veryfast \\
    -c:a aac -ac 1 -ar 16000 \\
    "$OUTPUT"

echo "oracle: wrote $OUTPUT and $OUTPUT_CUTS"
'''


def _write_exec(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _run(cmd: list[str]) -> None:
    print(f"  $ {' '.join(cmd)}")
    res = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr, file=sys.stderr)
        raise RuntimeError(f"command failed: {cmd[0]}")


def _ffprobe_video_info(path: Path) -> tuple[float, str]:
    """Return (duration_sec, r_frame_rate_str like '50/1')."""
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate,duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ], text=True).strip().splitlines()
    # First line is r_frame_rate, second is duration
    r_fr = out[0].strip()
    dur = float(out[1].strip()) if len(out) > 1 else 0.0
    return dur, r_fr


def _fps_to_float(rate: str) -> float:
    if "/" in rate:
        num, den = rate.split("/", 1)
        return float(num) / float(den)
    return float(rate)


def _count_frames(path: Path) -> int:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-count_frames", "-show_entries", "stream=nb_read_frames",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ], text=True).strip()
    return int(out)


def _build_select_or(glitches: list[tuple[int, int]]) -> str:
    # Inner commas must be escaped so the ffmpeg filter-graph parser
    # doesn't treat them as filter separators.
    parts = [f"between(n\\,{s}\\,{e - 1})" for s, e in glitches]
    return "+".join(parts)


def _build_aselect_or(glitches: list[tuple[int, int]], fps: float) -> str:
    """ffmpeg `aselect` expression over time-in-seconds.

    For freeze block at post-injection frame range [s, e), the matching
    audio span is [s/fps, e/fps). Drop those samples to keep AV synced.
    """
    parts = []
    for s, e in glitches:
        ts = s / fps
        te = e / fps
        parts.append(f"between(t\\,{ts:.6f}\\,{te:.6f})")
    return "+".join(parts)


def _pick_injection_points(total_frames: int, dup_len: int,
                           n_inj: int, seed: int) -> list[int]:
    """Pick n_inj injection points P_i in [100, total_frames - 100).
    Each P is the source-frame index immediately AFTER which the dup
    block is inserted. We pick them well-separated so they don't overlap
    on the post-injection timeline.
    """
    rng = random.Random(seed)
    margin = 100
    min_gap = dup_len + 50  # ensure separation in source space
    lo = margin
    hi = total_frames - margin - 1
    if hi - lo <= 0:
        raise RuntimeError(f"clip too short ({total_frames} frames) for margin={margin}")

    # Reject-sampling for well-separated points.
    for _attempt in range(1000):
        candidates = sorted(rng.sample(range(lo, hi), n_inj))
        ok = all(candidates[i + 1] - candidates[i] >= min_gap
                 for i in range(len(candidates) - 1))
        if ok:
            return candidates
    raise RuntimeError("could not find non-overlapping injection points")


def build_task(
    *,
    task_name: str,
    source_mp4: Path,
    dup_len: int,
    keep_workdir_dump: bool = False,
    # Precision verifier per-task scoring params (see HANDOFF.md sec.2).
    tolerance_each_side_s: float = 0.20,
    duration_tolerance_s: float = 0.10,
    ssim_threshold: float = 0.95,
    audio_xcorr_threshold: float = 0.90,
    audio_mode: str = "required",
    # How to fill audio over the freeze window. Replaces an earlier
    # implementation that inserted digital silence — too obvious a tell.
    #   "loop_one_video_frame":  copy 1 video-frame's worth of audio from
    #     just before the freeze and tile it across the freeze duration.
    #     Cheap, smooth-sounding; right for short freezes (~100-400 ms).
    #   "copy_prior_window":     copy the same-length audio chunk from
    #     immediately before the freeze and paste it once into the freeze.
    #     Right for long freezes (~1 s+) where tiling a single frame would
    #     read as obvious looping artefacts.
    audio_fill_mode: str = "loop_one_video_frame",
    # Clip duration is now a per-task input (deliberately non-round to avoid
    # leaking "exactly 60 s" as a hint the agent can back-calculate from).
    clip_duration_sec: float = CLIP_DURATION_SEC_DEFAULT,
) -> dict:
    """Generate one duplicated-frame-glitch Harbor task dir.

    Returns a dict with build summary (paths, injection points, fps).
    """
    task_dir = TASKS_DIR / task_name
    if task_dir.exists():
        shutil.rmtree(task_dir)
    task_dir.mkdir(parents=True)

    # ---- 1. Sample 60s @ 480p from source. ----
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        clip = tmp / "clip.mp4"
        _, r_fr = _ffprobe_video_info(source_mp4)
        fps = _fps_to_float(r_fr)
        # Use -ss before -i for fast keyframe seek; re-encode to be safe.
        _run([
            "ffmpeg", "-y",
            "-ss", str(CLIP_OFFSET_SEC),
            "-t", str(clip_duration_sec),
            "-i", str(source_mp4),
            "-vf", f"scale=-2:{TARGET_HEIGHT}",
            "-r", r_fr,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
            "-c:a", "aac", "-ac", "1", "-ar", "16000",
            str(clip),
        ])

        # ---- 2. Decode to PNG frames. ----
        frames_dir = tmp / "frames"
        frames_dir.mkdir()
        _run([
            "ffmpeg", "-y", "-i", str(clip),
            "-vsync", "0",
            str(frames_dir / "%06d.png"),
        ])
        frame_paths = sorted(frames_dir.glob("*.png"))
        total = len(frame_paths)
        if total < 200 + dup_len * N_INJECTIONS:
            raise RuntimeError(f"clip has only {total} frames; need more")

        # ---- 3. Pick injection points and assemble corrupted frame list. ----
        injection_pts = _pick_injection_points(total, dup_len, N_INJECTIONS, SEED)
        # FREEZE injection: at injection point P, hold frame P for dup_len
        # additional frames. The corrupted output then contains frame P
        # appearing dup_len + 1 times consecutively. The GT glitch range
        # marks the dup_len redundant copies (i.e., the freeze block to
        # remove).
        corrupted_order: list[int] = []  # source frame indices to use, in order
        gt_glitches: list[tuple[int, int]] = []  # (start, end) post-injection
        inj_iter = iter(sorted(injection_pts))
        next_inj = next(inj_iter, None)
        for src_idx in range(total):
            corrupted_order.append(src_idx)
            if next_inj is not None and src_idx == next_inj:
                # Hold this frame for dup_len more output positions.
                start_post = len(corrupted_order)  # index of first redundant copy
                for _ in range(dup_len):
                    corrupted_order.append(src_idx)
                end_post = len(corrupted_order)
                gt_glitches.append((start_post, end_post))
                next_inj = next(inj_iter, None)

        # ---- 4. Reassemble corrupted.mp4. ----
        corrupted_frames_dir = tmp / "corrupted_frames"
        corrupted_frames_dir.mkdir()
        # Symlink to save IO.
        for out_i, src_i in enumerate(corrupted_order):
            dst = corrupted_frames_dir / f"{out_i + 1:06d}.png"
            dst.symlink_to(frame_paths[src_i].resolve())

        # Step 4a: silent video from corrupted frame list.
        silent_video = tmp / "corrupted_video.mp4"
        _run([
            "ffmpeg", "-y",
            "-framerate", r_fr,
            "-i", str(corrupted_frames_dir / "%06d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
            "-r", r_fr,
            "-an",
            str(silent_video),
        ])

        # Step 4b: build matching audio track.
        # Original audio is `clip.mp4`'s audio (AAC mono 16k from extract).
        # At each injection point P (source frame), insert (dup_len / fps)
        # seconds of audio aligned with the duplicated video frames. Two
        # modes (see audio_fill_mode docstring):
        #   - loop_one_video_frame: take audio[t - 1/fps : t] (1 video
        #     frame of audio) and tile it across the freeze duration.
        #   - copy_prior_window: take audio[t - dup_dur_s : t] (same length
        #     as the freeze) and paste it once into the freeze span.
        dup_dur_s = dup_len / fps
        src_audio = tmp / "src_audio.wav"
        _run([
            "ffmpeg", "-y", "-i", str(clip),
            "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
            str(src_audio),
        ])

        # Read PCM samples for direct splicing.
        import wave as _wave
        import numpy as _np
        with _wave.open(str(src_audio), "rb") as w:
            sr = w.getframerate()
            n_chan = w.getnchannels()
            samp_width = w.getsampwidth()
            raw = w.readframes(w.getnframes())
        assert n_chan == 1 and samp_width == 2 and sr == 16000
        src_samples = _np.frombuffer(raw, dtype=_np.int16).copy()

        if audio_fill_mode == "loop_one_video_frame":
            loop_window_s = 1.0 / fps
        elif audio_fill_mode == "copy_prior_window":
            loop_window_s = dup_dur_s
        else:
            raise ValueError(f"unknown audio_fill_mode: {audio_fill_mode}")

        inj_times = sorted(p / fps for p in injection_pts)
        out_chunks: list[_np.ndarray] = []
        fill_n = int(round(dup_dur_s * sr))
        loop_n = max(1, int(round(loop_window_s * sr)))
        prev_sample = 0
        for t in inj_times:
            inj_sample = int(round(t * sr))
            inj_sample = min(inj_sample, len(src_samples))
            out_chunks.append(src_samples[prev_sample:inj_sample])
            # Build the freeze-window audio fill from the audio
            # immediately preceding the injection point.
            loop_start = max(0, inj_sample - loop_n)
            loop_audio = src_samples[loop_start:inj_sample]
            if len(loop_audio) == 0:
                # Edge case at very start; emit silence rather than crash.
                fill = _np.zeros(fill_n, dtype=_np.int16)
            elif len(loop_audio) >= fill_n:
                fill = loop_audio[:fill_n]
            else:
                n_reps = (fill_n + len(loop_audio) - 1) // len(loop_audio)
                fill = _np.tile(loop_audio, n_reps)[:fill_n]
            out_chunks.append(fill)
            prev_sample = inj_sample
        out_chunks.append(src_samples[prev_sample:])
        merged_samples = _np.concatenate(out_chunks)

        merged_audio = tmp / "corrupted_audio.wav"
        with _wave.open(str(merged_audio), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(merged_samples.tobytes())

        # Step 4c: mux silent video + merged audio into final corrupted.mp4.
        corrupted_mp4 = tmp / "corrupted.mp4"
        _run([
            "ffmpeg", "-y",
            "-i", str(silent_video),
            "-i", str(merged_audio),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac", "-ac", "1", "-ar", "16000",
            "-shortest",
            str(corrupted_mp4),
        ])

        # Also write the *clean* reference (60 s clip) into tests/original.mp4
        # — judge doesn't currently use it directly, but PLAN spec says
        # ship it for diagnostics / future judges.
        # Reuse `clip` directly.

        # ---- 5. Write Harbor task dir. ----
        (task_dir / "environment").mkdir(parents=True, exist_ok=True)
        (task_dir / "environment" / "Dockerfile").write_text(DOCKERFILE)
        (task_dir / "task.toml").write_text(TASK_TOML.format(
            task_name=task_name,
            source_name=source_mp4.name,
        ))

        step = task_dir / "steps" / "solve"
        step.mkdir(parents=True, exist_ok=True)

        dup_ms = int(round(dup_len / fps * 1000))
        (step / "instruction.md").write_text(INSTRUCTION_MD.format(
            duration_s=clip_duration_sec,
            fps_int=int(round(fps)),
            n_inj=N_INJECTIONS,
            dup_len=dup_len,
            dup_len_plus_one=dup_len + 1,
            dup_ms=dup_ms,
        ))

        workdir = step / "workdir"
        workdir.mkdir(parents=True, exist_ok=True)
        shutil.copy(corrupted_mp4, workdir / "corrupted.mp4")
        _write_exec(workdir / "setup.sh", SETUP_SH)

        tests = step / "tests"
        tests.mkdir(parents=True, exist_ok=True)
        # Probe corrupted duration now so we can record it in cuts.json.
        _corr_dur = _ffprobe_video_info(workdir / "corrupted.mp4")[0]
        cuts_payload = {
            "kind": "glitch_dup",
            "unit": "frames",
            "fps": fps,
            "source_duration_s": round(_corr_dur, 3),
            "tolerance_each_side_s": tolerance_each_side_s,
            "duration_tolerance_s": duration_tolerance_s,
            "ssim_threshold": ssim_threshold,
            "audio_xcorr_threshold": audio_xcorr_threshold,
            "audio": audio_mode,
            "glitches": [
                {"type": "duplicated", "start_frame": s, "end_frame": e}
                for s, e in gt_glitches
            ],
        }
        (tests / "cuts.json").write_text(json.dumps(cuts_payload, indent=2))
        shutil.copy(clip, tests / "original.mp4")
        _write_exec(tests / "test.sh", TEST_SH)
        # Embed verifier core into the per-task judge.
        import re as _re_local
        verifier_core_path = Path(__file__).resolve().parent / "_cut_verifier_core.py"
        verifier_core_source = verifier_core_path.read_text()
        verifier_core_source = _re_local.sub(
            r"^from __future__ import .*\n", "",
            verifier_core_source, count=1, flags=_re_local.M,
        )
        judge_py_text = JUDGE_PY_TEMPLATE.replace(
            "{verifier_core_source}", verifier_core_source,
        )
        _write_exec(tests / "judge.py", judge_py_text)

        # Oracle solve.sh: bake in GT, build select expr.
        solve_dir = step / "solution"
        solve_dir.mkdir(parents=True, exist_ok=True)
        select_or = _build_select_or(gt_glitches)
        aselect_or = _build_aselect_or(gt_glitches, fps)
        agent_facing_cuts = {
            "glitches": [
                {"type": "duplicated", "start_frame": s, "end_frame": e}
                for s, e in gt_glitches
            ],
        }
        solve_sh = SOLVE_SH_TEMPLATE.format(
            cuts_json_payload=json.dumps(agent_facing_cuts, indent=2),
            fps_expr=r_fr,  # ffmpeg accepts "50/1" style in env interp
            select_or=select_or,
            aselect_or=aselect_or,
        )
        _write_exec(solve_dir / "solve.sh", solve_sh)

        # ---- 6. Verify and report. ----
        corrupted_dst = workdir / "corrupted.mp4"
        n_frames_corrupted = _count_frames(corrupted_dst)
        dur_corrupted, _ = _ffprobe_video_info(corrupted_dst)
        size_mb = corrupted_dst.stat().st_size / (1024 * 1024)

        summary = {
            "task_name": task_name,
            "task_dir": str(task_dir),
            "source": str(source_mp4),
            "source_fps": fps,
            "source_fps_rational": r_fr,
            "n_source_frames_60s": total,
            "dup_len": dup_len,
            "injection_points_source_frame": injection_pts,
            "gt_glitches_post_injection": gt_glitches,
            "corrupted_n_frames": n_frames_corrupted,
            "corrupted_duration_s": dur_corrupted,
            "corrupted_size_mb": round(size_mb, 2),
            "expected_extra_frames": dup_len * N_INJECTIONS,
        }
        print(json.dumps(summary, indent=2))
        return summary
