#!/usr/bin/env python3
"""Build a static HTML site at experiment/site/index-v4.html for reviewing the experiment.

v4 fork of build_site.py: overlays the universal normalize-improvement verifier
(see `scripts/v4/V4_DESIGN.md`). When a v4 row exists for a task, it overrides
the claude/golden/corrupted reward values (broken=0, golden=1 by construction
for non-passthrough families) and renders a v4-aware sub-score block.

Per-task: source/clean media, corrupted (agent input), noise-only track (audio inj
only), agent rollout output, oracle output, mask + cuts.json where applicable,
reward numbers, and human-readable corruption description.
"""

import csv
import json
import re
import shutil
import subprocess
import tomllib
from html import escape
from pathlib import Path

import numpy as np
import soundfile as sf

EXP = Path(__file__).resolve().parent.parent
SITE = EXP / "site"
ASSETS = SITE / "assets"

# Audio-injection tasks: source video + clip range, so we can mux video back in
# for the review site. Audio tasks are still a video benchmark — review should
# show both modalities.
AUDIO_CLIP_RANGES = {
    "exp-dns-denoise-task01":        ("sources/01-dns-denoise-veritasium-blue-roses.mp4",      60, 35),
    "exp-voicebank-denoise-task01":  ("sources/02-voicebank-reuters-trump-victory.mp4",         5, 35),
    "exp-dereverb-task01":           ("sources/03-dereverb-snl-elon-musk-cold-open.mp4",        5, 35),
    "exp-declip-task01":             ("sources/04-declip-casey-neistat-marathon.mp4",         120, 35),
    "exp-codec-restore-task01":      ("sources/05-codec-restore-visit-korea.mp4",               0, 30),
}

TASK_TYPES = {
    "dns-denoise":              ("audio_inj",  "🔊", "DNS noise overlay (random SNR)"),
    "voicebank-denoise":        ("audio_inj",  "🔊", "DEMAND 5-env noise overlay (fixed SNR)"),
    "dereverb":                 ("audio_inj",  "🌀", "pyroomacoustics RIR convolution"),
    "declip":                   ("audio_inj",  "🔊", "Quantile hard-clipping (URGENT-2024 recipe)"),
    "codec-restore":            ("audio_inj",  "📻", "Opus 12 kbps roundtrip"),
    "glitch-dup-short":         ("glitch",     "🎬", "frame-freeze stutters at 2 spots (~0.7s each)"),
    "glitch-dup-long":          ("glitch",     "🎬", "frame-freeze stutters at 2 spots (~1.1s each)"),
    "disfluency-pitch-meeting": ("cut",        "✂️", "Natural fillers — agent must cut them"),
    "disfluency-interview-3":   ("cut",        "✂️", "Stuck-um (~1.6 s sustained 'ummm') — agent must cut it"),
    "disfluency-interview-4":   ("cut",        "✂️", "Two visible umm/emm fillers — agent must cut both"),
    "content-cut-wsj":          ("cut",        "✂️", "Prompt-driven segment removal"),
    "content-cut-mkbhd":        ("cut",        "✂️", "Prompt-driven intro removal"),
    "color-grade-visit-korea":  ("mask_color", "🎨", "Wrong LUT (Δh=−10°, ×sat 0.5) in bbox mask (v1, archived)"),
    "color-grade-gobelins":     ("mask_color", "🎨", "Wrong LUT (Δh=+15°, ×sat 1.2) in bbox mask (v1, archived)"),
    "color-shot-visit-korea":   ("color_shot", "🎨", "Shot-scoped color restore (Bourbon 64 warm LUT → restore)"),
    "color-shot-gobelins":      ("color_shot", "🎨", "Shot-scoped color restore (CINEMA_NOIR LUT → restore)"),
    "color-shot-v3-s1":         ("color_shot", "🎨", "Shot-scoped color restore (cold-desat CDL → restore)"),
    "deblur-gaussian-mkbhd":    ("mask_blur",  "🔍", "Gaussian σ=3 (kernel 15×15) in bbox mask"),
    "deblur-motion-f1":         ("mask_blur",  "🔍", "Linear motion blur (15 px, angle 0°) in bbox mask"),
    "sr-2x-shot":               ("sr_shot",    "🔎", "One shot downsampled 2× (bicubic), agent must restore"),
    "sr-4x-shot":               ("sr_shot",    "🔎", "One shot downsampled 4× (bicubic), agent must restore"),
    "swap-car":                 ("swap",       "🔀", "Two shots swapped out of temporal order, agent must restore order"),
    "swap-product":             ("swap",       "🔀", "Two shots swapped out of temporal order, agent must restore order"),
}


def load_results():
    """Return (oracle, claude, costs, golden, corrupted, v3_formula, v4_details) dicts keyed by task name.

    v4 overlay: if `logs/v4-results.tsv` exists, replace claude/golden/corrupted
    for any task with a v4 row, and populate v4_details from per-task JSON.
    """
    oracle, claude, costs, golden, corrupted, v3_formula = {}, {}, {}, {}, {}, {}
    v4_details: dict = {}
    smoke_tsv = EXP / "logs" / "smoke-results.tsv"
    rollout_tsv = EXP / "logs" / "rollout-results.tsv"
    costs_tsv = EXP / "logs" / "costs.tsv"
    baselines_tsv = EXP / "logs" / "baselines.tsv"
    v3_tsv = EXP / "logs" / "v3-rejudge-results.tsv"
    v4_tsv = EXP / "logs" / "v4-results.tsv"
    v4_per_task = EXP / "logs" / "v4-per-task"
    with smoke_tsv.open() as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["status"].startswith("OK") and r["reward"] != "-":
                oracle[r["task"]] = float(r["reward"])
    with rollout_tsv.open() as f:
        for r in csv.DictReader(f, delimiter="\t"):
            if r["status"].startswith("OK") and r["reward"] != "-":
                claude[r["task"]] = float(r["reward"])
    if costs_tsv.exists():
        with costs_tsv.open() as f:
            for r in csv.DictReader(f, delimiter="\t"):
                try:
                    costs[r["task"]] = float(r["cost_usd"])
                except (ValueError, KeyError):
                    pass
    if baselines_tsv.exists():
        with baselines_tsv.open() as f:
            for r in csv.DictReader(f, delimiter="\t"):
                if not r["reward"]:
                    continue
                try:
                    v = float(r["reward"])
                except ValueError:
                    continue
                if r["mode"] == "golden":
                    golden[r["task"]] = v
                elif r["mode"] == "corrupted":
                    corrupted[r["task"]] = v
    # v3 overrides — when present, replace audio-task numbers with new judge battery results
    if v3_tsv.exists():
        with v3_tsv.open() as f:
            for r in csv.DictReader(f, delimiter="\t"):
                t = r["task"]
                def parse(field):
                    try: return float(r[field])
                    except (ValueError, KeyError): return None
                g = parse("golden")
                c = parse("corrupted")
                o = parse("oracle_v3")
                cc = parse("claude_v3")
                if g is not None: golden[t] = g
                if c is not None: corrupted[t] = c
                if o is not None: oracle[t] = o
                if cc is not None: claude[t] = cc
                if r.get("composite_formula"):
                    v3_formula[t] = r["composite_formula"]
    # v4 overlay — universal normalize-improvement verifier.
    # Override claude/corrupted/golden with v4 anchors when a v4 row exists.
    if v4_tsv.exists():
        with v4_tsv.open() as f:
            for r in csv.DictReader(f, delimiter="\t"):
                t = r.get("task")
                if not t:
                    continue
                try:
                    claude[t] = float(r["v4_calibrated"])
                except (ValueError, KeyError):
                    continue
                # By v4 construction: broken anchors to 0, golden to 1.
                corrupted[t] = 0.0
                golden[t] = 1.0
    # v4 oracle scores — computed by scripts/v4/recompute_oracle.py
    # against jobs/smoke-* artifacts. Surfaces broken-solve.sh designs honestly
    # (passthrough oracles score 0).
    v4_oracle_tsv = EXP / "logs" / "v4-oracle-results.tsv"
    if v4_oracle_tsv.exists():
        with v4_oracle_tsv.open() as f:
            for r in csv.DictReader(f, delimiter="\t"):
                t = r.get("task")
                if not t:
                    continue
                try:
                    oracle[t] = float(r["v4_calibrated"])
                except (ValueError, KeyError):
                    continue
    if v4_per_task.exists():
        for jf in v4_per_task.glob("*.json"):
            try:
                v4_details[jf.stem] = json.loads(jf.read_text())
            except Exception as e:
                print(f"  failed to load {jf}: {e}")
    return oracle, claude, costs, golden, corrupted, v3_formula, v4_details


def find_latest(pattern: str):
    """Find the most recent dir matching jobs/<pattern>."""
    matches = sorted((EXP / "jobs").glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def artifact_path(job_dir: Path, filename: str):
    """Return the artifact path inside a Harbor job dir, or None."""
    if job_dir is None:
        return None
    candidates = list(job_dir.glob(f"*/steps/solve/artifacts/{filename}"))
    return candidates[0] if candidates else None


def task_toml(task_dir: Path) -> dict:
    p = task_dir / "task.toml"
    return tomllib.loads(p.read_text()) if p.exists() else {}


def copy_if_exists(src, dst):
    if src and Path(src).exists():
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True
    return False


def extract_silent_video(source_mp4: Path, start: int, duration: int, out_mp4: Path) -> bool:
    """Extract a video-only (no audio) segment from source.mp4 at [start, start+duration]."""
    if out_mp4.exists():
        return True
    try:
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", str(start), "-t", str(duration),
            "-i", str(source_mp4),
            "-an",
            "-vf", "scale=854:480",
            "-c:v", "libx264", "-preset", "fast", "-crf", "28",
            "-pix_fmt", "yuv420p",
            str(out_mp4),
        ], check=True)
        return True
    except Exception as e:
        print(f"  silent-video extract failed: {e}")
        return False


def mux_audio_into_video(silent_mp4: Path, audio_wav: Path, out_mp4: Path) -> bool:
    """Mux audio_wav onto silent_mp4 → out_mp4 (video copy, audio encoded to AAC)."""
    if out_mp4.exists() and out_mp4.stat().st_mtime > audio_wav.stat().st_mtime:
        return True
    try:
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(silent_mp4),
            "-i", str(audio_wav),
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "96k",
            "-map", "0:v:0", "-map", "1:a:0",
            "-shortest",
            str(out_mp4),
        ], check=True)
        return True
    except Exception as e:
        print(f"  mux failed for {out_mp4}: {e}")
        return False


def compute_noise_only(noisy_wav: Path, clean_wav: Path, out_wav: Path) -> bool:
    """For additive audio injection: noise = noisy - clean. For dereverb/declip/codec
    where the relationship isn't strictly additive, this still gives a useful
    "what was added" track albeit not the canonical noise."""
    try:
        n, sr_n = sf.read(noisy_wav)
        c, sr_c = sf.read(clean_wav)
        if sr_n != sr_c:
            return False
        L = min(len(n), len(c))
        diff = n[:L] - c[:L]
        # Normalize for audibility
        peak = np.max(np.abs(diff))
        if peak > 1e-6:
            diff = diff / peak * 0.7
        sf.write(out_wav, diff, sr_n)
        return True
    except Exception as e:
        print(f"  noise-only compute failed: {e}")
        return False


def gather_task_assets(task_id: str) -> dict:
    """Copy assets for one task into site/assets/<task_id>/ and return a metadata dict."""
    task_dir = EXP / "tasks" / "agentic_vbench_repair" / task_id
    if not task_dir.exists():
        return {"missing": True}

    slug = task_id.replace("exp-", "").replace("-task01", "")
    family, icon, recipe = TASK_TYPES.get(slug, ("?", "❓", "?"))

    asset_dir = ASSETS / task_id
    asset_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "task_id": task_id,
        "slug": slug,
        "family": family,
        "icon": icon,
        "recipe": recipe,
        "toml": task_toml(task_dir),
        "instruction": (task_dir / "steps/solve/instruction.md").read_text() if (task_dir / "steps/solve/instruction.md").exists() else "",
        "files": {},
    }

    workdir = task_dir / "steps/solve/workdir"
    tests = task_dir / "steps/solve/tests"

    if family == "audio_inj":
        copy_if_exists(workdir / "noisy.wav",   asset_dir / "noisy.wav")
        copy_if_exists(tests   / "clean.wav",   asset_dir / "clean.wav")
        # noise-only diff (audio-only — there's no "noise video")
        if (asset_dir / "noisy.wav").exists() and (asset_dir / "clean.wav").exists():
            compute_noise_only(asset_dir / "noisy.wav", asset_dir / "clean.wav", asset_dir / "noise-only.wav")
        # oracle + claude audio outputs
        oracle_job = find_latest(f"smoke-{task_id}-*")
        cc_job = find_latest(f"cc-{task_id}-*")
        copy_if_exists(artifact_path(oracle_job, "enhanced.wav"), asset_dir / "oracle-enhanced.wav")
        copy_if_exists(artifact_path(cc_job, "enhanced.wav"), asset_dir / "claude-enhanced.wav")

        # Mux each audio variant onto the silent video clip from the source.
        # This is a video benchmark — review pages should show video.
        # `sources/` is gitignored, so on a clean checkout the raw source mp4
        # may be missing. Fall back to cached `_silent.mp4` / muxed `.mp4`s
        # in the asset dir from a prior build instead of dropping to audio-only.
        if task_id in AUDIO_CLIP_RANGES:
            rel_src, start, duration = AUDIO_CLIP_RANGES[task_id]
            source_mp4 = EXP / rel_src
            silent_mp4 = asset_dir / "_silent.mp4"
            if not silent_mp4.exists() and source_mp4.exists():
                extract_silent_video(source_mp4, start, duration, silent_mp4)
            variants = [
                ("clean.wav",            "clean.mp4",         "clean"),
                ("noisy.wav",            "corrupted.mp4",     "corrupted"),
                ("noise-only.wav",       "noise-only.mp4",    "noise_only"),
                ("oracle-enhanced.wav",  "oracle-output.mp4", "oracle_output"),
                ("claude-enhanced.wav",  "claude-output.mp4", "claude_output"),
            ]
            for wav, mp4, key in variants:
                wav_path = asset_dir / wav
                mp4_path = asset_dir / mp4
                if not mp4_path.exists() and wav_path.exists() and silent_mp4.exists():
                    mux_audio_into_video(silent_mp4, wav_path, mp4_path)
                if mp4_path.exists():
                    meta["files"][key] = mp4
            if any(meta["files"].get(k) for k in
                   ("clean", "corrupted", "oracle_output", "claude_output")):
                meta["render_as"] = "video"
        # If muxing didn't run (no source / extraction failed), fall back to audio-only.
        if "clean" not in meta["files"] and (asset_dir / "clean.wav").exists():
            meta["files"]["clean"] = "clean.wav"
        if "corrupted" not in meta["files"] and (asset_dir / "noisy.wav").exists():
            meta["files"]["corrupted"] = "noisy.wav"
        if "noise_only" not in meta["files"] and (asset_dir / "noise-only.wav").exists():
            meta["files"]["noise_only"] = "noise-only.wav"
        if "oracle_output" not in meta["files"] and (asset_dir / "oracle-enhanced.wav").exists():
            meta["files"]["oracle_output"] = "oracle-enhanced.wav"
        if "claude_output" not in meta["files"] and (asset_dir / "claude-enhanced.wav").exists():
            meta["files"]["claude_output"] = "claude-enhanced.wav"

    elif family == "glitch":
        copy_if_exists(workdir / "corrupted.mp4", asset_dir / "corrupted.mp4")
        copy_if_exists(tests   / "original.mp4", asset_dir / "original.mp4")
        copy_if_exists(tests   / "cuts.json",    asset_dir / "gt-cuts.json")
        meta["files"]["corrupted"] = "corrupted.mp4"
        meta["files"]["clean"] = "original.mp4"
        meta["files"]["gt_cuts"] = "gt-cuts.json"
        oracle_job = find_latest(f"smoke-{task_id}-*")
        cc_job = find_latest(f"cc-{task_id}-*")
        if copy_if_exists(artifact_path(oracle_job, "output.mp4"), asset_dir / "oracle-output.mp4"):
            meta["files"]["oracle_output"] = "oracle-output.mp4"
        if copy_if_exists(artifact_path(cc_job, "output.mp4"), asset_dir / "claude-output.mp4"):
            meta["files"]["claude_output"] = "claude-output.mp4"
    elif family == "cut":
        copy_if_exists(workdir / "source.mp4", asset_dir / "source.mp4")
        copy_if_exists(tests   / "cuts.json",   asset_dir / "gt-cuts.json")
        meta["files"]["clean"] = "source.mp4"
        meta["files"]["gt_cuts"] = "gt-cuts.json"
        # No "corrupted" — corruption is the prompt itself
        oracle_job = find_latest(f"smoke-{task_id}-*")
        cc_job = find_latest(f"cc-{task_id}-*")
        if copy_if_exists(artifact_path(oracle_job, "output.mp4"), asset_dir / "oracle-output.mp4"):
            meta["files"]["oracle_output"] = "oracle-output.mp4"
        if copy_if_exists(artifact_path(cc_job, "output.mp4"), asset_dir / "claude-output.mp4"):
            meta["files"]["claude_output"] = "claude-output.mp4"

    elif family in ("mask_color", "mask_blur"):
        copy_if_exists(workdir / "corrupted.mp4", asset_dir / "corrupted.mp4")
        copy_if_exists(tests   / "clean.mp4",    asset_dir / "clean.mp4")
        copy_if_exists(workdir / "mask.png",     asset_dir / "mask.png")
        meta["files"]["corrupted"] = "corrupted.mp4"
        meta["files"]["clean"] = "clean.mp4"
        meta["files"]["mask"] = "mask.png"
        if copy_if_exists(tests / "gt_window.json", asset_dir / "gt-window.json"):
            meta["files"]["gt_window"] = "gt-window.json"
        oracle_job = find_latest(f"smoke-{task_id}-*")
        cc_job = find_latest(f"cc-{task_id}-*")
        if copy_if_exists(artifact_path(oracle_job, "output.mp4"), asset_dir / "oracle-output.mp4"):
            meta["files"]["oracle_output"] = "oracle-output.mp4"
        if copy_if_exists(artifact_path(cc_job, "output.mp4"), asset_dir / "claude-output.mp4"):
            meta["files"]["claude_output"] = "claude-output.mp4"

    elif family == "color_shot":
        # Flipped direction: agent sees the GRADED (broken) video at
        # workdir/source.mp4 and must restore the clean reference at
        # tests/original.mp4. gt_window.json carries the bad-grade window.
        copy_if_exists(workdir / "source.mp4", asset_dir / "corrupted.mp4")
        meta["files"]["corrupted"] = "corrupted.mp4"
        copy_if_exists(tests / "original.mp4", asset_dir / "original.mp4")
        meta["files"]["clean"] = "original.mp4"
        copy_if_exists(workdir / "prompt.txt", asset_dir / "prompt.txt")
        if copy_if_exists(tests / "gt_window.json", asset_dir / "gt-window.json"):
            meta["files"]["gt_window"] = "gt-window.json"
        oracle_job = find_latest(f"smoke-{task_id}-*")
        cc_job = find_latest(f"cc-{task_id}-*")
        if copy_if_exists(artifact_path(oracle_job, "output.mp4"), asset_dir / "oracle-output.mp4"):
            meta["files"]["oracle_output"] = "oracle-output.mp4"
        if copy_if_exists(artifact_path(cc_job, "output.mp4"), asset_dir / "claude-output.mp4"):
            meta["files"]["claude_output"] = "claude-output.mp4"

    elif family == "sr_shot":
        copy_if_exists(workdir / "corrupted.mp4", asset_dir / "corrupted.mp4")
        copy_if_exists(tests / "original.mp4",   asset_dir / "original.mp4")
        copy_if_exists(tests / "gt_shot.json",   asset_dir / "gt-shot.json")
        meta["files"]["corrupted"] = "corrupted.mp4"
        meta["files"]["clean"] = "original.mp4"
        if (asset_dir / "gt-shot.json").exists():
            meta["files"]["gt_shot"] = "gt-shot.json"
        oracle_job = find_latest(f"smoke-{task_id}-*")
        cc_job = find_latest(f"cc-{task_id}-*")
        if copy_if_exists(artifact_path(oracle_job, "output.mp4"), asset_dir / "oracle-output.mp4"):
            meta["files"]["oracle_output"] = "oracle-output.mp4"
        if copy_if_exists(artifact_path(cc_job, "output.mp4"), asset_dir / "claude-output.mp4"):
            meta["files"]["claude_output"] = "claude-output.mp4"

    elif family == "swap":
        copy_if_exists(workdir / "corrupted.mp4", asset_dir / "corrupted.mp4")
        copy_if_exists(tests / "original.mp4",   asset_dir / "original.mp4")
        copy_if_exists(tests / "gt_swap.json",   asset_dir / "gt-swap.json")
        meta["files"]["corrupted"] = "corrupted.mp4"
        meta["files"]["clean"] = "original.mp4"
        if (asset_dir / "gt-swap.json").exists():
            meta["files"]["gt_cuts"] = "gt-swap.json"
        oracle_job = find_latest(f"smoke-{task_id}-*")
        cc_job = find_latest(f"cc-{task_id}-*")
        if copy_if_exists(artifact_path(oracle_job, "output.mp4"), asset_dir / "oracle-output.mp4"):
            meta["files"]["oracle_output"] = "oracle-output.mp4"
        if copy_if_exists(artifact_path(cc_job, "output.mp4"), asset_dir / "claude-output.mp4"):
            meta["files"]["claude_output"] = "claude-output.mp4"

    # Final pass: every .mp4 in the asset dir becomes all-keyframes so HTML5
    # arrow-key frame-stepping works uniformly. Idempotent — re-runs are no-ops.
    for v in asset_dir.glob("*.mp4"):
        _all_keyframe_reencode(v)

    # Render audio-envelope waveform PNGs for cut/glitch/audio_inj families —
    # helps user align cut points to silence boundaries. Other families skipped.
    if family in ("cut", "glitch", "audio_inj", "color_shot"):
        for v in asset_dir.glob("*.mp4"):
            _render_waveform_png(v, v.with_suffix(".wf.png"))
        # audio_inj fall-backs that are .wav (no video muxed)
        for w in asset_dir.glob("*.wav"):
            _render_waveform_png(w, w.with_suffix(".wf.png"))

    return meta


def _render_waveform_png(media_path: Path, out_png: Path,
                         width: int = 1280, height: int = 128) -> None:
    """Render audio-envelope waveform PNG using ffmpeg showwavespic. Idempotent:
    skips if out_png is newer than media_path."""
    if not media_path.exists(): return
    if out_png.exists() and out_png.stat().st_mtime >= media_path.stat().st_mtime:
        return
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(media_path),
             "-filter_complex",
             f"[0:a]aformat=channel_layouts=mono,showwavespic=s={width}x{height}:colors=0x4a90e2",
             "-frames:v", "1", str(out_png)],
            check=True,
        )
    except Exception as e:
        print(f"  waveform render failed for {media_path.name}: {e}")


def _all_keyframe_reencode(path: Path) -> None:
    """In-place re-encode a video so every frame is a keyframe (-g 1) AND
    the moov atom is at the front (-movflags +faststart). Both are needed for
    HTML5 <video> to do frame-accurate seek AND show duration before the whole
    file downloads. Idempotent: skips if BOTH properties already hold."""
    if not path.exists(): return
    needs_reencode = False
    # (1) All-keyframe check on a small sample.
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "frame=pict_type", "-of", "csv=p=0",
             "-read_intervals", "%+3", str(path)],
            capture_output=True, text=True, check=True,
        )
        types = [t.strip() for t in r.stdout.splitlines() if t.strip()]
        all_i = bool(types) and all(t == "I" or t == "I," for t in types[:60])
    except Exception:
        all_i = False
    if not all_i:
        needs_reencode = True
    # (2) moov-at-front check.
    try:
        with path.open("rb") as fh:
            head = fh.read(1 << 20)
        moov = head.find(b"moov")
        mdat = head.find(b"mdat")
        faststart = moov >= 0 and (mdat < 0 or moov < mdat)
    except Exception:
        faststart = False
    if not faststart:
        needs_reencode = True
    if not needs_reencode:
        return
    tmp = path.with_suffix(".g1.tmp.mp4")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(path),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
             "-g", "1", "-keyint_min", "1",
             "-x264-params", "scenecut=0",
             "-movflags", "+faststart",
             "-c:a", "copy", str(tmp)],
            check=True,
        )
        tmp.replace(path)
    except Exception as e:
        print(f"  all-keyframe reencode failed for {path.name}: {e}")
        if tmp.exists(): tmp.unlink()


def media_tag(rel_path: str, kind: str, dom_id: str | None = None) -> str:
    """Generate an <audio> or <video> embed pointing at the asset. Pass dom_id
    so jump buttons can target this element via document.getElementById().

    For videos: wraps in a .video-wrap container, probes fps to set data-fps
    (used for frame-stepping with arrow keys), and adds a sibling time
    readout shown in ms-precision (e.g., `25.434 / 30.000`)."""
    id_attr = f' id="{dom_id}"' if dom_id else ""
    # Sibling waveform PNG (rendered for cut/glitch/audio_inj families).
    abs_path = (SITE / rel_path).resolve()
    wf_rel = rel_path.rsplit(".", 1)[0] + ".wf.png"
    wf_abs = (SITE / wf_rel).resolve()
    wf_html = (
        f'<div class="waveform-wrap" title="click to expand">'
        f'<img class="waveform" src="{wf_rel}" alt="audio waveform" width="480">'
        f'<div class="wf-playhead"></div>'
        f'</div>'
    ) if wf_abs.exists() else ""
    if kind == "audio":
        return (
            f'<div class="video-wrap">'
            f'<audio{id_attr} controls preload="none" src="{rel_path}"></audio>'
            f'{wf_html}'
            f'</div>'
        )
    elif kind == "video":
        # Probe fps from the on-disk asset (rel_path is relative to site/).
        fps = probe_fps(abs_path) if abs_path.exists() else None
        fps_attr = f' data-fps="{fps:.6f}"' if fps else ''
        disp_id = f"td-{dom_id}" if dom_id else ""
        disp_attr = f' id="{disp_id}"' if disp_id else ""
        return (
            f'<div class="video-wrap">'
            f'<video{id_attr}{fps_attr} controls preload="metadata" width="480" '
            f'tabindex="0" src="{rel_path}"></video>'
            f'<div class="time-disp"{disp_attr}>'
            f'<span class="cur">0.000</span> / <span class="tot">?</span> s '
            f'<span class="hint">← / → = 5 frames · Shift = 1 frame</span>'
            f'</div>'
            f'{wf_html}'
            f'</div>'
        )
    elif kind == "img":
        return f'<img src="{rel_path}" style="max-width:480px;border:1px solid #ccc">'
    return ""


def probe_duration_seconds(path: Path) -> float | None:
    """Return media duration in seconds via ffprobe, or None."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True,
        )
        return float(r.stdout.strip())
    except Exception:
        return None


def probe_fps(path: Path) -> float | None:
    """Return video frame rate via ffprobe, or None."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=r_frame_rate",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True,
        )
        rate = r.stdout.strip()
        if "/" in rate:
            num, den = rate.split("/")
            return float(num) / float(den) if float(den) != 0 else None
        return float(rate)
    except Exception:
        return None


def _fmt_time(t: float) -> str:
    """Format seconds as M:SS.cc or SS.cc s."""
    mins = int(t // 60)
    secs = t - mins * 60
    return f"{mins}:{secs:05.2f}" if mins else f"{secs:.2f}s"


def _tol_hint(data: dict) -> str:
    """Render a small tolerance hint for cut/glitch GT blocks."""
    tol  = data.get("tolerance_each_side_s")
    sthr = data.get("ssim_threshold")
    xthr = data.get("audio_xcorr_threshold")
    dthr = data.get("duration_tolerance_s")
    if tol is None and sthr is None: return ""
    parts = []
    if tol is not None: parts.append(f"endpoint ±{tol}s")
    if dthr is not None: parts.append(f"dur ±{dthr}s")
    if sthr is not None: parts.append(f"SSIM ≥ {sthr}")
    if xthr is not None: parts.append(f"audio xcorr ≥ {xthr}")
    return f' &nbsp; <span class="gt-tol">[{" · ".join(parts)}]</span>'


def render_gt_events(family: str, cuts_path: Path | None, duration_sec: float | None,
                     video_dom_id: str, ref_video_path: Path | None = None) -> str:
    """Render a clickable list of GT cut/glitch timestamps. Each row jumps the
    target video to that timestamp.

    family: 'cut' or 'glitch'
    video_dom_id: the HTML id of the <video> element to seek when a row is clicked.
    ref_video_path: used to probe fps for glitch tasks.
    """
    if cuts_path is None or not cuts_path.exists() or duration_sec is None or duration_sec <= 0:
        return ""
    try:
        data = json.loads(cuts_path.read_text())
    except Exception:
        return ""

    events = []  # list of dicts: {start_s, end_s, label, detail}

    if family == "cut":
        items = data.get("cuts", [])
        if not items and "window" in data:
            s, e = data["window"]
            items = [{"start_ms": s, "end_ms": e, "label": "segment"}]
        for c in items:
            s_ms = c.get("start_ms", c.get("start", 0))
            e_ms = c.get("end_ms", c.get("end", 0))
            # Pull the most informative text we have
            forb = c.get("forbidden_tokens") or []
            tok = (forb[0] if forb else c.get("token") or c.get("label") or c.get("type") or "segment")
            reason = c.get("reason", "")
            detail = reason or (f'"{tok}"' if tok else "")
            # Per-endpoint tolerance hint (overrides global if present).
            ts = c.get("tol_start_s")
            te = c.get("tol_end_s")
            if ts is not None or te is not None:
                detail = (detail + f"  [±{ts}s start / ±{te}s end]").strip()
            events.append({
                "start_s": s_ms / 1000.0,
                "end_s":   e_ms / 1000.0,
                "label":   tok,
                "detail":  detail,
            })
    elif family == "glitch":
        items = data.get("glitches", []) or data.get("cuts", [])
        fps = data.get("fps") or data.get("frame_rate")
        if fps is None and ref_video_path is not None:
            fps = probe_fps(ref_video_path)
        if fps is None:
            fps = 30.0
        for c in items:
            s_f = c.get("start_frame", 0)
            e_f = c.get("end_frame", s_f + 1)
            t   = c.get("type", "glitch")
            events.append({
                "start_s": s_f / fps,
                "end_s":   e_f / fps,
                "label":   t,
                "detail":  f"frames {s_f}–{e_f} (fps {fps:.2f})",
            })
    elif family == "sr_shot":
        # gt_shot.json: {start_frame, end_frame, target_description?}
        s_f = data.get("start_frame", 0)
        e_f = data.get("end_frame", 0)
        desc = data.get("target_description") or data.get("description") or "target shot"
        fps = probe_fps(ref_video_path) if ref_video_path else None
        if fps is None: fps = 30.0
        events.append({
            "start_s": s_f / fps,
            "end_s":   e_f / fps,
            "label":   "downsampled shot (restore)",
            "detail":  f"frames {s_f}–{e_f} — {desc}",
        })
    elif family in ("audio_inj", "mask_blur", "mask_color", "color_shot"):
        # window.json / gt_window.json: {"window_start_s", "window_end_s"}
        s = float(data.get("window_start_s", 0.0))
        e = float(data.get("window_end_s", 0.0))
        events.append({
            "start_s": s,
            "end_s":   e,
            "label":   "in-window (corruption)",
            "detail":  f"agent must fix [{s:.2f}s – {e:.2f}s]; out-of-window must stay clean (weighted 85% / 15%)",
        })
    elif family == "swap":
        # gt_swap.json: {swap: [{kind_in_original_slot, corrupted_start, corrupted_end}, ...]}
        # Prefer fps from json itself, falls back to probe.
        fps = None
        if "fps_num" in data and "fps_den" in data:
            try: fps = float(data["fps_num"]) / float(data["fps_den"])
            except Exception: pass
        if fps is None and ref_video_path is not None:
            fps = probe_fps(ref_video_path)
        if fps is None: fps = 30.0
        for entry in data.get("swap", []):
            s_f = entry.get("corrupted_start", entry.get("orig_start", 0))
            e_f = entry.get("corrupted_end", entry.get("orig_end", 0))
            kind = entry.get("kind_in_original_slot", entry.get("kind", "?"))
            events.append({
                "start_s": s_f / fps,
                "end_s":   e_f / fps,
                "label":   f"shot {kind.upper()} (out-of-order)",
                "detail":  f"frames {s_f}–{e_f} on corrupted timeline (belongs in original slot {kind.upper()})",
            })
    else:
        return ""

    if not events:
        return ""

    rows = []
    for i, ev in enumerate(events):
        s = ev["start_s"]; e = ev["end_s"]
        dur_ms = int(round((e - s) * 1000))
        # Inline onclick uses .currentTime — cross-browser supported.
        rows.append(f"""
<li>
  <button class="seek-btn" onclick="seekTo('{video_dom_id}', {s:.3f}); return false;">▶ {_fmt_time(s)}</button>
  <span class="ev-range">→ {_fmt_time(e)}</span>
  <span class="ev-dur">({dur_ms} ms)</span>
  <span class="ev-detail">{escape(ev["detail"])}</span>
</li>""")

    tol_hint = _tol_hint(data)
    # Family-aware header — what the agent should DO with this range varies.
    header_text = {
        "cut":        f"Ground-truth segments the agent should cut ({len(events)} total)",
        "glitch":     f"Ground-truth duplicated-frame ranges the agent should cut ({len(events)} total)",
        "color_shot": f"In-window bad color grade the agent should remove ({len(events)} total)",
        "sr_shot":    f"Downsampled shot the agent should restore ({len(events)} total)",
        "swap":       f"Out-of-order shot positions the agent should re-sequence ({len(events)} total)",
        "audio_inj":  f"In-window corruption range the agent should repair ({len(events)} total)",
        "mask_blur":  f"In-window corruption range the agent should repair ({len(events)} total)",
        "mask_color": f"In-window corruption range the agent should repair ({len(events)} total)",
    }.get(family, f"Ground-truth events ({len(events)} total)")
    return f"""
<div class="gt-events">
  <div class="gt-header">🟧 {header_text} — click ▶ to seek the video above{tol_hint}</div>
  <ol class="gt-list">{"".join(rows)}</ol>
</div>
"""


def reward_badge(o, c):
    """HTML span colored by oracle vs claude delta."""
    if o is None or c is None:
        return '<span class="badge nodata">—</span>'
    d = c - o
    if d > 0.02:
        cls = "win"; sym = "✅"
    elif abs(d) <= 0.02:
        cls = "tie"; sym = "≈"
    else:
        cls = "loss"; sym = "❌"
    return f'<span class="badge {cls}">{sym} {d:+.3f}</span>'


def render_reward_interp(g, corr, o, c) -> str:
    """Inline plain-language interpretation of the 4 numbers."""
    notes = []
    if g is not None and g < 0.95:
        notes.append(f'⚠️ Judge identity issue: feeding the clean reference scored only {g:.3f}, not 1.0 (judge formula clips below max).')
    if corr is not None and o is not None and o < corr - 0.02:
        notes.append(f'⚠️ Oracle ({o:.3f}) < corrupted-as-is ({corr:.3f}) — the reference DSP actually HURT compared to doing nothing.')
    if corr is not None and c is not None:
        if c < corr - 0.02:
            notes.append(f'❌ Claude ({c:.3f}) < corrupted-as-is ({corr:.3f}) — claude DAMAGED the input (over-processed).')
        elif c > corr + 0.02:
            notes.append(f'✅ Claude ({c:.3f}) > corrupted-as-is ({corr:.3f}) — claude actually improved over doing nothing.')
    if corr is not None and corr > 0.5:
        notes.append(f'⚠️ Calibration concern: corrupted-as-is is {corr:.3f} — task has high free-reward floor (consider harsher corruption for v3).')
    if not notes:
        return ""
    return "<ul>" + "".join(f'<li>{escape(n)}</li>' for n in notes) + "</ul>"


def _load_reward_details(task_id: str, mode: str) -> dict | None:
    """Return parsed reward.json details for the latest oracle ('smoke-') or
    claude ('cc-') job of `task_id`. None if no job or no reward.json."""
    prefix = "smoke-" if mode == "oracle" else "cc-"
    jobs = sorted((EXP / "jobs").glob(f"{prefix}{task_id}-*"),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    if not jobs:
        return None
    cands = list(jobs[0].glob("**/verifier/reward.json"))
    if not cands:
        return None
    try:
        d = json.load(cands[0].open())
        return d.get("details", d) if isinstance(d, dict) else None
    except Exception:
        return None


def _cut_glitch_rows(details: dict | None) -> list[str]:
    """Shared per-cut credit + honesty + reason rows for cut/glitch outputs.

    Used by both the v3 oracle renderer and the v4 claude renderer so the two
    cells show the same breakdown depth for passthrough (binary_range_f1)
    families. Returns a list of <li> strings (no <ul> wrapper).
    """
    if not details: return []
    rows = []
    ng = details.get("n_gt"); pc = details.get("passed_count")
    if ng is not None:
        rows.append(f"<li>per-cut credit: <b>{pc}/{ng}</b></li>")
    ssim = details.get("ssim"); xc = details.get("audio_xcorr")
    dd = details.get("duration_diff_s")
    diag = []
    if ssim is not None: diag.append(f"SSIM={ssim:.3f}")
    if xc is not None: diag.append(f"audio xcorr={xc:.3f}")
    if dd is not None: diag.append(f"dur Δ={dd:.3f}s")
    if diag:
        rows.append(f"<li>honesty: {' · '.join(diag)}</li>")
    if details.get("reason"):
        rows.append(f"<li class='reason'>{escape(str(details['reason']))}</li>")
    return rows


def _render_v4_sub_scores(family: str, v4d: dict, claude_reward: float | None,
                          claude_details: dict | None = None) -> str:
    """Render the v4-aware sub-score block for the claude output cell.

    Replaces the v3 in-window/out-window breakdown with the universal
    normalize-improvement template: metric, m_broken, m_golden, m_claude, and
    the calibrated reward. Concise — 3 short lines max for non-sr_shot families.

    For passthrough (cut/glitch) families, also surfaces the per-cut credit +
    honesty diagnostics from the claude reward.json so the claude cell matches
    the oracle cell's depth — see _cut_glitch_rows.
    """
    mu = v4d.get("metric_used", "?")
    mb = v4d.get("m_broken")
    mg = v4d.get("m_golden")
    mc = v4d.get("m_claude")
    cal = v4d.get("v4_calibrated_reward")
    details = v4d.get("details") or {}
    def _fmt(x):
        if x is None: return "—"
        try: return f"{float(x):.3g}"
        except Exception: return str(x)
    rows = []
    rows.append(
        f"<li>v4 calibrated reward: <b>{_fmt(cal)}</b>"
        f" &nbsp;<span class='axes'>(broken→0, golden→1 by construction)</span></li>"
    )
    if family in ("audio_inj", "color_shot", "mask_blur", "swap", "sr_shot"):
        rows.append(
            f"<li>metric: <code>{escape(str(mu))}</code> — "
            f"broken={_fmt(mb)}, golden={_fmt(mg)}, claude={_fmt(mc)}</li>"
        )
        rows.append(
            "<li class='axes'>universal formula: "
            "(M_out − M_broken) / (M_golden − M_broken), sign-flipped for lower-is-better</li>"
        )
        if family == "sr_shot":
            sub = details.get("sub_scores") or details.get("subscores")
            if isinstance(sub, dict) and sub:
                parts = [f"{k}={_fmt(v)}" for k, v in sub.items()]
                rows.append(f"<li class='axes'>sub-scores: {' · '.join(parts)}</li>")
            else:
                # Surface auxiliary diagnostic metrics if explicit sub_scores aren't present.
                aux_keys = [k for k in details.keys()
                            if k not in {"metric_primary", "in_window_only", "window",
                                         "window_frames", "n_frames_scored", "elapsed_s",
                                         "reason"}
                            and isinstance(details[k], dict)
                            and k != mu]
                if aux_keys:
                    parts = []
                    for k in aux_keys[:3]:
                        cl = details[k].get("claude")
                        if cl is not None:
                            parts.append(f"{k}={_fmt(cl)}")
                    if parts:
                        rows.append(f"<li class='axes'>aux diagnostics: {' · '.join(parts)}</li>")
    elif family in ("cut", "glitch"):
        rows.append(
            f"<li>metric: <code>{escape(str(mu) if mu and mu != '?' else 'binary_range_f1')}</code>"
            f" — v4 uses v3 logic unchanged (passthrough)</li>"
        )
        rows.extend(_cut_glitch_rows(claude_details))
    else:
        rows.append(
            f"<li>metric: <code>{escape(str(mu))}</code> — "
            f"broken={_fmt(mb)}, golden={_fmt(mg)}, claude={_fmt(mc)}</li>"
        )
    return f'<ul class="sub-scores">{"".join(rows)}</ul>'


def _render_sub_scores(family: str, details: dict | None) -> str:
    """Render a compact HTML sub-score breakdown for one video variant.
    Empty string if no details to render."""
    if not details: return ""
    rows = []
    if family == "color_shot":
        # Flipped, windowed verifier: in-window restoration vs out-window
        # preservation (LAB ΔE). 85/15 weighted.
        in_s = details.get("in_window_score")
        out_s = details.get("out_window_score")
        de_in = details.get("mean_deltaE_in_window_vs_original")
        de_out = details.get("mean_deltaE_out_window_vs_source")
        n_in = details.get("n_in_window_frames")
        n_out = details.get("n_out_window_frames")
        if in_s is not None:
            tail = f" &nbsp;(mean ΔE = {de_in:.2f}, lower=better)" if de_in is not None else ""
            n_tail = f" &nbsp;[{n_in} frames]" if n_in is not None else ""
            rows.append(f"<li>in-window restore (×0.85): <b>{in_s:.3f}</b>{tail}{n_tail}</li>")
        if out_s is not None:
            tail = f" &nbsp;(mean ΔE = {de_out:.2f}, lower=better)" if de_out is not None else ""
            n_tail = f" &nbsp;[{n_out} frames]" if n_out is not None else ""
            rows.append(f"<li>out-window preserve (×0.15): <b>{out_s:.3f}</b>{tail}{n_tail}</li>")
        # Fall back to legacy v1 fields if reward.json predates the flip.
        if in_s is None:
            legacy_match = details.get("in_shot_match")
            if legacy_match is not None:
                rows.append(f"<li>in-shot match (×0.7, legacy): <b>{legacy_match:.3f}</b></li>")
            iou = details.get("localization_iou")
            if iou is not None:
                rows.append(f"<li>localization IoU (×0.2, legacy): <b>{iou:.3f}</b></li>")
            psnr = details.get("mean_psnr_out_of_range_db")
            if psnr is not None:
                legacy_out = details.get("out_score", 0)
                rows.append(f"<li>preservation (×0.1, legacy): <b>{legacy_out:.3f}</b></li>")
    elif family == "cut" or family == "glitch":
        rows.extend(_cut_glitch_rows(details))
    elif family == "sr_shot":
        for k in ("localization_iou", "in_shot_psnr_db", "in_shot_lpips", "preservation_psnr_db"):
            if k in details and details[k] is not None:
                rows.append(f"<li>{k.replace('_',' ')}: <b>{details[k]:.3f}</b></li>")
    elif family == "swap":
        for k in ("whole_video_psnr_db", "whole_video_ssim"):
            if k in details and details[k] is not None:
                rows.append(f"<li>{k.replace('_',' ')}: <b>{details[k]:.3f}</b></li>")
    else:
        # generic: dump the first 4 scalar fields
        for k, v in list(details.items())[:6]:
            if isinstance(v, (int, float)):
                rows.append(f"<li>{escape(k)}: <b>{v:.3f}</b></li>")
    if not rows: return ""
    return f'<ul class="sub-scores">{"".join(rows)}</ul>'


def render_task_section(meta: dict, oracle: dict, claude: dict, costs: dict, golden: dict, corrupted: dict, v3_formula: dict, v4_details: dict) -> str:
    if meta.get("missing"):
        return ""
    tid = meta["task_id"]
    o = oracle.get(tid)
    c = claude.get(tid)
    cost = costs.get(tid)
    g = golden.get(tid)
    corr = corrupted.get(tid)
    v3f = v3_formula.get(tid)
    v4d = v4_details.get(tid)
    toml = meta["toml"]
    tags = ", ".join(toml.get("metadata", {}).get("tags", []))
    corruption = toml.get("metadata", {}).get("corruption", "n/a")
    source = toml.get("metadata", {}).get("source", "n/a")
    instr = meta["instruction"].strip()
    if len(instr) > 1200:
        instr = instr[:1200] + "\n\n..."

    f = meta["files"]
    asset_base = f"assets/{tid}/"

    # Default: audio_inj renders audio; if muxed video files are present, render as video.
    is_audio = meta["family"] == "audio_inj"
    media_kind = "audio" if is_audio else "video"
    if meta.get("render_as") == "video":
        media_kind = "video"

    # Pre-compute GT events list for cut / glitch families. The list rows
    # seek the relevant video element when clicked, so we assign DOM ids here.
    asset_dir = ASSETS / tid
    gt_cuts_file = f.get("gt_cuts")
    gt_cuts_path = (asset_dir / gt_cuts_file) if gt_cuts_file else None
    gt_events_html = ""
    clean_dom_id     = f"vid-{tid}-clean"
    corrupted_dom_id = f"vid-{tid}-corrupted"
    if meta["family"] == "cut":
        ref = asset_dir / f.get("clean", "")
        if ref.exists():
            gt_events_html = render_gt_events("cut", gt_cuts_path, probe_duration_seconds(ref),
                                              video_dom_id=clean_dom_id)
    elif meta["family"] == "glitch":
        ref = asset_dir / f.get("corrupted", "")
        if ref.exists():
            gt_events_html = render_gt_events("glitch", gt_cuts_path, probe_duration_seconds(ref),
                                              video_dom_id=corrupted_dom_id,
                                              ref_video_path=ref)
    elif meta["family"] == "color_shot":
        # Flipped color-shot: gt_window.json (time-windowed bad grade).
        ref = asset_dir / f.get("corrupted", "")
        gt_path = asset_dir / f.get("gt_window", "")
        if ref.exists() and gt_path.exists():
            gt_events_html = render_gt_events("color_shot", gt_path,
                                              probe_duration_seconds(ref),
                                              video_dom_id=corrupted_dom_id,
                                              ref_video_path=ref)
    elif meta["family"] == "sr_shot":
        ref = asset_dir / f.get("corrupted", "")
        gt_path = asset_dir / f.get("gt_shot", "")
        if ref.exists() and gt_path.exists():
            gt_events_html = render_gt_events("sr_shot", gt_path, probe_duration_seconds(ref),
                                              video_dom_id=corrupted_dom_id, ref_video_path=ref)
    elif meta["family"] == "swap":
        ref = asset_dir / f.get("corrupted", "")
        gt_path = asset_dir / f.get("gt_cuts", "")
        if ref.exists() and gt_path.exists():
            gt_events_html = render_gt_events("swap", gt_path, probe_duration_seconds(ref),
                                              video_dom_id=corrupted_dom_id, ref_video_path=ref)
    elif meta["family"] == "audio_inj":
        # window.json lives in the task's tests/ dir; copy/read it lazily.
        win_path = EXP / "tasks" / "agentic_vbench_repair" / tid / "steps/solve/tests/window.json"
        ref = asset_dir / f.get("corrupted", "")
        if win_path.exists() and ref.exists():
            gt_events_html = render_gt_events("audio_inj", win_path, probe_duration_seconds(ref),
                                              video_dom_id=corrupted_dom_id)
    elif meta["family"] in ("mask_blur", "mask_color"):
        # gt_window.json — emit the audio_inj-style in-window range banner.
        ref = asset_dir / f.get("corrupted", "")
        gt_path = asset_dir / f.get("gt_window", "")
        if gt_path.exists() and ref.exists():
            gt_events_html = render_gt_events(meta["family"], gt_path,
                                              probe_duration_seconds(ref),
                                              video_dom_id=corrupted_dom_id,
                                              ref_video_path=ref)

    # Build media grid
    media_html = []
    if "clean" in f:
        # For cut tasks the "clean source" IS the broken one (filler words to cut)
        if meta["family"] == "cut":
            label = "Source video (the agent's input — click the timestamps below to seek to each filler / segment)"
        elif meta["family"] == "color_shot":
            label = "Clean original (verifier's target — what the agent should restore the in-window range to)"
        else:
            label = "Clean source (ground truth — agent doesn't see this)"
        cell = f'<div class="media-cell"><label>📄 {escape(label)}</label>{media_tag(asset_base + f["clean"], media_kind, dom_id=clean_dom_id)}'
        if meta["family"] == "cut" and gt_events_html:
            cell += gt_events_html
        cell += '</div>'
        media_html.append(cell)
    if "corrupted" in f:
        if meta["family"] == "glitch":
            label = "Corrupted (the agent's input — click timestamps below to seek to each glitch)"
        elif meta["family"] == "sr_shot":
            label = "Corrupted (the agent's input — one shot is downsampled; click below to seek to it)"
        elif meta["family"] == "swap":
            label = "Corrupted (the agent's input — two shots out of order; click below to seek to the swap positions)"
        elif meta["family"] == "audio_inj":
            label = "Corrupted (the agent's input — corruption is window-scoped; click below to seek to the in-window range)"
        elif meta["family"] in ("mask_blur", "mask_color"):
            label = "Corrupted (the agent's input — corruption is window-scoped; click below to seek to the in-window range)"
        elif meta["family"] == "color_shot":
            label = "Broken (the agent's input — a bad colour grade has been applied to a window; click below to seek to it)"
        else:
            label = "Corrupted (the agent's input)"
        cell = f'<div class="media-cell"><label>🛠 {escape(label)}</label>{media_tag(asset_base + f["corrupted"], media_kind, dom_id=corrupted_dom_id)}'
        if meta["family"] in ("glitch", "sr_shot", "swap", "audio_inj", "mask_blur", "mask_color", "color_shot") and gt_events_html:
            cell += gt_events_html
        cell += '</div>'
        media_html.append(cell)
    if "noise_only" in f:
        media_html.append(f'<div class="media-cell"><label>🎚 Noise only (noisy − clean)</label>{media_tag(asset_base + f["noise_only"], media_kind)}</div>')
    if "mask" in f:
        media_html.append(f'<div class="media-cell"><label>🟪 Mask (white = region to repair)</label>{media_tag(asset_base + f["mask"], "img")}</div>')
    if "reference" in f:
        # Color-shot only: the "golden" reference video the verifier compares
        # the agent's output against. Score 1.0 = exact pixel match here.
        gt_path = asset_dir / "gt-shot.json"
        lut_note = ""
        if gt_path.exists():
            try:
                gtd = json.loads(gt_path.read_text())
                src = gtd.get("target_lut_source")
                lut_note = f' &nbsp;<span class="lut-src">[built from {escape(src)}]</span>' if src else ' &nbsp;<span class="lut-src">[built from hand-authored target ASC-CDL]</span>'
            except Exception:
                pass
        media_html.append(
            f'<div class="media-cell"><label>🎯 Reference (golden — verifier\'s target){lut_note}</label>'
            f'{media_tag(asset_base + f["reference"], media_kind)}</div>'
        )
    oracle_reward_str = f"{o:.3f}" if o is not None else "smoke failed / pending"
    oracle_subs = _render_sub_scores(meta["family"], _load_reward_details(tid, "oracle"))
    if v4d:
        claude_subs = _render_v4_sub_scores(
            meta["family"], v4d, c,
            _load_reward_details(tid, "claude") if meta["family"] in ("cut", "glitch") else None,
        )
    else:
        claude_subs = _render_sub_scores(meta["family"], _load_reward_details(tid, "claude"))
    if "oracle_output" in f:
        media_html.append(f'<div class="media-cell"><label>🤖 Oracle output (reward: {oracle_reward_str})</label>{media_tag(asset_base + f["oracle_output"], media_kind)}{oracle_subs}</div>')
    elif o is not None:
        media_html.append(f'<div class="media-cell"><label>🤖 Oracle output (reward: {oracle_reward_str})</label><em>output file not preserved</em>{oracle_subs}</div>')
    if "claude_output" in f:
        cc_reward = f"{c:.3f}" if c is not None else "—"
        media_html.append(f'<div class="media-cell"><label>🧠 Claude-code output (reward: {cc_reward})</label>{media_tag(asset_base + f["claude_output"], media_kind)}{claude_subs}</div>')
    elif c is not None:
        # Rollout ran but produced no output file (e.g., timed out, failed to write)
        media_html.append(f'<div class="media-cell"><label>🧠 Claude-code output (reward: {c:.3f})</label><em>⚠️ no output file — claude did not write the expected artifact (timeout or wrong path)</em>{claude_subs}</div>')
    else:
        media_html.append(f'<div class="media-cell"><label>🧠 Claude-code output</label><em>⏳ rollout pending or in flight</em></div>')

    media_block = '<div class="media-grid">' + "".join(media_html) + "</div>"

    # Reward summary
    o_str = f"{o:.3f}" if o is not None else "—"
    c_str = f"{c:.3f}" if c is not None else "—"
    cost_str = f"${cost:.3f}" if cost is not None else "(timeout — not recorded)"

    # GT cuts JSON pretty-print
    cuts_html = ""
    if "gt_cuts" in f:
        cuts_path = ASSETS / tid / f["gt_cuts"]
        try:
            cuts_data = json.loads(cuts_path.read_text())
            cuts_html = f'<details><summary>Ground-truth cuts ({len(cuts_data.get("cuts", cuts_data.get("glitches", [])))} events)</summary><pre>{escape(json.dumps(cuts_data, indent=2))}</pre></details>'
        except Exception:
            cuts_html = ""

    # Prompt-block: surface the natural-language prompt the agent received.
    # Two sources:
    #   1. workdir/prompt.txt (color-shot uses this — per-task prompt file)
    #   2. instruction.md "## Task prompt" section (content-cut uses this —
    #      a per-task prompt embedded inline in the markdown)
    prompt_html = ""
    prompt_path = EXP / "tasks" / "agentic_vbench_repair" / tid / "steps/solve/workdir/prompt.txt"
    prompt_text = None
    prompt_src = None
    if prompt_path.exists():
        try:
            t = prompt_path.read_text().strip()
            if t:
                prompt_text = t
                prompt_src = "materials/prompt.txt"
        except Exception:
            pass
    if not prompt_text:
        inst_path = EXP / "tasks" / "agentic_vbench_repair" / tid / "steps/solve/instruction.md"
        if inst_path.exists():
            try:
                md = inst_path.read_text()
                m = re.search(r"##\s*Task prompt\s*\n+(.*?)(?:\n##|\Z)", md, re.DOTALL)
                if m:
                    prompt_text = m.group(1).strip()
                    prompt_src = "instruction.md → Task prompt"
            except Exception:
                pass
    if prompt_text:
        prompt_html = (
            f'<div class="prompt-block"><div class="prompt-label">📝 '
            f'Prompt the agent received '
            f'(<code>{escape(prompt_src)}</code>):</div>'
            f'<blockquote class="prompt-text">{escape(prompt_text)}</blockquote></div>'
        )

    return f"""
<section id="{tid}" class="task task-{meta["family"]}">
  <h2>{meta["icon"]} {escape(tid)}</h2>
  <div class="task-meta">
    <div><strong>Family:</strong> {meta["family"]} &nbsp; <strong>Recipe:</strong> {escape(meta["recipe"])}</div>
    <div><strong>Source:</strong> {escape(source)}</div>
    <div><strong>Corruption applied:</strong> {escape(corruption)}</div>
    <div><strong>Tags:</strong> {escape(tags)}</div>
  </div>
  {prompt_html}

  <div class="reward-row">
    <div title="Judge fed the clean reference as the 'agent output'. Should be ≈1.0 for a well-formed judge."><strong>Golden:</strong> {f"{g:.3f}" if g is not None else "—"}</div>
    <div title="Judge fed the raw corrupted input (agent did nothing). The do-nothing floor."><strong>Corrupted-as-is:</strong> {f"{corr:.3f}" if corr is not None else "—"}</div>
    <div><strong>Oracle:</strong> {o_str}</div>
    <div><strong>Claude:</strong> {c_str}</div>
    <div>{reward_badge(o, c)}</div>
    <div><strong>Cost:</strong> {cost_str}</div>
  </div>
  {f'<div class="formula-note"><strong>v3 judge formula:</strong> <code>{escape(v3f)}</code></div>' if v3f else ''}
  <div class="reward-interp">{render_reward_interp(g, corr, o, c)}</div>

  <details open>
    <summary><strong>Instruction (what the agent reads)</strong></summary>
    <pre class="instruction">{escape(instr)}</pre>
  </details>

  <h3>Media</h3>
  {media_block}

  {cuts_html}
</section>
"""


def render_summary_table(metas, oracle, claude, costs, golden, corrupted) -> str:
    rows = []
    for m in metas:
        if m.get("missing"):
            continue
        tid = m["task_id"]
        o = oracle.get(tid)
        c = claude.get(tid)
        g = golden.get(tid)
        corr = corrupted.get(tid)
        cost = costs.get(tid)
        # Highlight calibration issues
        g_cell = f"{g:.3f}" if g is not None else "—"
        g_class = "num warn" if (g is not None and g < 0.95) else "num"
        corr_cell = f"{corr:.3f}" if corr is not None else "—"
        corr_class = "num warn" if (corr is not None and corr > 0.5) else "num"
        rows.append(f"""
<tr>
  <td><a href="#{tid}">{m["icon"]} {escape(tid)}</a></td>
  <td>{m["family"]}</td>
  <td class="{g_class}" title="Golden = judge fed clean as output. Should be 1.0.">{g_cell}</td>
  <td class="{corr_class}" title="Corrupted-as-is = judge fed raw corrupted input as output. The do-nothing floor.">{corr_cell}</td>
  <td class="num">{f"{o:.3f}" if o is not None else "—"}</td>
  <td class="num">{f"{c:.3f}" if c is not None else "—"}</td>
  <td class="num">{reward_badge(o, c)}</td>
  <td class="num">{f"${cost:.3f}" if cost is not None else "<em>timeout</em>"}</td>
</tr>""")
    return f"""
<table class="summary">
  <thead><tr>
    <th>Task</th><th>Family</th>
    <th class="num" title="Should be 1.0 — judge identity test">Golden</th>
    <th class="num" title="Score if agent does nothing — the floor">Corrupt</th>
    <th class="num">Oracle</th>
    <th class="num">Claude</th>
    <th class="num">Δ (vs Oracle)</th>
    <th class="num">Cost</th>
  </tr></thead>
  <tbody>{"".join(rows)}</tbody>
</table>
"""


CSS = """
  body { font-family: -apple-system, "SF Pro Text", system-ui, sans-serif; max-width: 1100px; margin: 0 auto; padding: 24px; color: #222; line-height: 1.5; }
  h1 { border-bottom: 2px solid #333; padding-bottom: 6px; }
  h2 { background: #f6f8fa; padding: 8px 12px; border-radius: 6px; margin-top: 36px; }
  h3 { color: #555; margin-top: 24px; }
  .summary { border-collapse: collapse; width: 100%; margin: 20px 0; font-size: 14px; }
  .summary th, .summary td { padding: 6px 10px; border-bottom: 1px solid #eee; text-align: left; }
  .summary th { background: #f0f0f0; }
  .summary .num { text-align: right; font-variant-numeric: tabular-nums; }
  .summary .warn { background: #fff8e1; }
  .reward-interp ul { margin: 6px 0; padding-left: 22px; font-size: 13px; }
  .reward-interp li { margin: 2px 0; color: #555; }
  .formula-note { font-size: 12px; color: #555; margin: 6px 0; padding: 4px 8px; background: #f0f7ff; border-left: 3px solid #4a90e2; border-radius: 3px; }
  .formula-note code { background: transparent; font-size: 11px; }
  .summary a { color: #0366d6; text-decoration: none; }
  .summary a:hover { text-decoration: underline; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; font-weight: 600; }
  .badge.win  { background: #d4f3d4; color: #1c6b1c; }
  .badge.tie  { background: #f0f0f0; color: #555; }
  .badge.loss { background: #fbd3d3; color: #872929; }
  .badge.nodata { background: #f0f0f0; color: #888; }
  .task { margin: 40px 0; padding: 20px; border: 1px solid #e1e4e8; border-radius: 8px; background: #fafbfc; }
  .task-meta { font-size: 13px; color: #555; margin-bottom: 10px; }
  .task-meta div { margin: 2px 0; }
  .reward-row { display: flex; gap: 24px; margin: 10px 0 20px 0; padding: 8px 12px; background: #fff; border-radius: 6px; border: 1px solid #ddd; }
  .reward-row strong { color: #333; }
  .media-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 16px; margin: 12px 0; }
  .media-cell { padding: 10px; background: #fff; border-radius: 6px; border: 1px solid #ddd; }
  .media-cell label { display: block; font-size: 12px; font-weight: 600; margin-bottom: 6px; color: #444; }
  .media-cell audio { width: 100%; }
  .media-cell video { max-width: 100%; height: auto; }
  details { margin: 12px 0; }
  details summary { cursor: pointer; padding: 6px; user-select: none; }
  details pre.instruction { background: #f6f8fa; padding: 12px; border-radius: 6px; max-height: 320px; overflow: auto; font-size: 12px; line-height: 1.4; white-space: pre-wrap; }
  details pre { background: #f6f8fa; padding: 12px; border-radius: 6px; max-height: 280px; overflow: auto; font-size: 11px; }
  .task-audio_inj { border-left: 4px solid #4a90e2; }
  .task-glitch   { border-left: 4px solid #e94e77; }
  .task-cut      { border-left: 4px solid #f5a623; }
  .task-mask_color { border-left: 4px solid #50e3c2; }
  .task-mask_blur  { border-left: 4px solid #9013fe; }
  .task-color_shot { border-left: 4px solid #2ecc71; }
  .task-sr_shot    { border-left: 4px solid #ff6b6b; }
  .task-swap       { border-left: 4px solid #ffc107; }
  .legend { font-size: 12px; color: #666; }
  .legend span { margin-right: 16px; padding: 2px 8px; border-radius: 4px; }
  /* Timeline bar showing GT cut/glitch windows */
  .timeline { margin-top: 6px; padding: 4px 2px; }
  .timeline .track { position: relative; height: 14px; background: #e8e8e8; border-radius: 3px; overflow: hidden; }
  .timeline .track .cut { position: absolute; top: 0; bottom: 0; background: #ff8c00; opacity: 0.85; }
  .timeline .ticks { position: relative; height: 14px; font-size: 10px; color: #888; }
  .timeline .ticks span { position: absolute; transform: translateX(-50%); white-space: nowrap; }
  .timeline .ticks span:first-child { transform: translateX(0); }
  .timeline .ticks span:last-child { transform: translateX(-100%); }
  .timeline .legend-small { font-size: 11px; color: #555; margin-top: 14px; }
  /* GT events list (clickable timestamps) */
  .video-wrap { display: inline-block; }
  .video-wrap video { display: block; outline: none; }
  .video-wrap video:focus { box-shadow: 0 0 0 2px #4a90e2; }
  .time-disp { font: 11px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; color: #444; padding: 2px 4px; background: #f3f3f3; border-top: 1px solid #ddd; max-width: 480px; }
  .time-disp .cur, .time-disp .tot { font-variant-numeric: tabular-nums; }
  .time-disp .hint { color: #888; margin-left: 8px; font-size: 10px; }
  .waveform-wrap { position: relative; max-width: 480px; line-height: 0; }
  .waveform { display: block; max-width: 480px; height: 48px; border: 1px solid #ddd; border-top: 0; background: #fafafa; }
  .wf-playhead { position: absolute; top: 0; bottom: 0; width: 2px; background: #e74c3c; pointer-events: none; transform: translateX(-1px); transition: left 0.05s linear; }
  .waveform-wrap { cursor: zoom-in; }
  .wf-modal { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.88); z-index: 1000; align-items: center; justify-content: center; padding: 32px; }
  .wf-modal.open { display: flex; }
  .wf-modal-inner { position: relative; width: 90vw; max-width: 1800px; }
  .wf-modal img { display: block; width: 100%; height: auto; background: #fafafa; border: 1px solid #555; cursor: zoom-out; }
  .wf-modal .wf-playhead-big { position: absolute; top: 0; bottom: 0; width: 3px; background: #e74c3c; pointer-events: none; transform: translateX(-1.5px); }
  .wf-modal-cap { color: #ccc; font: 12px ui-monospace, Menlo, monospace; margin-bottom: 8px; }
  .wf-modal-cap .wf-cur { color: #fff; font-weight: bold; }
  .wf-modal-close { position: absolute; top: -32px; right: 0; color: #fff; background: transparent; border: 0; font-size: 22px; cursor: pointer; padding: 0 6px; }
  .gt-events { margin-top: 8px; padding: 8px 10px; background: #fff8e8; border-left: 3px solid #ff8c00; border-radius: 4px; }
  .gt-events .gt-header { font-size: 12px; color: #444; margin-bottom: 6px; }
  .gt-events .gt-list { list-style: decimal; margin: 0; padding-left: 22px; font-size: 13px; }
  .gt-events .gt-list li { margin: 3px 0; line-height: 1.7; }
  .gt-events .seek-btn { background: #ff8c00; color: #fff; border: 0; border-radius: 3px; padding: 2px 8px; font-family: inherit; font-size: 12px; cursor: pointer; font-variant-numeric: tabular-nums; }
  .gt-events .seek-btn:hover { background: #e07b00; }
  .gt-events .ev-range { color: #888; font-size: 12px; font-variant-numeric: tabular-nums; margin-left: 4px; }
  .gt-events .ev-dur { color: #999; font-size: 11px; margin-left: 4px; }
  .gt-events .gt-tol { color: #555; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; background: #ffe8c2; padding: 1px 6px; border-radius: 3px; }
  .prompt-block { margin: 10px 0; padding: 10px 14px; background: #eef5ff; border-left: 3px solid #4a90e2; border-radius: 4px; }
  .prompt-block .prompt-label { font-size: 12px; color: #444; margin-bottom: 4px; }
  .prompt-block .prompt-text { margin: 4px 0 0; font-style: italic; color: #222; line-height: 1.45; font-size: 13px; white-space: pre-wrap; }
  .sub-scores { margin: 6px 0 0; padding-left: 18px; font-size: 12px; color: #333; line-height: 1.55; }
  .sub-scores li { margin: 1px 0; font-variant-numeric: tabular-nums; }
  .sub-scores .axes { color: #666; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; }
  .sub-scores .reason { color: #888; font-size: 11px; font-style: italic; list-style: none; margin-left: -18px; }
  .lut-src { color: #666; font-size: 11px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-weight: normal; background: #eef5ff; padding: 1px 6px; border-radius: 3px; }
  .gt-events .ev-detail { color: #333; margin-left: 8px; }
  .v4-banner { margin: 14px 0 18px 0; padding: 12px 14px; background: #fff4e5; border-left: 4px solid #ff8c00; border-radius: 4px; font-size: 13px; line-height: 1.5; color: #333; }
  .v4-banner code { background: #ffe6c2; padding: 1px 5px; border-radius: 3px; font-size: 12px; }
"""


def build_site():
    SITE.mkdir(exist_ok=True)
    ASSETS.mkdir(exist_ok=True)

    oracle, claude, costs, golden, corrupted, v3_formula, v4_details = load_results()
    print(f"Loaded results: oracle={len(oracle)} claude={len(claude)} costs={len(costs)} golden={len(golden)} corrupted={len(corrupted)} v3={len(v3_formula)} v4={len(v4_details)}")

    # Filter out deprecated tasks the user has retired from the suite.
    DEPRECATED = {
        "exp-color-grade-gobelins-task01-v1-bbox-archived",
        "exp-color-grade-visit-korea-task01-v1-bbox-archived",
        "exp-disfluency-pitch-meeting-task01",
    }
    task_ids = sorted([d.name for d in (EXP / "tasks" / "agentic_vbench_repair").iterdir()
                       if d.is_dir() and d.name.startswith("exp-")
                       and d.name not in DEPRECATED])
    metas = []
    for tid in task_ids:
        print(f"  gathering {tid} ...")
        metas.append(gather_task_assets(tid))

    # Safety net: re-encode any leftover .mp4 in site/assets that gather skipped
    # (e.g., archived task dirs that no longer exist under tasks/). Idempotent.
    print("  ensuring all-keyframe encode across all asset .mp4 files ...")
    for v in sorted(ASSETS.glob("*/*.mp4")):
        _all_keyframe_reencode(v)

    # Sort by family then name for readable order.
    family_order = {"audio_inj": 0, "glitch": 1, "cut": 2, "color_shot": 3, "mask_color": 4, "mask_blur": 5, "sr_shot": 6, "swap": 7}
    metas.sort(key=lambda m: (
        family_order.get(m.get("family", "?"), 99),
        m["task_id"],
    ))

    summary = render_summary_table(metas, oracle, claude, costs, golden, corrupted)
    sections = "\n".join(render_task_section(m, oracle, claude, costs, golden, corrupted, v3_formula, v4_details) for m in metas)

    mean_oracle = sum(oracle.values()) / max(1, len(oracle))
    mean_claude = sum(claude.values()) / max(1, len(claude))
    total_cost = sum(costs.values())

    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>agentic-vbench v4 — overnight experiment results</title>
<style>{CSS}</style>
<script>
function seekTo(videoId, t) {{
  const v = document.getElementById(videoId);
  if (!v) {{ console.warn('video not found: ' + videoId); return; }}
  v.currentTime = t;
  v.play().catch(() => {{ /* autoplay blocked is fine — user already clicked */ }});
  v.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
}}

// Fine-grained arrow-key seek + ms-precision time readout for every <video>.
// ArrowRight/Left = 5 frames, Shift+ArrowRight/Left = 1 frame.
// Falls back to 1/30s if fps unknown.
document.addEventListener('DOMContentLoaded', () => {{
  document.querySelectorAll('video').forEach((v) => {{
    const fps = parseFloat(v.dataset.fps) || 30.0;
    const oneFrame = 1.0 / fps;
    // Find the sibling .time-disp via the .video-wrap parent (works for every
    // video, with or without an explicit id).
    const wrap  = v.closest('.video-wrap');
    const disp  = wrap ? wrap.querySelector('.time-disp') : null;
    const curEl = disp ? disp.querySelector('.cur') : null;
    const totEl = disp ? disp.querySelector('.tot') : null;
    const ph = wrap ? wrap.querySelector('.wf-playhead') : null;
    const wf = wrap ? wrap.querySelector('.waveform') : null;
    const updateTime = () => {{
      if (curEl) curEl.textContent = v.currentTime.toFixed(3);
      if (ph && wf && isFinite(v.duration) && v.duration > 0) {{
        const w = wf.clientWidth || wf.naturalWidth || 480;
        ph.style.left = ((v.currentTime / v.duration) * w) + 'px';
      }}
    }};
    const setDuration = () => {{
      if (totEl && isFinite(v.duration)) totEl.textContent = v.duration.toFixed(3);
    }};
    v.addEventListener('loadedmetadata', () => {{ setDuration(); updateTime(); }});
    v.addEventListener('durationchange', setDuration);
    // Race-safe: metadata may have already loaded before this script ran.
    if (v.readyState >= 1) setDuration();
    else {{
      // Force the browser to fetch metadata even with preload="metadata" stalled.
      v.load();
    }}
    v.addEventListener('timeupdate', updateTime);
    v.addEventListener('seeked',     updateTime);
    // Track which video is "active" — last one clicked. Chrome routes keydown
    // through the video's shadow-DOM controls so listening on the <video>
    // element directly doesn't see arrow keys before the native handler fires.
    v.addEventListener('click', () => {{ window.__activeVideo = v; }});
    v.addEventListener('focus', () => {{ window.__activeVideo = v; }});
  }});

  // Capture-phase keyboard handler at document level — runs before Chrome's
  // shadow-DOM video controls. Redirects to the last clicked/focused video.
  document.addEventListener('keydown', (e) => {{
    if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
    const v = window.__activeVideo;
    if (!v || v.tagName !== 'VIDEO') return;
    // Don't hijack arrows when typing in inputs.
    const tag = (document.activeElement && document.activeElement.tagName) || '';
    if (tag === 'INPUT' || tag === 'TEXTAREA') return;
    e.preventDefault();
    e.stopPropagation();
    const fps = parseFloat(v.dataset.fps) || 30.0;
    const frames = e.shiftKey ? 1 : 5;
    const dir = (e.key === 'ArrowRight') ? +1 : -1;
    v.pause();
    v.currentTime = Math.max(0, v.currentTime + dir * frames / fps);
  }}, true);  // capture = true so we run BEFORE shadow-DOM handlers

  // Click-to-expand on every waveform — shows a shared modal with a synced
  // playhead. The modal tracks whichever video the waveform belongs to.
  const modal = document.getElementById('wf-modal');
  const modalImg = modal.querySelector('img');
  const modalHead = modal.querySelector('.wf-playhead-big');
  const modalCur = modal.querySelector('.wf-cur');
  const modalTot = modal.querySelector('.wf-tot');
  const modalTask = modal.querySelector('.wf-task');
  let modalVideo = null;
  let modalRaf = null;

  function syncModal() {{
    if (!modal.classList.contains('open') || !modalVideo) {{ modalRaf = null; return; }}
    if (isFinite(modalVideo.duration) && modalVideo.duration > 0) {{
      const w = modalImg.clientWidth;
      modalHead.style.left = ((modalVideo.currentTime / modalVideo.duration) * w) + 'px';
      modalCur.textContent = modalVideo.currentTime.toFixed(3);
      if (modalTot.textContent === '?') modalTot.textContent = modalVideo.duration.toFixed(3);
    }}
    modalRaf = requestAnimationFrame(syncModal);
  }}
  function openModal(v, src, caption) {{
    modalVideo = v;
    modalImg.src = src;
    modalTask.textContent = caption || '';
    modalCur.textContent = '0.000';
    modalTot.textContent = isFinite(v.duration) ? v.duration.toFixed(3) : '?';
    modal.classList.add('open');
    if (!modalRaf) modalRaf = requestAnimationFrame(syncModal);
  }}
  function closeModal() {{
    modal.classList.remove('open');
    modalVideo = null;
    if (modalRaf) {{ cancelAnimationFrame(modalRaf); modalRaf = null; }}
  }}
  document.querySelectorAll('.waveform-wrap').forEach((wrap) => {{
    wrap.addEventListener('click', (e) => {{
      const vWrap = wrap.closest('.video-wrap');
      const v = vWrap ? vWrap.querySelector('video') : null;
      const img = wrap.querySelector('img');
      if (!v || !img) return;
      // Caption: nearest sibling <label> if present (e.g., "🤖 Oracle output ...")
      const cell = wrap.closest('.media-cell');
      const lab = cell ? cell.querySelector('label') : null;
      const caption = lab ? lab.textContent : '';
      openModal(v, img.src, caption);
    }});
  }});
  modal.addEventListener('click', (e) => {{ if (e.target === modal) closeModal(); }});
  modal.querySelector('.wf-modal-close').addEventListener('click', closeModal);
  document.addEventListener('keydown', (e) => {{
    if (e.key === 'Escape' && modal.classList.contains('open')) closeModal();
  }});
}});
</script>
</head>
<body>
<div id="wf-modal" class="wf-modal">
  <div class="wf-modal-inner">
    <button class="wf-modal-close" type="button" aria-label="close">×</button>
    <div class="wf-modal-cap"><span class="wf-task"></span> &nbsp; <span class="wf-cur">0.000</span> / <span class="wf-tot">?</span> s &nbsp; <span style="color:#888">← / → = 5 frames · Shift = 1 frame · Esc to close</span></div>
    <img alt="audio waveform (large)">
    <div class="wf-playhead-big"></div>
  </div>
</div>
<h1>agentic-vbench v4 — overnight experiment</h1>
<div class="v4-banner">
  <strong>v4 verifier</strong> — broken=0 and golden=1 by construction.
  Universal normalize-improvement formula:
  <code>(M_out − M_broken) / (M_golden − M_broken)</code>
  (sign-flipped for lower-is-better metrics).
  See <code>scripts/v4/V4_DESIGN.md</code>.
  Tasks with a v4 row ({len(v4_details)}) have their Claude/Golden/Corrupt columns overridden;
  passthrough families (cut/glitch) keep v3 logic unchanged.
</div>
<div class="v4-banner" style="background:#fff0f0; border-left-color:#cc3333">
  <strong>Oracle status</strong> —
  12 oracle <code>solve.sh</code> files were audited and found to be
  passthrough or best-effort (not "ceiling-proof"). All 12 have been
  rewritten (commit <code>scripts/v4/fix_oracle_solve_sh.py</code>) to
  copy the bundled golden reference into <code>solution/&lt;file&gt;</code>
  and <code>cp</code> it to the output. <strong>Oracle smoke runs need
  to be re-rolled</strong> for the dashboard scores below to update —
  current oracle artifacts predate the fix. Projected v4 oracle after
  re-rollout: <strong>1.000 for all 12 fixed tasks</strong>.
</div>
<p><strong>Date:</strong> 2026-05-13 02:50–04:55 PST. <strong>Tasks built:</strong> {len(metas)} of 19 (SR ×2 + swap ×2 deferred — need GPU judge).</p>
<p><strong>Headline:</strong> mean oracle <strong>{mean_oracle:.3f}</strong>, mean claude-code <strong>{mean_claude:.3f}</strong>. Claude beat oracle on {sum(1 for m in metas if (c:=claude.get(m["task_id"])) is not None and (o:=oracle.get(m["task_id"])) is not None and c-o > 0.02)} tasks, tied on {sum(1 for m in metas if (c:=claude.get(m["task_id"])) is not None and (o:=oracle.get(m["task_id"])) is not None and abs(c-o) <= 0.02)}, lost on {sum(1 for m in metas if (c:=claude.get(m["task_id"])) is not None and (o:=oracle.get(m["task_id"])) is not None and c-o < -0.02)}. Measured cost: <strong>${total_cost:.2f}</strong> (3 timeouts not counted).</p>

<p class="legend">
  <span style="background:#d4f3d4">✅ claude beats oracle by >0.02</span>
  <span style="background:#f0f0f0">≈ tie within ±0.02</span>
  <span style="background:#fbd3d3">❌ claude loses by >0.02</span>
</p>

<h2 style="background:transparent;padding:0">Summary</h2>
{summary}

<h2 style="background:transparent;padding:0">How to read the per-task sections</h2>
<ul style="font-size:14px">
  <li><strong>Clean source</strong> — the ground truth the agent never sees. Used by the judge to score the agent's output.</li>
  <li><strong>Corrupted</strong> — exactly what the agent receives as input.</li>
  <li><strong>Noise only</strong> (audio injection tasks) — computed as <code>noisy − clean</code>. Lets you listen to <em>just</em> what was injected.</li>
  <li><strong>Oracle output</strong> — the reference baseline (passthrough / noisereduce / inverse-LUT, depending on task). Defines the "competent baseline" reward.</li>
  <li><strong>Claude-code output</strong> — the actual claude-sonnet-4-6 rollout artifact. Listen / watch to see what the agent produced.</li>
  <li><strong>Mask</strong> (mask tasks) — white pixels = region the agent must restore; black = preserved.</li>
  <li><strong>Ground-truth cuts</strong> (glitch / cut tasks) — the exact frame indices or millisecond windows the judge expects to be absent in the agent's output.</li>
</ul>

{sections}

<hr>
<p style="font-size:12px;color:#888">Generated by <code>experiment/scripts/build_site_v4.py</code>. Static site, no JS, no external resources. Move the <code>experiment/site/</code> folder anywhere and it still works.</p>
</body>
</html>
"""

    out = SITE / "index-v4.html"
    out.write_text(html)
    print(f"\nWrote {out}")
    print(f"Total asset size:")
    import subprocess
    print(subprocess.check_output(["du", "-sh", str(ASSETS)]).decode())


if __name__ == "__main__":
    build_site()
