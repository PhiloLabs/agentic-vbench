"""Shared core for cut-based Harbor task generators (disfluency + content-cut).

Each task ships:
  - `workdir/source.mp4`: clean 60–90 s clip (agent input)
  - `tests/cuts.json`: GT cut windows (the windows the agent must remove)
  - `tests/judge.py`: re-transcribes agent's `output.mp4`, checks that the
    GT content does NOT appear in the agent's transcript inside the
    (start, end) window. Per-cut binary reward = correct / total.
  - `solution/solve.sh`: oracle that reads baked-in GT and produces
    `output.mp4` (ffmpeg select+atrim+concat) and `cuts.json`.

Two task kinds:
  - "disfluency": each GT cut is a short filler-word window. Judge looks
    for `forbidden_tokens` (e.g., "um","uh","like") inside the window in
    the agent's transcript.
  - "content_cut": each GT cut is a longer topical segment. Judge collects
    distinctive keywords from the GT segment's clean transcript and
    checks those keywords are absent from the agent's output transcript
    in (or near) the corresponding window.
"""
from __future__ import annotations

import json
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent  # experiment/
TASKS_DIR = REPO_ROOT / "tasks" / "agentic_vbench_repair"
SOURCES_DIR = REPO_ROOT / "sources"


TASK_TOML = """\
version = "1.0"

[task]
name = "agentic-vbench/{task_name}"

[metadata]
difficulty = "medium"
category = "{category}"
tags = {tags_toml}
source = "{source_name}"
license = "unknown-research-use-only"
attribution = "see source URL"

[environment]
build_timeout_sec = 900.0
cpus = 2
memory_mb = 4096
storage_mb = 8192
allow_internet = true

[[steps]]
name = "solve"

[steps.agent]
timeout_sec = 1800.0

[steps.verifier]
timeout_sec = 900.0
"""


DOCKERFILE = """\
FROM --platform=linux/amd64 python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \\
        ffmpeg \\
        git \\
        ca-certificates \\
    && rm -rf /var/lib/apt/lists/*

# Precision cut verifier deps: numpy + scikit-image (SSIM) for honesty gate,
# stdlib wave for audio xcorr. No transcription needed.
RUN pip install --no-cache-dir \\
        "numpy<3" \\
        "scikit-image>=0.22,<1.0" \\
        "scipy>=1.10"

WORKDIR /workspace
RUN mkdir -p /workspace/materials /workspace/output /workspace/work
"""


DISFLUENCY_INSTRUCTION = """\
# Disfluency Removal (Video Cut Task)

`/workspace/materials/source.mp4` is a ~{duration_s} s video clip with
speech. The speaker uses several **filler words** (e.g., "um", "uh",
"like", "you know", "so" used as a filler). Your job is to find those
filler-word moments and produce a cleaned version of the video with
those short segments removed.

## What counts as a filler

A filler is a short ({min_ms}–{max_ms} ms) word like "um", "uh", "like",
"you know", "so" that does NOT carry content — i.e., removing it does
not change the meaning of the sentence. "Like" as a verb ("I like it")
is NOT a filler. "So" introducing a logical consequence ("So the
result is...") is NOT a filler. Only target words used as discourse
fillers / hesitations.

## Your output (two files)

1. `/workspace/output/output.mp4` — cleaned video with each filler
   segment cut out. H.264 / yuv420p, AAC audio, same resolution as
   input. Audio and video must stay in sync (cut both together).

2. `/workspace/output/cuts.json` — JSON describing the cuts you made:

   ```json
   {{
     "cuts": [
       {{"start_ms": 12480, "end_ms": 12720, "reason": "filler: 'um'"}},
       {{"start_ms": 23010, "end_ms": 23320, "reason": "filler: 'like'"}}
     ]
   }}
   ```

   `start_ms` / `end_ms` are time offsets in the **input** video
   (milliseconds, integers). Each entry is one filler-word segment you
   removed.

## Scoring

Per-cut binary. There are exactly **{n_gt}** ground-truth filler
moments. For each, the judge runs speech-to-text on your
`output.mp4` and checks that no filler-token transcript word falls
near the corresponding time window. Reward = correct / {n_gt}.

## Notes

- CPU only, ~30 min timeout. Container has internet; you may
  `pip install` extra tools.
- `ffmpeg` + `opencv-python-headless` + `faster-whisper` (tiny.en
  pre-cached) are available.
- Tip: `faster-whisper` with `word_timestamps=True` gives precise
  per-word start/end times. Combine that with a filler-token list to
  locate fillers, then use ffmpeg `select` + `atrim` + `concat`, or
  `ffmpeg -ss` / `-to` segment-and-concat, to cut.
- Use `/workspace/work/` for scratch.
"""


# Variant for tasks that include long-pause cuts in addition to filler
# words (used for natural interview-speech tasks where the speaker pauses
# meaningfully between phrases).
DISFLUENCY_PAUSE_INSTRUCTION = """\
# Disfluency + Pause Removal (Video Cut Task)

`/workspace/materials/source.mp4` is a ~{duration_s} s clip from a
real interview. The speaker talks slowly and the audio contains BOTH
short **filler words** (e.g., "um", "uh", "like", "so", "well" used as
hesitations) and **long silent pauses** (>= ~1.0 s of silence between
words inside a thought). Your job is to remove both kinds of dead air
and produce a tighter cleaned version.

## What to remove

1. **Filler words** — short ({min_ms}-{max_ms} ms) discourse markers
   ("um", "uh", "like", "you know", "so", "well") that don't carry
   meaning. Don't cut "like" when used as a verb ("I like that"); don't
   cut "so" when introducing a real consequence ("So we won").
2. **Meaningless long pauses** — silent gaps >= 1.0 s in the middle of
   a sentence/thought. Do NOT cut natural sentence breaks where the
   speaker has finished a thought. Cut hesitation silences, not
   end-of-sentence silences.

## Your output (two files)

1. `/workspace/output/output.mp4` — cleaned video with each filler /
   pause segment removed. H.264 / yuv420p, AAC audio, same resolution
   as input. Audio and video must stay in sync.

2. `/workspace/output/cuts.json` — JSON describing every cut:

   ```json
   {{
     "cuts": [
       {{"start_ms": 12480, "end_ms": 12720, "reason": "filler: 'um'"}},
       {{"start_ms": 18000, "end_ms": 19600, "reason": "long pause"}}
     ]
   }}
   ```

   `start_ms` / `end_ms` are offsets in the **input** video
   (milliseconds, integers).

## Scoring

Per-cut. There are **{n_gt}** ground-truth dead-air segments (mix of
fillers and pauses). For each, the judge runs speech-to-text on your
`output.mp4` and checks:
- For filler cuts: the forbidden filler token no longer appears in the
  transcript.
- For pause cuts: the word right before the pause and the word right
  after the pause are now adjacent (gap shrunk) in your output.

Reward = mean per-cut credit.

## Notes

- CPU only, ~30 min timeout. Container has internet; you may
  `pip install` extra tools.
- `ffmpeg` + `opencv-python-headless` + `faster-whisper` (tiny.en
  pre-cached) are available.
- Tip: transcribe with `faster-whisper` (`word_timestamps=True`) to
  find filler words; detect silent gaps via `librosa.effects.split` or
  `ffmpeg silencedetect`. Combine both, then cut with `ffmpeg select`
  + `atrim` + `concat`.
- Use `/workspace/work/` for scratch.
"""


CONTENT_CUT_INSTRUCTION = """\
# Content Cut (Video Cut Task)

`/workspace/materials/source.mp4` is a ~{duration_s} s video clip
containing more than one topical segment. Your job is described
below in the **task prompt** — read it carefully.

## Task prompt

{user_prompt}

## Your output (two files)

1. `/workspace/output/output.mp4` — the input with the target segment
   removed. H.264 / yuv420p, AAC audio, same resolution as input.
   Audio and video must stay in sync (cut both together).

2. `/workspace/output/cuts.json` — JSON describing the cut(s) you made:

   ```json
   {{
     "cuts": [
       {{"start_ms": 12000, "end_ms": 38500, "reason": "off-topic segment"}}
     ]
   }}
   ```

   `start_ms` / `end_ms` are time offsets in the **input** video
   (milliseconds, integers).

## Scoring

There is exactly **1** ground-truth segment to remove. The judge runs
speech-to-text on your `output.mp4` and verifies that none of the
distinctive keywords from the ground-truth segment survives in your
output. Reward is 1.0 if the segment is fully removed, otherwise the
fraction of keywords successfully removed.

## Notes

- CPU only, ~30 min timeout. Container has internet; you may
  `pip install` extra tools.
- `ffmpeg` + `opencv-python-headless` + `faster-whisper` (tiny.en
  pre-cached) are available.
- Tip: transcribe with `faster-whisper`, then locate the target segment
  in the transcript and cut by time.
- Use `/workspace/work/` for scratch.
"""


SETUP_SH = """\
#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

mkdir -p /workspace/materials /workspace/output /workspace/work
cp "$HERE/source.mp4" /workspace/materials/source.mp4

if [ ! -s /workspace/materials/source.mp4 ]; then
    echo "ERROR: source.mp4 missing or empty" >&2
    exit 1
fi

mkdir -p /logs/artifacts
ffprobe -v error -show_entries stream=duration,r_frame_rate \\
        -select_streams v:0 \\
        /workspace/materials/source.mp4 \\
        > /logs/artifacts/input-probe.txt 2>&1 || true

rm -rf -- "$HERE/source.mp4" "$0"
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
        --source-mp4 /workspace/materials/source.mp4 \\
        --output-mp4 /workspace/output/output.mp4 \\
        --output-cuts /workspace/output/cuts.json \\
        --gt-cuts /tests/cuts.json \\
        --reward-json /logs/verifier/reward.json \\
        --reward-txt /logs/verifier/reward.txt
"""


JUDGE_PY_TEMPLATE = """\
#!/usr/bin/env python3
\"\"\"Precision cut judge for agentic-vbench cut tasks.

Generated by experiment/scripts/_cut_task_core.py. The verifier core is
embedded below; do not edit this file by hand.

Two gates over the agent's submission (output.mp4 + cuts.json):

  - Range gate: each GT cut range gets a binary pass when the closest
    submitted range falls within +- tolerance_each_side_s on BOTH endpoints.
    Greedy-nearest match; no reuse. Score component = passed_count / N.

  - Honesty gate: reconstruct expected_remainder from ALL submitted ranges
    via ffmpeg select, then mean-SSIM (+-2 frame lag) >= ssim_threshold AND
    audio cross-correlation >= audio_xcorr_threshold. If honesty or audio
    fail, final score = 0 regardless of range gate.

Tolerances live in /tests/cuts.json, NOT here.
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

    # Agent might have skipped or mangled cuts.json. Treat missing/invalid
    # as empty submission (range gate gets 0; honesty likely fails too).
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


SOLVE_SH_TEMPLATE = '''\
#!/bin/bash
# Oracle solver: baked-in GT cut windows. Uses ffmpeg select/aselect
# filters to drop each GT segment, then writes output.mp4 + cuts.json.
set -euo pipefail

mkdir -p /workspace/output /workspace/work

INPUT=/workspace/materials/source.mp4
OUTPUT=/workspace/output/output.mp4
OUTPUT_CUTS=/workspace/output/cuts.json

cat > "$OUTPUT_CUTS" <<'JSONEOF'
{cuts_json_payload}
JSONEOF

# Build ffmpeg filter: keep frames whose presentation time t falls OUTSIDE all GT windows.
# select expression: not(between(t,s1,e1)+between(t,s2,e2)+...)
ffmpeg -y -i "$INPUT" \\
    -vf "select='not({video_between_or})',setpts=N/FRAME_RATE/TB" \\
    -af "aselect='not({audio_between_or})',asetpts=N/SR/TB" \\
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


def _norm_basic(s: str) -> str:
    import re as _re
    return _re.sub(r"[^a-z0-9'\s]", " ", s.lower()).strip()


def _ffprobe_duration(path: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ], text=True).strip()
    return float(out) if out else 0.0


def _build_between_or(cuts: list[tuple[float, float]]) -> str:
    """Build ffmpeg expression: between(t,s1,e1)+between(t,s2,e2)+...
    Commas inside between(...) must be escaped for filter-graph parser.
    """
    parts = [f"between(t\\,{s:.3f}\\,{e:.3f})" for s, e in cuts]
    return "+".join(parts)


def _extract_clip(source: Path, start_s: float, duration_s: float,
                  out_mp4: Path) -> None:
    """Extract a clip, 480p, mono 16kHz audio (AAC), libx264."""
    _run([
        "ffmpeg", "-y",
        "-ss", f"{start_s}",
        "-t", f"{duration_s}",
        "-i", str(source),
        "-vf", "scale=854:480",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
        "-c:a", "aac", "-ac", "1", "-ar", "16000",
        str(out_mp4),
    ])


def _transcribe_clip(clip_mp4: Path, model_size: str = "base.en") -> dict:
    """Run whisper-timestamped on clip; return its raw result dict."""
    import whisper_timestamped as wt
    audio = wt.load_audio(str(clip_mp4))
    model = wt.load_model(model_size, device="cpu")
    return wt.transcribe(model, audio, detect_disfluencies=True,
                         language="en", vad=False)


def build_cut_task(
    *,
    task_name: str,
    source_mp4: Path,
    clip_start_s: float,
    clip_duration_s: float,
    kind: str,                                    # "disfluency" | "content_cut"
    category: str,
    tags: list[str],
    # disfluency:
    filler_window_picker=None,
    pause_window_picker=None,    # optional: (wt_result, clip_path) -> list[dict]
    # content_cut:
    gt_segment_window_s: tuple[float, float] | None = None,
    user_prompt: str | None = None,
    # common:
    model_size: str = "base.en",
    # Precision-verifier per-task scoring params; see HANDOFF.md sec.2.
    tolerance_each_side_s: float = 0.20,
    duration_tolerance_s: float = 0.10,
    ssim_threshold: float = 0.95,
    audio_xcorr_threshold: float = 0.90,
    audio_mode: str = "required",   # "required" | "skip"
) -> dict:
    """Build one Harbor cut task.

    For "disfluency": `filler_window_picker(transcribe_result)` must
    return list of dicts. Each dict is one cut and has fields:
      {"start_s","end_s","reason": "..."}
    plus EITHER:
      - "forbidden_tokens": [tok,...]                     (filler cut, default)
    OR (for a pause/silence cut):
      - "type": "pause",
      - "pause_duration_ms": int,
      - "anchor_before": [word, word, ...],
      - "anchor_after":  [word, word, ...]

    For "content_cut": `gt_segment_window_s` and `user_prompt` are
    required. The judge will use distinctive keywords extracted from
    the clean transcript over that window.
    """
    assert kind in ("disfluency", "content_cut")
    task_dir = TASKS_DIR / task_name
    if task_dir.exists():
        shutil.rmtree(task_dir)
    task_dir.mkdir(parents=True)

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        clip = tmp / "source.mp4"
        _extract_clip(source_mp4, clip_start_s, clip_duration_s, clip)
        dur = _ffprobe_duration(clip)

        wt_result = _transcribe_clip(clip, model_size=model_size)

        # Build GT cuts.
        if kind == "disfluency":
            picks = filler_window_picker(wt_result) if filler_window_picker else []
            if pause_window_picker is not None:
                pause_picks = pause_window_picker(wt_result, clip) or []
                picks = list(picks) + list(pause_picks)
                picks.sort(key=lambda p: p["start_s"])
            assert picks, "no cuts produced (both pickers empty)"

            # Re-transcribe the SAME clip with the same model the judge uses
            # (faster-whisper tiny.en) so that source_filler_counts and pause
            # anchors are aligned with what the judge will see at score time.
            # If _judge_view isn't importable we fall back to wt_result.
            try:
                from _judge_view import (
                    transcribe_with_faster_whisper,
                    count_token_occurrences,
                    find_phrase,
                )
                jv_words = transcribe_with_faster_whisper(clip)
                use_jv = True
            except Exception as _e:  # noqa: F841
                jv_words = None
                use_jv = False

            # Source counts per filler token.
            source_counts: dict[str, int] = {}
            unique_tokens = set()
            for p in picks:
                if p.get("type") == "pause":
                    continue
                for t in p["forbidden_tokens"]:
                    unique_tokens.add(t.lower())

            if use_jv:
                for tok in unique_tokens:
                    source_counts[tok] = count_token_occurrences(jv_words, tok)
                # For each filler pick, find the judge-view word whose time
                # window overlaps the pick. If none, drop the pick. If found,
                # EXPAND the pick window to include the judge-view word
                # (since the oracle ffmpeg cut uses the pick window, not the
                # judge-view position -- they can disagree by 200+ ms).
                filtered = []
                for p in picks:
                    if p.get("type") == "pause":
                        filtered.append(p)
                        continue
                    s, e = p["start_s"], p["end_s"]
                    matched = None
                    for t in p["forbidden_tokens"]:
                        tok = t.lower()
                        parts = tok.split()
                        norm = [_norm_basic(w["text"]) for w in jv_words]
                        for i in range(len(jv_words) - len(parts) + 1):
                            if all(norm[i + j] == parts[j]
                                   for j in range(len(parts))):
                                ws = jv_words[i]["start"]
                                we = jv_words[i + len(parts) - 1]["end"]
                                if not (we < s - 0.3 or ws > e + 0.3):
                                    matched = (ws, we)
                                    break
                        if matched:
                            break
                    if matched:
                        ws, we = matched
                        # Expand pick to cover both ASR views with a 250ms
                        # safety pad. tiny.en's word boundaries shift across
                        # runs by 100-300ms; an under-sized cut leaves the
                        # filler audible and the judge still detects it.
                        p = dict(p)
                        p["start_s"] = max(0.0, min(s, ws) - 0.25)
                        p["end_s"] = max(e, we) + 0.25
                        filtered.append(p)
                picks = filtered
                assert picks, "no filler/pause cuts survived judge-view filter"
            else:
                all_words = []
                for seg in wt_result.get("segments", []):
                    for w in seg.get("words", []):
                        all_words.append(w)
                for tok in unique_tokens:
                    parts = tok.split()
                    n = 0
                    for i in range(len(all_words) - len(parts) + 1):
                        seq = " ".join(
                            _norm_basic(all_words[i + j]["text"])
                            for j in range(len(parts))
                        )
                        if seq == tok:
                            n += 1
                    source_counts[tok] = n

            # For pause cuts, rewrite anchor_before / anchor_after using
            # judge-view words (so the judge can actually find them). Drop
            # pause cuts whose anchors don't exist in the judge transcript.
            if use_jv:
                rewritten = []
                for p in picks:
                    if p.get("type") != "pause":
                        rewritten.append(p)
                        continue
                    cut_start = p["start_s"]
                    cut_end = p["end_s"]
                    # find judge-view word ending closest to cut_start (before)
                    before_idx = -1
                    for i, w in enumerate(jv_words):
                        if w["end"] <= cut_start + 0.20:
                            before_idx = i
                    after_idx = -1
                    for i, w in enumerate(jv_words):
                        if w["start"] >= cut_end - 0.20:
                            after_idx = i
                            break
                    if before_idx < 0 or after_idx < 0:
                        # can't anchor; drop this pause cut
                        continue
                    # Skip if these are adjacent / overlap.
                    if after_idx <= before_idx:
                        continue
                    anchor_before = [w["text"].strip() for w in
                                     jv_words[max(0, before_idx - 1):before_idx + 1]]
                    anchor_after = [w["text"].strip() for w in
                                    jv_words[after_idx:after_idx + 2]]
                    # Ensure the anchor pair can be found in order in jv_words.
                    i_b = find_phrase(jv_words, anchor_before)
                    i_a = find_phrase(jv_words, anchor_after,
                                      start_idx=i_b + len(anchor_before)) \
                        if i_b >= 0 else -1
                    if i_b < 0 or i_a < 0:
                        continue
                    p = dict(p)
                    p["anchor_before"] = anchor_before
                    p["anchor_after"] = anchor_after
                    rewritten.append(p)
                picks = rewritten
                assert picks, "no cuts survived judge-view anchor check"

            cuts_list = []
            for p in picks:
                base = {
                    "start_ms": int(round(p["start_s"] * 1000)),
                    "end_ms": int(round(p["end_s"] * 1000)),
                    "reason": p.get("reason", ""),
                }
                if p.get("type") == "pause":
                    base["type"] = "pause"
                    base["pause_duration_ms"] = int(p.get(
                        "pause_duration_ms",
                        int(round((p["end_s"] - p["start_s"]) * 1000))))
                    base["anchor_before"] = list(p.get("anchor_before", []))
                    base["anchor_after"] = list(p.get("anchor_after", []))
                else:
                    base["forbidden_tokens"] = p["forbidden_tokens"]
                cuts_list.append(base)

            cuts_payload = {
                "kind": "disfluency",
                "unit": "ms",
                "source_duration_s": round(dur, 3),
                "tolerance_each_side_s": tolerance_each_side_s,
                "duration_tolerance_s": duration_tolerance_s,
                "ssim_threshold": ssim_threshold,
                "audio_xcorr_threshold": audio_xcorr_threshold,
                "audio": audio_mode,
                "cuts": cuts_list,
                "source_filler_counts": source_counts,
            }
            gt_windows_s = [(p["start_s"], p["end_s"]) for p in picks]
        else:
            s, e = gt_segment_window_s  # type: ignore
            # Extract keywords from clean transcript in window.
            kws = _extract_keywords_from_window(wt_result, s, e)
            assert kws, "no keywords extracted from GT window"
            cuts_payload = {
                "kind": "content_cut",
                "unit": "ms",
                "source_duration_s": round(dur, 3),
                "tolerance_each_side_s": tolerance_each_side_s,
                "duration_tolerance_s": duration_tolerance_s,
                "ssim_threshold": ssim_threshold,
                "audio_xcorr_threshold": audio_xcorr_threshold,
                "audio": audio_mode,
                "cuts": [
                    {
                        "start_ms": int(round(s * 1000)),
                        "end_ms": int(round(e * 1000)),
                        "forbidden_keywords": kws,
                        "reason": "off-topic segment per prompt",
                    }
                ]
            }
            gt_windows_s = [(s, e)]

        # ---- Write task dir. ----
        (task_dir / "environment").mkdir(parents=True, exist_ok=True)
        (task_dir / "environment" / "Dockerfile").write_text(DOCKERFILE)
        tags_toml = "[" + ", ".join(f'"{t}"' for t in tags) + "]"
        (task_dir / "task.toml").write_text(TASK_TOML.format(
            task_name=task_name,
            category=category,
            tags_toml=tags_toml,
            source_name=source_mp4.name,
        ))

        step = task_dir / "steps" / "solve"
        step.mkdir(parents=True, exist_ok=True)

        if kind == "disfluency":
            has_pause = any(c.get("type") == "pause"
                            for c in cuts_payload["cuts"])
            tmpl = (DISFLUENCY_PAUSE_INSTRUCTION if has_pause
                    else DISFLUENCY_INSTRUCTION)
            (step / "instruction.md").write_text(tmpl.format(
                duration_s=int(round(dur)),
                min_ms=80, max_ms=600,
                n_gt=len(cuts_payload["cuts"]),
            ))
        else:
            (step / "instruction.md").write_text(CONTENT_CUT_INSTRUCTION.format(
                duration_s=int(round(dur)),
                user_prompt=user_prompt,
            ))

        workdir = step / "workdir"
        workdir.mkdir(parents=True, exist_ok=True)
        shutil.copy(clip, workdir / "source.mp4")
        _write_exec(workdir / "setup.sh", SETUP_SH)

        tests = step / "tests"
        tests.mkdir(parents=True, exist_ok=True)
        (tests / "cuts.json").write_text(json.dumps(cuts_payload, indent=2))
        _write_exec(tests / "test.sh", TEST_SH)
        # Embed the precision-verifier core source verbatim into judge.py so
        # the in-container judge has no extra import path dependency.
        # We use a sentinel string replacement (not str.format) because the
        # inlined source contains literal { and } characters that would
        # otherwise be misparsed as format fields.
        verifier_core_path = Path(__file__).resolve().parent / "_cut_verifier_core.py"
        verifier_core_source = verifier_core_path.read_text()
        # Strip the embedded module's `from __future__` import; judge.py
        # already has its own at the top, and __future__ imports must be the
        # first statements.
        verifier_core_source = re.sub(
            r"^from __future__ import .*\n", "",
            verifier_core_source, count=1, flags=re.M,
        )
        judge_py_text = JUDGE_PY_TEMPLATE.replace(
            "{verifier_core_source}", verifier_core_source,
        )
        _write_exec(tests / "judge.py", judge_py_text)

        # Oracle solve.sh.
        solve_dir = step / "solution"
        solve_dir.mkdir(parents=True, exist_ok=True)
        # Pad windows slightly so oracle definitely removes content.
        pad = 0.10  # 100 ms each side
        padded = [(max(0.0, s - pad), min(dur, e + pad))
                  for (s, e) in gt_windows_s]
        between_or = _build_between_or(padded)
        solve_sh = SOLVE_SH_TEMPLATE.format(
            cuts_json_payload=json.dumps(
                {"cuts": [
                    {"start_ms": c["start_ms"], "end_ms": c["end_ms"],
                     "reason": c.get("reason", "")}
                    for c in cuts_payload["cuts"]
                ]}, indent=2),
            video_between_or=between_or,
            audio_between_or=between_or,
        )
        _write_exec(solve_dir / "solve.sh", solve_sh)
        # Also bake GT cuts file for reference.
        (solve_dir / "gt_cuts.json").write_text(
            json.dumps(cuts_payload, indent=2))

        # ---- Verify, summarise. ----
        size_mb = (workdir / "source.mp4").stat().st_size / (1024 * 1024)
        summary = {
            "task_name": task_name,
            "task_dir": str(task_dir),
            "kind": kind,
            "source": str(source_mp4),
            "clip_start_s": clip_start_s,
            "clip_duration_s": clip_duration_s,
            "clip_actual_duration_s": round(dur, 2),
            "clip_size_mb": round(size_mb, 2),
            "n_gt_cuts": len(cuts_payload["cuts"]),
            "gt_windows_ms": [(c["start_ms"], c["end_ms"])
                              for c in cuts_payload["cuts"]],
            "gt_total_ms": sum(c["end_ms"] - c["start_ms"]
                               for c in cuts_payload["cuts"]),
        }
        if kind == "content_cut":
            summary["n_keywords"] = len(cuts_payload["cuts"][0][
                "forbidden_keywords"])
            summary["keywords_preview"] = cuts_payload["cuts"][0][
                "forbidden_keywords"][:10]
        print(json.dumps(summary, indent=2))
        return summary


_STOPWORDS = set("""a about above after again against all am an and any are aren't as at be
because been before being below between both but by can can't cannot could couldn't did didn't
do does doesn't doing don't down during each few for from further had hadn't has hasn't have
haven't having he he'd he'll he's her here here's hers herself him himself his how how's i i'd
i'll i'm i've if in into is isn't it it's its itself let's me more most mustn't my myself no
nor not of off on once only or other ought our ours ourselves out over own same shan't she
she'd she'll she's should shouldn't so some such than that that's the their theirs them
themselves then there there's these they they'd they'll they're they've this those through to
too under until up very was wasn't we we'd we'll we're we've were weren't what what's when
when's where where's which while who who's whom why why's with won't would wouldn't you you'd
you'll you're you've your yours yourself yourselves like get got just also even now still
really thing things one two way got say said going gonna want need think know talk talked
talking actually basically literally seriously kinda kind sort yeah ok okay yes yeah yep yup
right well""".split())


def _extract_keywords_from_window(wt_result: dict, start_s: float,
                                  end_s: float, max_kws: int = 25) -> list[str]:
    """Get distinctive content words from clean transcript in the window.

    Keep nouns/verbs/etc., drop stopwords/short words. Returns lowercased
    unique tokens. We don't need POS tagging — frequency + stopword
    filter works for short experiments.
    """
    in_window = []
    for seg in wt_result.get("segments", []):
        for w in seg.get("words", []):
            ws, we = float(w["start"]), float(w["end"])
            # word overlaps window
            if we < start_s or ws > end_s:
                continue
            t = re.sub(r"[^a-zA-Z']", "", w["text"]).lower()
            if not t or len(t) < 4:
                continue
            if t in _STOPWORDS:
                continue
            in_window.append(t)
    # Frequency-sort, take top distinct.
    from collections import Counter
    counts = Counter(in_window)
    # prefer words that don't appear outside window (more distinctive)
    outside = Counter()
    for seg in wt_result.get("segments", []):
        for w in seg.get("words", []):
            ws, we = float(w["start"]), float(w["end"])
            if start_s <= ws <= end_s or start_s <= we <= end_s:
                continue
            t = re.sub(r"[^a-zA-Z']", "", w["text"]).lower()
            if t and len(t) >= 4 and t not in _STOPWORDS:
                outside[t] += 1

    scored = []
    for tok, n in counts.items():
        out_n = outside.get(tok, 0)
        # distinctiveness: high in-window count, low outside count
        distinct = n - 0.5 * out_n
        scored.append((distinct, n, tok))
    scored.sort(reverse=True)
    # take tokens that appear at least once in window AND are reasonably
    # distinctive (out_n <= 2*in_n)
    picked = []
    for distinct, n, tok in scored:
        out_n = outside.get(tok, 0)
        if n >= 1 and out_n <= max(2, 2 * n):
            picked.append(tok)
        if len(picked) >= max_kws:
            break
    return picked
