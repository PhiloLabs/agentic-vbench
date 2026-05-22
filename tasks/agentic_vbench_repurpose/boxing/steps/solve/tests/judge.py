"""v5 judge — per-item grading with prompt caching per pillar.

For one rollout:
  - Pillar 0 (format): deterministic programmatic checks
  - Pillars 1/2/3: one Opus call per item, with pillar-shared evidence cached

Writes results/<run_id>_p{N}.json (same shape the inspect expects).
"""
from __future__ import annotations
import base64, io, json, os, re, subprocess, sys, tempfile, time
from pathlib import Path

import numpy as np
import yaml
import anthropic

from PIL import Image
import librosa

def _find_config_yaml():
    env = os.environ.get('CUTBENCH_CONFIG')
    if env and Path(env).exists():
        return env
    # Walk up from this file looking for config.yaml (supports both the repo
    # layout and workspace copies where eval_tools/ is 2 levels deep).
    p = Path(__file__).resolve()
    for _ in range(6):
        p = p.parent
        cand = p / 'config.yaml'
        if cand.exists():
            return str(cand)
    raise FileNotFoundError("config.yaml not found; set CUTBENCH_CONFIG")

CFG = yaml.safe_load(Path(_find_config_yaml()).read_text())
os.environ.setdefault("ANTHROPIC_API_KEY", CFG["api_keys"]["anthropic"])

JUDGE_MODEL = "claude-opus-4-7"
GEMINI_AUDIO_MODEL = "gemini-3.1-pro-preview"  # native audio; more reliable than Flash on sound judging
GEMINI_AI_STUDIO_KEY = os.environ.get("GEMINI_API_KEY", CFG.get("api_keys", {}).get("gemini", ""))
REPURPOSE_ONLY = os.environ.get("CUTBENCH_REPURPOSE_ONLY", "").lower() in {"1", "true", "yes"}


def resolve_workspace_from_run_dir(run_dir: str) -> Path:
    """run_dir is <workspace>/runs/<run_id>. Workspace is its grandparent."""
    return Path(run_dir).resolve().parent.parent


def _score_max(item: dict, passed: bool) -> tuple[int, int]:
    """Score and max for an item given its pass/fail.

    Three modes:
      positive weight: score = w if passed else 0; max = w (contributes to ceiling).
      negative + narrative_essential=True: criterion describes the GOOD state
        (e.g. "the convulsion appears"). pass=true means good state present →
        score=0 (no penalty). pass=false means good state missing → score=w (penalty).
        max=0 (penalties don't add to positive ceiling).
      negative + no flag (P4 violation): criterion describes the BAD state.
        pass=true means violation present → score=w (penalty applied).
        pass=false means clean → score=0. max=0.
    """
    w = item["weight"]
    if w >= 0:
        return (w if passed else 0), w
    if item.get("narrative_essential"):
        return (w if not passed else 0), 0
    return (w if passed else 0), 0


def load_rubric_and_context(workspace: Path) -> tuple[dict, str]:
    rubric = json.loads((workspace / "rubric.json").read_text())
    if REPURPOSE_ONLY:
        task_context = (
            "Repurpose-only verifier mode: grade using only the submitted repurpose video "
            "and the rubric item text. Do not assume access to the source video, "
            "input brief, hidden understanding notes, or a golden reference."
        )
        return rubric, task_context
    stage1_path = workspace / "stage1_understanding.md"
    if stage1_path.exists():
        stage1 = stage1_path.read_text()
        # Grab the plot synopsis paragraph (first non-heading chunk after "synopsis")
        para = ""
        for block in stage1.split("\n\n"):
            if "synopsis" in block.lower() or len(block.split()) > 40:
                para = block.strip()[:800]
                break
        if not para:
            para = stage1[:500]
        task_context = para
    else:
        task_context = "An AI agent was asked to produce a 60-second narrative repurpose of a source film with a new voice-over."
    return rubric, task_context


# These get set at module level for convenience in the rest of the code,
# but actual resolution happens in main() based on the passed run_dir.
BASE: Path = Path.cwd()
RUBRIC: dict = {}
TASK_CONTEXT: str = ""


def probe(path: str) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", path],
        capture_output=True, text=True)
    return json.loads(r.stdout) if r.stdout else {}


def extract_frame_at(path: str, t: float, max_w: int = 480) -> Image.Image | None:
    with tempfile.TemporaryDirectory() as td:
        fp = f"{td}/f.jpg"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
                        "-ss", f"{t:.3f}", "-i", path, "-vframes", "1", fp], check=False)
        if os.path.exists(fp):
            return Image.open(fp).copy()
    return None


def img_b64(img: Image.Image, max_w: int = 480) -> str:
    if img.width > max_w:
        img = img.copy()
        img.thumbnail((max_w, max_w))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=72)
    return base64.b64encode(buf.getvalue()).decode()


def image_block(img: Image.Image, max_w: int = 480) -> dict:
    return {"type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg",
                       "data": img_b64(img, max_w)}}


def whisper_segments(path: str) -> list[dict]:
    """Transcribe spoken audio. Lets Whisper auto-detect language so foreign-language
    audio (Korean in Parasite/Oldboy, Cantonese in ITMFL) is transcribed in its native
    script rather than mis-transcribed as English phonemes. Each segment also includes
    a 'language' field at the result level so downstream items can check what was heard.
    """
    import whisper
    m = whisper.load_model("base", device="cpu")
    r = m.transcribe(path, fp16=False, language=None, task="transcribe", verbose=False)
    segs = r.get("segments", [])
    # Annotate each segment with the detected language so consumers can filter
    lang = r.get("language", "")
    for s in segs:
        s.setdefault("language", lang)
    return segs


def vo_at_second(segments: list[dict], t: float) -> str:
    for s in segments:
        if s["start"] <= t < s["end"]:
            return s["text"].strip()
    for s in segments:
        if abs((s["start"] + s["end"]) / 2 - t) < 1.5:
            return s["text"].strip()
    return ""


def scene_cut_times(path: str) -> list[float]:
    from scenedetect import detect, ContentDetector
    return [s[0].get_seconds() for s in detect(path, ContentDetector(threshold=27))]


# ---------- Pillar 0 deterministic scoring ----------


def ocr_last_5s(path: str) -> str:
    import pytesseract
    dur = float(probe(path)["format"]["duration"])
    text = []
    with tempfile.TemporaryDirectory() as td:
        for t in np.linspace(max(0.0, dur - 5.0), dur - 0.1, 6):
            fp = f"{td}/f_{t:.2f}.png"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
                            "-ss", f"{t:.3f}", "-i", path, "-vframes", "1", fp], check=False)
            if os.path.exists(fp):
                text.append(pytesseract.image_to_string(Image.open(fp)))
    return "\n".join(text)


def distinct_source_bin_hit_first_15s(repurpose: str, source: str) -> tuple[bool, str]:
    """P0.REORDER_HOOK — find a story shot (source ≥172s and ≤200s) in first 15s of repurpose."""
    import imagehash
    src_dur = float(probe(source)["format"]["duration"])
    # Sample dense source frames in the STORY late-third range [172, 200]
    src_hashes = []
    for t in np.linspace(172, min(200, src_dur), 20):
        with tempfile.TemporaryDirectory() as td:
            fp = f"{td}/f.jpg"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
                            "-ss", f"{t:.3f}", "-i", source, "-vframes", "1",
                            "-vf", "scale=256:-1", fp], check=False)
            if os.path.exists(fp):
                src_hashes.append((t, imagehash.phash(Image.open(fp))))
    # Sample repurpose first 15s
    for t in np.linspace(0.5, 14.5, 15):
        f = extract_frame_at(repurpose, float(t), max_w=256)
        if f is None:
            continue
        h = imagehash.phash(f)
        for src_t, sh in src_hashes:
            if (h - sh) <= 14:
                return True, f"repurpose t={t:.1f}s matches source t={src_t:.1f}s (phash dist ≤14)"
    return False, "no story-range (172–200s) match found in repurpose's first 15s"


def _check_duration(dur, source_dur=None, item: dict | None = None):
    """Parse target duration (and tolerance) from the rubric item's criterion text,
    falling back to a 60s ± 2s window if the item doesn't state a specific target.

    Example criteria we should match:
      "exactly 60 seconds" / "exactly 60s"             → 58–62s (legacy default)
      "60.0 s ± 0.5 s (59.5–60.5 s)"                   → 59.5–60.5s
      "75.0 s ± 0.5 s (74.5–75.5 s inclusive)"         → 74.5–75.5s
      "Trailer runtime is 75 seconds"                  → 73–77s (broad ±2)
      "ffprobe format duration is between 59.9 and 60.1 seconds." → 59.9–60.1s
    """
    if item is None:
        return 58.0 <= dur <= 62.0, f"{dur:.2f}s"
    text = ((item.get("criterion", "") or "") + " " +
            (item.get("check", "") or "")).lower()
    # 1a) Two-unit range: "between 206.0 seconds and 228.0 seconds" / "206 s to 228 s"
    #     (handles the case where the unit word appears after BOTH numbers, not just the second)
    rng = re.search(r"(\d+(?:\.\d+)?)\s*(?:s\b|sec\b|seconds?\b)\s*(?:[–-]|\s+and\s+|\s+to\s+)\s*(\d+(?:\.\d+)?)\s*(?:s\b|sec|seconds)", text)
    # 1b) Explicit range: "59.5–60.5 s" / "between 59.9 and 60.1" / "[59.9, 60.1] seconds"
    if not rng:
        rng = re.search(r"(\d+(?:\.\d+)?)\s*(?:[–-]|\s+and\s+|\s+to\s+)\s*(\d+(?:\.\d+)?)\s*(?:s\b|sec|seconds)", text)
    if not rng:
        # Bracketed-pair form "[59.9, 60.1]" with seconds keyword nearby
        m = re.search(r"\[\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\]\s*(?:s\b|sec|seconds)?", text)
        if m and ("s\b" in text or "sec" in text or "second" in text):
            rng = m
    if rng:
        lo, hi = float(rng.group(1)), float(rng.group(2))
        if 1 < lo < hi < 600:
            return lo <= dur <= hi, f"{dur:.2f}s (target {lo}-{hi}s)"
    # 2) "X s ± Y s" or "X seconds ± Y" format
    pm = re.search(r"(\d+(?:\.\d+)?)\s*(?:s\b|sec|seconds)\s*[±+\-]\s*(\d+(?:\.\d+)?)\s*(?:s\b|sec|seconds)?", text)
    if pm:
        target = float(pm.group(1)); tol = float(pm.group(2))
        return abs(dur - target) <= tol, f"{dur:.2f}s (target {target}±{tol}s)"
    # 3) Single-value: pick the LARGEST plausible duration mentioned in the
    #    criterion text. Using max guards against criteria that mention the
    #    tolerance first ("within 0.5s of the 75s") — a naive re.search would
    #    match "0.5s", fail the plausibility window, and fall through.
    #    Also accepts hyphenated forms like "78-second" / "60-sec".
    matches = re.findall(r"(\d+(?:\.\d+)?)[\s-]*(?:s\b|sec\b|seconds?\b)", text)
    plausible = [float(m) for m in matches if 5 < float(m) < 600]
    if plausible:
        target = max(plausible)
        tol = 2.0  # default ±2s when only a target is stated
        return abs(dur - target) <= tol, f"{dur:.2f}s (target {target}±{tol}s)"
    # Fall back to legacy 60s default
    return 58.0 <= dur <= 62.0, f"{dur:.2f}s"


def _check_resolution(vstream, item: dict | None = None):
    """Parse target resolution(s) from the rubric item's criterion text.
    Falls back to 1920×1080 (legacy narrative default).

    Storage dimensions must match target AND pixels must be square (SAR 1:1)
    so that display aspect ratio matches storage. Otherwise an agent can
    encode at e.g. 1080×1920 with SAR=16:9 to render as a 1:1 square but
    pass a naive width/height check.
    """
    w, h = vstream.get("width", 0), vstream.get("height", 0)
    sar = vstream.get("sample_aspect_ratio", "1:1") or "1:1"
    # SAR is "N:D" — square pixels are 1:1. Encoder rounding can produce SARs
    # like 10240:10239 (≈1.0001) which are visually identical to 1:1; only
    # flag as non-square when the ratio deviates >2% from 1.0 (catches real
    # cheats like 16:9 / 2:1 / 256:81 but tolerates encoder noise).
    try:
        if ":" in sar:
            n, d = sar.split(":")
            ratio = float(n) / float(d) if float(d) > 0 else 1.0
        else:
            ratio = 1.0
    except Exception:
        ratio = 1.0
    sar_square = sar in ("0:1", "") or abs(ratio - 1.0) < 0.02
    if item is None:
        return (w, h) == (1920, 1080) and sar_square, f"{w}x{h} sar={sar}"
    text = ((item.get("criterion", "") or "") + " " +
            (item.get("check", "") or ""))
    # Match "WxH" or "W×H" patterns
    targets = [(int(a), int(b)) for a, b in re.findall(r"(\d{3,4})\s*[x×]\s*(\d{3,4})", text)]
    # Also match wordy forms: "1080 wide by 1920 tall", "1080 wide × 1920 tall"
    for a, b in re.findall(r"(\d{3,4})\s*wide\s*(?:by|x|×|\*)?\s*(\d{3,4})\s*tall", text, re.I):
        targets.append((int(a), int(b)))
    if targets:
        for tw, th in targets:
            if (w, h) == (tw, th):
                if sar_square:
                    return True, f"{w}x{h} (matches target {tw}x{th})"
                return False, f"{w}x{h} matches target {tw}x{th} but SAR={sar} (non-square pixels — rendered AR differs)"
        return False, f"{w}x{h} (targets {targets})"
    # Aspect-ratio range check: e.g. "width-to-height ratio between 1.30 and 2.40"
    # or "landscape with aspect ratio in [1.30, 2.40]". Triggered by aspect-ratio
    # vocabulary in the criterion text.
    text_lc = text.lower()
    if "aspect ratio" in text_lc or "width-to-height" in text_lc or "width to height" in text_lc \
       or "landscape" in text_lc or "portrait" in text_lc:
        ar_rng = re.search(r"(\d+(?:\.\d+)?)\s*(?:[–-]|\s+and\s+|\s+to\s+)\s*(\d+(?:\.\d+)?)", text)
        if ar_rng and w > 0 and h > 0:
            lo, hi = float(ar_rng.group(1)), float(ar_rng.group(2))
            if 0.1 < lo < hi < 10:
                ar = w / h
                ok = lo <= ar <= hi
                if ok and not sar_square:
                    return False, f"{w}x{h} AR={ar:.2f} in [{lo},{hi}] but SAR={sar}"
                return ok, f"{w}x{h} AR={ar:.2f} (target [{lo},{hi}])"
        # Landscape-only with no explicit range: w > h is the test
        if "landscape" in text_lc and w > 0 and h > 0:
            return w > h, f"{w}x{h} AR={w/h:.2f} (landscape={w>h})"
        if "portrait" in text_lc and w > 0 and h > 0:
            return h > w, f"{w}x{h} AR={w/h:.2f} (portrait={h>w})"
    return (w, h) == (1920, 1080) and sar_square, f"{w}x{h} sar={sar}"


def _check_video_codec(vstream, item: dict | None = None):
    """Parse target codec(s) from the rubric criterion. Falls back to h264."""
    c = vstream.get("codec_name", "")
    if item is None:
        return c == "h264", c
    text = ((item.get("criterion", "") or "") + " " +
            (item.get("check", "") or "")).lower()
    candidates = []
    for kw in ("h.264", "h264", "h.265", "h265", "hevc", "av1", "vp9"):
        if kw in text:
            candidates.append(kw.replace(".", ""))
    if not candidates:
        return c == "h264", c
    # Normalize aliases
    norm = {"h264":"h264", "h265":"hevc", "hevc":"hevc", "av1":"av1", "vp9":"vp9"}
    candidates = list({norm.get(k, k) for k in candidates})
    return c in candidates, f"{c} (targets {candidates})"


def _check_audio_codec(astream, item: dict | None = None):
    """Parse target audio codec(s) from the rubric criterion. Falls back to aac."""
    c = astream.get("codec_name", "") if astream else ""
    if not c:
        return False, "no audio"
    if item is None:
        return c == "aac", c
    text = ((item.get("criterion", "") or "") + " " +
            (item.get("check", "") or "")).lower()
    candidates = []
    for kw in ("aac", "mp3", "opus", "vorbis", "flac"):
        if kw in text:
            candidates.append(kw)
    if not candidates:
        return c == "aac", c
    return c in candidates, f"{c} (targets {candidates})"


def _check_fps(vstream, item: dict | None = None):
    """Parse target fps from the rubric item's criterion text, with 25fps default
    if the item doesn't state a specific target.

    Example criteria we should match:
      "Frame rate is 25 fps"                     → target 25
      "Frame rate is 24 fps within tolerance (23.9–24.1)" → target 24, tol 0.2
      "at 23.976 fps"                             → target 23.976
    """
    fps_str = vstream.get("r_frame_rate", "0/1")
    try:
        num, den = map(int, fps_str.split("/"))
        fps = num / den
    except Exception:
        fps = 0.0
    target = 25.0
    tol = 0.1
    if item is not None:
        text = ((item.get("criterion", "") or "") + " " +
                (item.get("check", "") or "")).lower()
        # Prefer a tolerance range if explicitly stated:
        #   "23.9–24.1 fps" / "23.9-24.1 fps" / "between 23.5 and 30.5 fps"
        rng = re.search(r"(\d+(?:\.\d+)?)\s*(?:[–-]|\s+and\s+|\s+to\s+)\s*(\d+(?:\.\d+)?)\s*fps", text)
        if rng:
            lo, hi = float(rng.group(1)), float(rng.group(2))
            if 5 < lo < 240 and 5 < hi < 240:
                return lo <= fps <= hi, f"{fps:.3f}fps (target {lo}-{hi})"
        # Otherwise: collect ALL fps targets from criterion text. Two patterns:
        #   (a) per-number "<X> fps" mentions: "24 fps or 25 fps"
        #   (b) shared-suffix list inside braces/brackets/parens with ≥2
        #       plausible values (5–240): "{23.976, 24, 25}" or
        #       "(23.976 / 24 / 25 / 29.97 / 30 / 50 / 59.94 / 60 fps)".
        # Both sets are merged so a criterion that has BOTH (e.g., "60 fps"
        # at the end of a parenthetical list of standard rates) doesn't
        # silently drop the earlier values.
        targets = [float(m) for m in re.findall(r"(\d+(?:\.\d+)?)\s*fps", text)]
        if "fps" in text or "frame rate" in text or "framerate" in text:
            for m in re.finditer(r"[{\[(]([^{}\[\]()]+)[}\])]", text):
                nums = re.findall(r"\d+(?:\.\d+)?", m.group(1))
                vals = [float(n) for n in nums if 5 < float(n) < 240]
                if len(vals) >= 2:  # ≥2 to avoid matching "(0.5)" tolerance parens
                    targets.extend(vals)
        if targets:
            uniq = sorted(set(round(t, 3) for t in targets))
            # Use a slightly looser tolerance for explicit set-form lists,
            # since "23.976" and "29.97" are usually written without trailing
            # decimal precision in source files (24000/1001 = 23.976023...).
            for t in uniq:
                if abs(fps - t) < 0.5:
                    return True, f"{fps:.3f}fps (matches target {t})"
            return False, f"{fps:.3f}fps (targets {uniq})"
    return abs(fps - target) < tol, f"{fps:.3f}fps (target {target}±{tol})"


def _check_loudness(repurpose_path):
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", repurpose_path,
         "-af", "loudnorm=I=-14:LRA=7:tp=-2:print_format=json",
         "-f", "null", "-"], capture_output=True, text=True).stderr
    s, e = out.rfind("{"), out.rfind("}")
    if s == -1 or e == -1:
        return False, "loudnorm parse failed"
    try:
        j = json.loads(out[s:e+1])
        lufs = float(j.get("input_i", 0))
        return -16 <= lufs <= -12, f"{lufs:.2f} LUFS"
    except Exception as e:
        return False, str(e)


def _check_vo_present(segments):
    total = sum((s["end"] - s["start"]) for s in segments)
    return total >= 20.0, f"{total:.1f}s of VO across {len(segments)} segments"


def _check_vo_original(segments, source_path):
    from difflib import SequenceMatcher
    vo_text = " ".join(s["text"] for s in segments).strip().lower()
    try:
        src = whisper_segments(source_path)
        src_text = " ".join(s["text"] for s in src).strip().lower()
    except Exception:
        src_text = ""
    if not vo_text:
        return False, "no VO text"
    sim = SequenceMatcher(None, vo_text, src_text).ratio() if src_text else 0
    return sim < 0.6, f"VO-source similarity {sim:.2f}"


def _check_titlecard(repurpose_path, title_keywords):
    try:
        ocr = ocr_last_5s(repurpose_path).lower()
    except Exception:
        ocr = ""
    has = any(kw.lower() in ocr for kw in title_keywords)
    return has, f"OCR final 5s: {ocr[:120].strip() or '(no text)'}"


def _check_reorder_hook(repurpose_path, source_path, final_third_start):
    try:
        return distinct_source_bin_hit_first_15s_generic(
            repurpose_path, source_path, final_third_start)
    except Exception as e:
        return False, f"error: {e}"


def distinct_source_bin_hit_first_15s_generic(repurpose, source, start_t):
    import imagehash
    src_dur = float(probe(source)["format"]["duration"])
    src_hashes = []
    end_t = min(src_dur, start_t + (src_dur - start_t) * 0.9)
    for t in np.linspace(start_t, end_t, 20):
        with tempfile.TemporaryDirectory() as td:
            fp = f"{td}/f.jpg"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
                            "-ss", f"{t:.3f}", "-i", source, "-vframes", "1",
                            "-vf", "scale=256:-1", fp], check=False)
            if os.path.exists(fp):
                src_hashes.append((t, imagehash.phash(Image.open(fp))))
    for t in np.linspace(0.5, 14.5, 15):
        f = extract_frame_at(repurpose, float(t), max_w=256)
        if f is None:
            continue
        h = imagehash.phash(f)
        for src_t, sh in src_hashes:
            if (h - sh) <= 14:
                return True, f"repurpose t={t:.1f}s matches source t={src_t:.1f}s"
    return False, f"no source ≥{start_t:.0f}s match found in repurpose first 15s"


def infer_format_check(item: dict) -> str:
    """Map a format rubric item to one of the programmatic checks by
    inspecting its ID and criterion text. Works for v8 (F-01, P0.*),
    v10 (F-01..F-10), and v11 (F-DUR, F-RES, F-CONTAINER, etc.) naming.

    Dispatch is **ID-prefix first** (specific tags like AUDIO-PRESENT,
    FPS, RES win immediately) and only falls back to text heuristics
    when the ID is generic (F-01, F-02, ...). Earlier versions of this
    function used loose substring matches like `"58" in blob` or
    `"59.9" in blob` which mis-routed any criterion mentioning 5.8 /
    0.58 / 59.94 to the duration check.
    """
    iid = (item.get("id") or "").upper()
    crit = (item.get("criterion") or item.get("desc") or "").lower()
    check_hint = (item.get("check") or "").lower()
    blob = f"{iid} | {crit} | {check_hint}"

    # 1) Specific ID prefixes — these are unambiguous
    if "AUDIO-PRESENT" in iid or "AUDIO_PRESENT" in iid: return "audio_present"
    if any(t in iid for t in ("AUD-NONSILENT", "AUDIO-NONSILENT", "NONSILENT", "NON-SILENT")): return "audio_nonsilent"
    if any(t in blob for t in ("aud-nonsilent", "audio-nonsilent", "non-silent", "non silent", "nonsilent")) or \
       ("audio is non-silent" in blob) or ("rms" in blob and "dbfs" in blob):
        return "audio_nonsilent"
    if "VO-WORDCOUNT" in iid or "VO_WORDCOUNT" in iid:   return "vo_wordcount"
    if "VO-PRESENT"   in iid or "VO_PRESENT"   in iid:   return "vo_present"
    if "VO-ORIGINAL"  in iid or "VO_ORIGINAL"  in iid:   return "vo_original"
    if "TITLE-SPAN"   in iid or "TITLE_SPAN"   in iid:   return "titlespan"
    if "FRAMERATE"    in iid or "FPS"          in iid:   return "fps"
    if "RES"          in iid or "VERTICAL"     in iid or "HORIZONTAL" in iid \
        or "LANDSCAPE" in iid or "PORTRAIT"    in iid or "ASPECT"     in iid: return "resolution"
    if "VIDEO-CODEC"  in iid or "VIDEO_CODEC"  in iid:   return "video_codec"
    if "AUDIO-CODEC"  in iid or "AUDIO_CODEC"  in iid:   return "audio_codec"
    if "CONTAINER"    in iid:                            return "container"
    if "LUFS"         in iid:                            return "loudness"
    if "CONTENT-DENSITY" in iid or "CONTENT_DENSITY" in iid: return "content_density"
    if "DUR"          in iid or "RUNTIME"      in iid:   return "duration"
    if "TITLE"        in iid:                            return "titlecard"
    if "CUT"          in iid:                            return "cut_count"
    if "REORDER"      in iid or "HOOK" in iid:           return "reorder_hook"
    if "BLACK" in iid or "BLANK" in iid:                 return "black_frames"

    # 2) Voice / VO text heuristics (ID didn't tell us)
    if ("voice-over" in blob and "present" in blob) or ("narrator" in blob and "audible" in blob):
        return "vo_present"
    if "lifted" in blob or "similarity" in blob:
        return "vo_original"
    if "wordcount" in blob or "word count" in blob:
        return "vo_wordcount"

    # 3) Format-mechanic text heuristics — order matters (most specific first)
    if "ffprobe format duration" in blob or "format=duration" in blob or "duration is between" in blob or "format duration" in blob:
        return "duration"
    if "frame rate" in blob or "framerate" in blob or "r_frame_rate" in blob or re.search(r"\d+(?:\.\d+)?\s*fps", blob):
        return "fps"
    if "resolution" in blob or re.search(r"\d{3,4}\s*[x×]\s*\d{3,4}", blob) or "wide by" in blob or "wide × " in blob or "wide x " in blob:
        return "resolution"
    if ("h.264" in blob and "codec" in blob) or ("h264" in blob and "codec" in blob):
        return "video_codec"
    if ("aac" in blob and "codec" in blob):
        return "audio_codec"
    if "container" in blob and "mp4" in blob:
        return "container"
    if "lufs" in blob or "loudness" in blob:
        return "loudness"
    if "audio" in blob and "stream" in blob:
        return "audio_present"

    # 4) Generic title / content-density / cut text patterns
    if "title card occupies" in blob or "title-card-span" in blob or ("title" in blob and "no more than" in blob):
        return "titlespan"
    if "titlecard" in blob or "title card" in blob:
        return "titlecard"
    if "source-derived footage" in blob or "content density" in blob:
        return "content_density"
    if "black frame" in blob or "black frames" in blob or "blank frame" in blob or "blank frames" in blob or "blackdetect" in blob:
        return "black_frames"
    if "scene cut" in blob or "shot cut" in blob or "scenedetect" in blob:
        return "cut_count"
    if "final third" in blob or "last third" in blob or "reorder" in blob:
        return "reorder_hook"
    return ""


def _check_container(repurpose_path: str):
    """MP4 decodes cleanly via ffprobe."""
    try:
        p = probe(repurpose_path)
        if not p.get("format") or not p.get("streams"):
            return False, "file does not decode"
        fmt = p["format"].get("format_name", "")
        return "mp4" in fmt.lower() or "mov" in fmt.lower(), f"format={fmt}"
    except Exception as e:
        return False, f"error: {e}"


def _check_audio_present(astream):
    return bool(astream), "audio stream present" if astream else "no audio stream"


def _check_audio_nonsilent(repurpose_path: str, item: dict | None = None):
    """librosa RMS check that audio body is not silent.
    Default: mean RMS over the body (5–55 s clipped to runtime) > −50 dBFS.
    """
    try:
        y, sr = librosa.load(repurpose_path, sr=16000, mono=True)
    except Exception as e:
        return False, f"audio load failed: {e}"
    if len(y) < sr:
        return False, "audio too short"
    dur = len(y) / sr
    a = int(min(5, dur * 0.1) * sr)
    b = int(min(55, dur - 5) * sr) if dur > 10 else len(y)
    body = y[a:b] if b > a else y
    if len(body) < sr // 2:
        body = y
    import numpy as np
    rms = float(np.sqrt(np.mean(body.astype("float64") ** 2)) + 1e-12)
    db = 20.0 * np.log10(rms)
    return db > -50.0, f"mean RMS over body = {db:.1f} dBFS (target > -50)"


def _check_vo_wordcount(segments):
    total = sum(len(s["text"].split()) for s in segments)
    return 140 <= total <= 170, f"{total} words"


def _check_titlespan(repurpose_path, title_keywords):
    """Approximate title-card-span: OCR frames at 2fps across full repurpose; count consecutive
    frames where OCR contains a title keyword as the dominant text. Span ≤ 3s passes."""
    try:
        import pytesseract
    except ImportError:
        return False, "pytesseract unavailable"
    dur = float(probe(repurpose_path)["format"]["duration"])
    if dur <= 0:
        return False, "bad duration"
    hit_times = []
    with tempfile.TemporaryDirectory() as td:
        for t in np.arange(0.0, dur, 0.5):  # 2 fps
            fp = f"{td}/f_{t:.2f}.png"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
                            "-ss", f"{t:.3f}", "-i", repurpose_path, "-vframes", "1", fp],
                           check=False)
            if os.path.exists(fp):
                txt = pytesseract.image_to_string(Image.open(fp)).lower()
                if any(kw.lower() in txt for kw in title_keywords):
                    hit_times.append(t)
    if not hit_times:
        return False, "title never OCR'd"
    span = hit_times[-1] - hit_times[0]
    # Find longest consecutive run
    max_run = 0
    cur_run = 1
    for i in range(1, len(hit_times)):
        if hit_times[i] - hit_times[i-1] <= 0.8:
            cur_run += 1
            max_run = max(max_run, cur_run)
        else:
            cur_run = 1
    max_run_s = max_run * 0.5  # frames are 0.5s apart
    return max_run_s <= 3.5, f"title span={max_run_s:.1f}s over {len(hit_times)} frames"


def _check_content_density(repurpose_path, title_keywords):
    """At least (duration - 3)s of non-title-card source content. OCR at 1fps: count
    frames that do NOT contain the title. If non-title count >= duration - 3, pass."""
    try:
        import pytesseract
    except ImportError:
        return False, "pytesseract unavailable"
    dur = float(probe(repurpose_path)["format"]["duration"])
    if dur <= 0:
        return False, "bad duration"
    non_title = 0
    total = 0
    with tempfile.TemporaryDirectory() as td:
        for t in np.arange(0.5, dur, 1.0):
            fp = f"{td}/f_{t:.2f}.png"
            subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
                            "-ss", f"{t:.3f}", "-i", repurpose_path, "-vframes", "1", fp],
                           check=False)
            if os.path.exists(fp):
                total += 1
                txt = pytesseract.image_to_string(Image.open(fp)).lower()
                if not any(kw.lower() in txt for kw in title_keywords):
                    non_title += 1
    need = max(0, int(dur) - 3)
    return non_title >= need, f"{non_title}/{total} non-title frames; need ≥ {need}"


def _check_black_frames(repurpose_path: str, item: dict | None = None):
    """Detect unintended black/blank frame runs with ffmpeg blackdetect."""
    text = ""
    if item:
        text = ((item.get("criterion", "") or "") + " " + (item.get("check", "") or "")).lower()
    threshold = 0.5
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:s|sec|seconds?)\s+or\s+longer", text)
    if m:
        threshold = float(m.group(1))
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", repurpose_path,
         "-vf", f"blackdetect=d={threshold}:pic_th=0.98:pix_th=0.10",
         "-an", "-f", "null", "-"],
        capture_output=True, text=True)
    hits = [line for line in r.stderr.splitlines() if "black_start:" in line]
    return not hits, "no blackdetect hits" if not hits else hits[0][:180]


def score_pillar_0(repurpose_path: str, source_path: str,
                    title_keywords=None, final_third_start=172.0) -> dict:
    """Deterministic checks for Pillar 0 format items.

    Handles v10 (F-01..F-10) and v8 (P0.*) item IDs by probing IDs and
    running the matching programmatic check.
    """
    if title_keywords is None:
        title_keywords = ["The Present", "Present"]
    items_p0 = [it for it in RUBRIC["items"] if it["pillar"] == 0]
    result = {"items": {}, "pillar_total": 0, "pillar_max": 0}
    for it in items_p0:
        # pillar_max = sum of POSITIVE weights only (the achievable ceiling).
        # Negative-weight violation items do not contribute to the ceiling;
        # they only ever deduct from pillar_total when they fire.
        if it["weight"] > 0:
            result["pillar_max"] += it["weight"]

    p = probe(repurpose_path)
    vstream = next((s for s in p.get("streams", []) if s["codec_type"] == "video"), {})
    astream = next((s for s in p.get("streams", []) if s["codec_type"] == "audio"), {})
    dur = float(p.get("format", {}).get("duration", 0))
    try:
        segments = whisper_segments(repurpose_path)
    except Exception:
        segments = []

    for it in items_p0:
        iid = it["id"]
        kind = infer_format_check(it)
        if kind == "duration":
            passed, note = _check_duration(dur, item=it)
        elif kind == "resolution":
            passed, note = _check_resolution(vstream, item=it)
        elif kind == "fps":
            passed, note = _check_fps(vstream, it)
        elif kind == "video_codec":
            passed, note = _check_video_codec(vstream, item=it)
        elif kind == "audio_codec":
            passed, note = _check_audio_codec(astream, item=it)
        elif kind == "container":
            passed, note = _check_container(repurpose_path)
        elif kind == "audio_present":
            passed, note = _check_audio_present(astream)
        elif kind == "audio_nonsilent":
            passed, note = _check_audio_nonsilent(repurpose_path, item=it)
        elif kind == "loudness":
            passed, note = _check_loudness(repurpose_path)
        elif kind == "vo_present":
            passed, note = _check_vo_present(segments)
        elif kind == "vo_wordcount":
            passed, note = _check_vo_wordcount(segments)
        elif kind == "vo_original":
            passed, note = _check_vo_original(segments, source_path)
        elif kind == "titlecard":
            passed, note = _check_titlecard(repurpose_path, title_keywords)
        elif kind == "titlespan":
            passed, note = _check_titlespan(repurpose_path, title_keywords)
        elif kind == "content_density":
            passed, note = _check_content_density(repurpose_path, title_keywords)
        elif kind == "black_frames":
            passed, note = _check_black_frames(repurpose_path, item=it)
        elif kind == "cut_count":
            try:
                cuts = scene_cut_times(repurpose_path)
            except Exception:
                cuts = []
            passed, note = len(cuts) >= 8, f"{len(cuts)} cuts"
        elif kind == "reorder_hook":
            passed, note = _check_reorder_hook(repurpose_path, source_path, final_third_start)
        else:
            # Could not infer a check — escalate to VLM judge rather than silent fail.
            passed, note = False, f"no deterministic check wired for {iid} ({it.get('criterion','')[:80]})"

        sc, mx = _score_max(it, bool(passed))
        result["items"][iid] = {
            "pass": bool(passed),
            "score": sc,
            "max": mx,
            "desc": it["criterion"],
            "why": note,
        }
        result["pillar_total"] += sc

    result["segments"] = [{"start": round(s["start"], 2), "end": round(s["end"], 2),
                           "text": s["text"].strip()} for s in segments]
    return result


# ---------- Pillar 1/2/3 VLM judging ----------


def build_pillar_1_evidence(repurpose_path: str, source_path: str,
                            golden_path: str | None = None) -> list[dict]:
    """Visual pillar evidence: repurpose frames at 1 fps.
    Optionally appends golden human-reference repurpose frames at 1 fps when golden_path is provided.

    1 fps on the repurposed cut gives 60 frames for a 60s repurposed cut — dense enough that rubric
    items referencing specific visible content cannot miss by sampling bad luck.
    Golden frames (when present) let golden-aware rubric items reference what the
    human reference cut actually showed (e.g., N-GOLDEN-FIDELITY).
    Source frames are NOT included — the judge grades the repurposed cut against the rubric,
    not against the source. Rubric items must be evaluable from the repurposed cut alone.
    """
    repurpose_dur = float(probe(repurpose_path)["format"]["duration"])
    # Cap repurpose frames at 250 to keep total image count under the Anthropic
    # 600-image-per-request limit (repurpose 250 + golden 250 < 600). For longer
    # repurposed cuts, fps drops below 1 — still adequate for rubric items.
    n_repurpose = min(250, max(30, int(repurpose_dur)))
    blocks: list[dict] = [{
        "type": "text",
        "text": f"# Task context\n\n{TASK_CONTEXT}\n\n# Repurpose frames ({n_repurpose} samples across the {repurpose_dur:.1f}s runtime)"
    }]
    for t in np.linspace(0.5, max(repurpose_dur - 0.5, 0.5), n_repurpose):
        f = extract_frame_at(repurpose_path, float(t), max_w=512)
        if f is None: continue
        blocks.append(image_block(f))
        blocks.append({"type": "text", "text": f"repurpose t={t:.1f}s"})

    if REPURPOSE_ONLY:
        return blocks

    if golden_path and not REPURPOSE_ONLY:
        golden_dur = float(probe(golden_path)["format"]["duration"])
        # Cap golden frames at 250 to keep total image count under the Anthropic
        # 600-image-per-request limit. Golden is typically short (60-180s) so this
        # rarely bites, but 4-min explainer goldens (Memento/Apollo) would otherwise
        # hit 240 + repurpose 240 = 480 — within budget at the 250 cap.
        n_golden = min(250, max(30, int(golden_dur)))
        blocks.append({"type": "text",
                       "text": (f"\n# Golden human reference repurpose frames "
                                f"({n_golden} samples at ~1 fps across the {golden_dur:.1f}s golden runtime). "
                                f"This is the human-edited reference cut. "
                                f"Use it only to check golden-aware rubric items (e.g. N-GOLDEN-FIDELITY) "
                                f"that ask whether the agent's repurposed cut honored an editorial choice the golden made. "
                                f"DO NOT score the repurposed cut on similarity to the golden generally.")})
        for t in np.linspace(0.5, max(golden_dur - 0.5, 0.5), n_golden):
            f = extract_frame_at(golden_path, float(t), max_w=512)
            if f is None: continue
            blocks.append(image_block(f))
            blocks.append({"type": "text", "text": f"golden t={t:.1f}s"})
    return blocks


def build_pillar_2_evidence(repurpose_path: str, segments: list[dict],
                            golden_path: str | None = None,
                            golden_segments: list[dict] | None = None) -> list[dict]:
    """Narrative pillar: AV-aligned tuples at 1 fps + full transcript + cut timestamps.
    Optionally appends a golden human-reference repurpose block when golden_path is provided.

    1 fps per-second tuples pair each second's frame with the VO text spoken at
    that second. For a 60s repurposed cut this is 60 tuples — dense enough that narrative
    items about specific moments (reveal placement, pacing across the runtime,
    VO-subject-on-screen alignment) don't miss by sampling.

    Golden frames (when present) are appended as a clearly-separate block — NOT
    interleaved with rollout tuples — so the judge can answer golden-aware items
    (N-GOLDEN-FIDELITY) by comparing the rollout block against the golden block
    without losing track of which timestamps belong to whom.
    """
    repurpose_dur = float(probe(repurpose_path)["format"]["duration"])
    cut_times = scene_cut_times(repurpose_path)
    shot_lengths = np.diff([0.0] + cut_times + [repurpose_dur])
    shot_stddev = float(np.std(shot_lengths)) if len(shot_lengths) > 1 else 0.0
    transcript_lines = "\n".join(f"[{s['start']:.1f}-{s['end']:.1f}s] {s['text'].strip()}"
                                 for s in segments)
    # Cap at 250 to keep total under the Anthropic 600-image limit
    # (repurpose 250 + golden 250 < 600).
    n_tuples = min(250, max(30, int(repurpose_dur)))
    blocks: list[dict] = [{
        "type": "text",
        "text": (f"# Task context\n\n{TASK_CONTEXT}\n\n"
                 f"# Scene cut timestamps (seconds)\n{[round(c, 2) for c in cut_times]}\n"
                 f"# Shot-length standard deviation: {shot_stddev:.2f}s\n\n"
                 f"# Full VO transcript with timestamps\n{transcript_lines}\n\n"
                 f"# Audio-visual aligned tuples ({n_tuples} samples at ~1 fps — "
                 f"frame + the VO text spoken at that moment)")
    }]
    for t in np.linspace(0.5, max(repurpose_dur - 0.5, 0.5), n_tuples):
        f = extract_frame_at(repurpose_path, float(t), max_w=400)
        if f is None: continue
        vo = vo_at_second(segments, float(t))
        blocks.append(image_block(f, max_w=400))
        blocks.append({"type": "text", "text": f"t={t:.1f}s | VO: {vo or '(silence)'}"})

    if golden_path and not REPURPOSE_ONLY:
        golden_dur = float(probe(golden_path)["format"]["duration"])
        n_golden = min(250, max(30, int(golden_dur)))
        golden_transcript_lines = ""
        if golden_segments:
            golden_transcript_lines = "\n".join(
                f"[{s['start']:.1f}-{s['end']:.1f}s] {s['text'].strip()}" for s in golden_segments)
        blocks.append({"type": "text",
                       "text": (f"\n# === Golden human reference repurpose ===\n"
                                f"# Golden duration: {golden_dur:.1f}s ; {n_golden} frames at 1 fps below.\n"
                                + (f"# Golden VO transcript:\n{golden_transcript_lines}\n"
                                   if golden_transcript_lines else "# Golden VO transcript: (not available)\n")
                                + f"# These frames are the human-edited reference cut, NOT the rollout. "
                                f"Use this block ONLY to score golden-aware rubric items "
                                f"(e.g. N-GOLDEN-FIDELITY, where the criterion explicitly names a golden choice). "
                                f"For all other items, score the rollout block above on its own merits.")})
        for t in np.linspace(0.5, max(golden_dur - 0.5, 0.5), n_golden):
            f = extract_frame_at(golden_path, float(t), max_w=400)
            if f is None: continue
            vo = vo_at_second(golden_segments, float(t)) if golden_segments else None
            blocks.append(image_block(f, max_w=400))
            blocks.append({"type": "text",
                           "text": f"golden t={t:.1f}s | VO: {vo or '(no transcript)'}"})
    return blocks


def audio_features(repurpose: str, segments: list[dict]) -> dict:
    y, sr = librosa.load(repurpose, sr=16000, mono=True)
    dur = len(y) / sr
    try:
        f0 = librosa.yin(y, fmin=75, fmax=400, sr=sr)
        f0 = f0[~np.isnan(f0) & (f0 > 50)]
        pitch_std = float(np.std(1200 * np.log2(f0 / f0.mean()))) if len(f0) > 10 else 0.0
    except Exception:
        pitch_std = 0.0
    win = sr
    rms = librosa.feature.rms(y=y, frame_length=win, hop_length=win)[0]
    rms_db = 20 * np.log10(np.maximum(rms, 1e-8))
    vo_mask = np.zeros(int(dur) + 1, dtype=bool)
    for s in segments:
        for t in range(int(s["start"]), int(s["end"]) + 1):
            if 0 <= t <= int(dur):
                vo_mask[t] = True
    gap = [rms_db[i] for i in range(min(len(rms_db), len(vo_mask))) if not vo_mask[i]]
    vo = [rms_db[i] for i in range(min(len(rms_db), len(vo_mask))) if vo_mask[i]]
    try:
        onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time").tolist()[:20]
    except Exception:
        onsets = []
    return {
        "duration_s": round(dur, 2),
        "pitch_stdev_cents": round(pitch_std, 1),
        "loudness_db_mean": round(float(np.mean(rms_db)), 2),
        "loudness_db_p10": round(float(np.percentile(rms_db, 10)), 2),
        "loudness_db_p90": round(float(np.percentile(rms_db, 90)), 2),
        "vo_loudness_db_mean": round(float(np.mean(vo)) if vo else -99.0, 2),
        "non_vo_gap_loudness_db_mean": round(float(np.mean(gap)) if gap else -99.0, 2),
        "onsets_head": [round(x, 2) for x in onsets],
        "vo_total_duration_s": round(sum((s["end"] - s["start"]) for s in segments), 2),
    }


def build_pillar_3_evidence(repurpose_path: str, segments: list[dict]) -> list[dict]:
    """Sound pillar: audio features + 8 AV tuples so judge can check VO-image sync."""
    feats = audio_features(repurpose_path, segments)
    transcript = "\n".join(f"[{s['start']:.1f}-{s['end']:.1f}s] {s['text'].strip()}"
                           for s in segments)
    blocks: list[dict] = [{
        "type": "text",
        "text": (f"# Task context\n\n{TASK_CONTEXT}\n\n"
                 f"# Programmatic audio features\n{json.dumps(feats, indent=2)}\n\n"
                 f"# Full VO transcript with timestamps\n{transcript}\n\n"
                 f"# Audio-visual aligned tuples (for VO-image alignment items)")
    }]
    repurpose_dur = feats["duration_s"]
    for t in np.linspace(0.5, repurpose_dur - 0.5, 8):
        f = extract_frame_at(repurpose_path, float(t), max_w=400)
        if f is None: continue
        vo = vo_at_second(segments, float(t))
        blocks.append(image_block(f, max_w=400))
        blocks.append({"type": "text", "text": f"t={t:.1f}s | VO: {vo or '(silence)'}"})
    return blocks


SYSTEM_PROMPT = """You are grading one rubric item against a submitted 60-second video repurpose.

# What "pass" means

"Pass" does not mean "the literal criterion is technically satisfied." It means the submitted output achieves the criterion at a level that a professional film editor would accept in a publishable deliverable of this type. The criterion describes what a GOOD output looks like — not the minimum floor for a checkbox.

# What "fail" means

Return pass=false when any of the following applies:
- The stated failure conditions hold.
- The output technically performs the named action but does it in a way that reads as surface-level, perfunctory, or box-checking — a reviewer grading craft would not be satisfied.
- The evidence is weak, partial, or could plausibly be read either way.
- You could easily point to a version of this specific output that does the item markedly better.

# Decision rule

When genuinely uncertain, fail. A professional rubric rewards craft execution, not compliance. Think of yourself as a senior editor doing a final-pass review — would you send this to the client as exemplifying this item, or would you ask for a revision?

# Output

Exactly one JSON object, no other text:
{"pass": true|false, "why": "<one sentence grounded in specific evidence from the video>"}"""


def mark_cache(blocks: list[dict]) -> list[dict]:
    """Mark the last evidence block as cache_control so subsequent calls hit the cache."""
    if blocks:
        last = blocks[-1]
        # Deep copy last block with cache marker
        last = dict(last)
        last["cache_control"] = {"type": "ephemeral"}
        blocks[-1] = last
    return blocks


def judge_item_gemini_audio(item: dict, repurpose_path: str) -> dict:
    """Grade one item using Gemini 3.1 Pro with AUDIO ONLY (not video).

    Extracting audio and sending it alone eliminates visual-prior
    hallucinations — e.g. Gemini models confidently assert a "crunch" sound
    when they see a bite action on video, even if no crunch is audible.
    Audio-only forces grounding in what's actually in the audio track.

    Uses a cache dir inside the repurposed cut's parent workspace so repeated items
    against the same repurpose reuse the uploaded audio file.
    """
    from google import genai
    from google.genai import types as gtypes
    import hashlib

    repurpose_p = Path(repurpose_path).resolve()
    cache_dir = repurpose_p.parent.parent.parent / "_agent_scratch" / "gemini_judge_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Extract audio as mp3 once per repurpose (cached on disk by content hash)
    h = hashlib.sha256()
    h.update(str(repurpose_p.stat().st_size).encode())
    with repurpose_p.open("rb") as fh:
        h.update(fh.read(256 * 1024))
    key = h.hexdigest()[:16]
    mp3_file = cache_dir / f"repurpose_{key}.mp3"
    cache_info = cache_dir / f"repurpose_{key}.json"

    if not mp3_file.exists():
        r = subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
             "-i", str(repurpose_p), "-vn", "-acodec", "libmp3lame", "-b:a", "96k",
             str(mp3_file)],
            capture_output=True)
        if r.returncode != 0:
            return {"pass": False, "score": 0, "max": max(0, item["weight"]),
                    "desc": item.get("criterion", item.get("desc", "")),
                    "why": f"(ffmpeg audio extraction failed: {r.stderr.decode()[:200]})",
                    "judge_used": "gemini-audio-error"}

    os.environ["GEMINI_API_KEY"] = GEMINI_AI_STUDIO_KEY
    client = genai.Client(
        api_key=GEMINI_AI_STUDIO_KEY,
        http_options=gtypes.HttpOptions(timeout=90000),
    )

    # Inline audio: re-send ~1MB per repurpose per rubric item — cheap, and
    # avoids the Files-API caching dance for short clips.
    audio_part = gtypes.Part.from_bytes(
        data=mp3_file.read_bytes(),
        mime_type="audio/mpeg",
    )

    criterion = item.get("criterion", item.get("desc", ""))
    check_hint = item.get("check", "")
    why_hint = item.get("why", "")

    # Pre-detect spoken language with whisper to give Gemini a grounded hint.
    # Gemini occasionally mis-classifies Korean/Cantonese speech as English; the
    # auto-detected language tag below prevents that failure mode.
    detected_lang = ""
    try:
        segs = whisper_segments(repurpose_path)
        detected_lang = segs[0].get("language", "") if segs else ""
    except Exception:
        detected_lang = ""
    lang_hint = ""
    if detected_lang:
        # Common Whisper codes → human names
        lang_name = {
            "en": "English", "ko": "Korean", "ja": "Japanese", "zh": "Chinese (Mandarin or Cantonese)",
            "yue": "Cantonese", "fr": "French", "es": "Spanish", "de": "German",
            "it": "Italian", "pt": "Portuguese", "ru": "Russian", "hi": "Hindi",
        }.get(detected_lang, detected_lang)
        lang_hint = (
            f"\n\n# Detected spoken-language hint (from Whisper auto-detect)\n"
            f"The repurposed cut's dominant spoken language was detected as: **{lang_name}** "
            f"(Whisper code: {detected_lang}). Use this as a prior — verify by listening — "
            f"and do NOT mis-classify non-English speech as English voice-over.\n"
        )

    system = (
        "You are an audio-only auditor. You are given ONLY the audio track of "
        "a 60-second video repurpose — no visuals. Judge the rubric item using "
        "ONLY what you can literally hear. Do NOT infer sounds from external "
        "context (e.g. do not assume a crunch exists because the repurposed cut's "
        "narration mentions biting). If you are not certain the audible "
        "evidence supports a pass, fail. CRITICAL: identify the spoken language "
        "of any voice you hear — do NOT default to assuming speech is English."
    )
    prompt = (
        f"{system}\n\n"
        f"# Rubric item\n**{item['id']}** ({item['weight']}pt): {criterion}{lang_hint}\n\n"
    )
    if why_hint:
        prompt += f"# Why this item exists\n{why_hint}\n\n"
    if check_hint:
        prompt += f"# How to judge\n{check_hint}\n\n"
    prompt += (
        "Listen to the full audio track. Return one JSON object — and describe "
        "what you literally hear BEFORE deciding the pass/fail:\n"
        "{\n"
        '  "what_i_literally_hear": "<2-4 sentences describing the actual audio at relevant moments>",\n'
        '  "pass": true|false,\n'
        '  "why": "<one sentence grounded in what_i_literally_hear>"\n'
        "}"
    )

    # Append strict format directive + truncation-tolerant parsing below.
    # Gemini 3 Flash does thinking tokens internally → needs generous max_output_tokens.
    strict_prompt = prompt + "\n\nFormat: return ONLY the JSON object on a single line — no code fence, no explanation, no preamble. Example: {\"pass\": true, \"why\": \"one short sentence\"}"

    last_text = ""
    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model=GEMINI_AUDIO_MODEL,
                contents=[audio_part, strict_prompt],
                config=gtypes.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=4096,
                    # Gemini 3 thinking models burn output budget on hidden
                    # reasoning by default; with budget=0 the JSON body
                    # actually fits inside max_output_tokens.
                    thinking_config=gtypes.ThinkingConfig(thinking_budget=0),
                ),
            )
            text = (resp.text or "").strip()
            last_text = text
            # Strip code fences
            text_clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
            # Try to parse a complete JSON object
            m = re.search(r"\{[^{}]*\}", text_clean, re.DOTALL)
            if m:
                try:
                    j = json.loads(m.group(0))
                    passed = bool(j.get("pass", False))
                    sc, mx = _score_max(item, passed)
                    return {
                        "pass": passed,
                        "score": sc,
                        "max": mx,
                        "desc": criterion,
                        "why": j.get("why", ""),
                        "judge_used": "gemini-audio",
                        "raw": text,
                    }
                except json.JSONDecodeError:
                    pass
            # Tolerant parse: look for truncated response `"pass": true/false`
            pass_match = re.search(r'"pass"\s*:\s*(true|false)', text_clean, re.IGNORECASE)
            if pass_match:
                passed = pass_match.group(1).lower() == "true"
                why_match = re.search(r'"why"\s*:\s*"([^"]*)', text_clean)
                why = why_match.group(1) if why_match else "(truncated)"
                sc, mx = _score_max(item, passed)
                return {
                    "pass": passed,
                    "score": sc,
                    "max": mx,
                    "desc": criterion,
                    "why": why,
                    "judge_used": "gemini-audio-truncated",
                    "raw": text,
                }
        except Exception as e:
            if attempt == 2:
                return {"pass": False, "score": 0, "max": max(0, item["weight"]),
                        "desc": criterion,
                        "why": f"(gemini-audio error: {e})",
                        "judge_used": "gemini-audio-error"}
            time.sleep(2 * (attempt + 1))
    return {"pass": False, "score": 0, "max": max(0, item["weight"]),
            "desc": criterion,
            "why": f"(gemini-audio unparseable; raw: {last_text[:200]})",
            "judge_used": "gemini-audio-error", "raw": last_text}


def judge_item_gemini_video(item: dict, repurpose_path: str) -> dict:
    """Gemini 3.1 Pro with native video+audio (full repurpose.mp4).

    Use for items that need BOTH what's on screen and what's audible — e.g.
    caption-sync checks where the judge reads the on-screen caption AND hears
    the speaker's words at that timestamp. Unlike judge_item_gemini_audio
    (audio-only, to avoid visual-prior hallucinations in sound judging), this
    route deliberately gives Gemini both channels.

    Uploads the repurpose.mp4 once per workspace and caches the File handle; all
    items using this route in the same scoring pass reuse the same upload.
    """
    from google import genai
    from google.genai import types as gtypes
    import hashlib

    repurpose_p = Path(repurpose_path).resolve()
    cache_dir = repurpose_p.parent.parent.parent / "_agent_scratch" / "gemini_judge_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    h = hashlib.sha256()
    h.update(str(repurpose_p.stat().st_size).encode())
    with repurpose_p.open("rb") as fh:
        h.update(fh.read(256 * 1024))
    key = h.hexdigest()[:16]
    cache_info = cache_dir / f"repurpose_video_{key}.json"

    os.environ["GEMINI_API_KEY"] = GEMINI_AI_STUDIO_KEY
    # Hard timeout on all Gemini HTTP calls so a stuck request can't hang the
    # whole scoring loop. 90s is plenty for a single generate_content on a
    # cached file; if it exceeds, it's a service hang we'd rather retry on.
    client = genai.Client(
        api_key=GEMINI_AI_STUDIO_KEY,
        http_options=gtypes.HttpOptions(timeout=90000))

    uploaded = None
    if cache_info.exists():
        try:
            info = json.loads(cache_info.read_text())
            uploaded = client.files.get(name=info["name"])
            if uploaded.state.name != "ACTIVE":
                uploaded = None
        except Exception:
            uploaded = None
    if uploaded is None:
        uploaded = client.files.upload(file=str(repurpose_p))
        while uploaded.state.name == "PROCESSING":
            time.sleep(2)
            uploaded = client.files.get(name=uploaded.name)
        if uploaded.state.name == "ACTIVE":
            cache_info.write_text(json.dumps({"name": uploaded.name, "uri": uploaded.uri}))
        else:
            return {"pass": False, "score": 0, "max": max(0, item["weight"]),
                    "desc": item.get("criterion", item.get("desc", "")),
                    "why": f"(gemini file upload state={uploaded.state.name})",
                    "judge_used": "gemini-video-error"}

    criterion = item.get("criterion", item.get("desc", ""))
    check_hint = item.get("check", "")
    why_hint = item.get("why", "")
    is_violation = item["weight"] < 0
    system = (
        "You are an audio-visual auditor. You are given the FULL repurpose video "
        "— both the picture and the synchronized audio. Judge the rubric item "
        "using what you actually see on screen AND what you actually hear. For "
        "caption-sync items specifically: read the caption text visible on "
        "screen at a timestamp and compare it to the audio content at the same "
        "timestamp. Do NOT guess. If the evidence is ambiguous, fail (for "
        "positive items) or decline to fire (for violation items)."
    )
    prompt = (
        f"{system}\n\n"
        f"# Rubric item\n**{item['id']}** ({item['weight']}pt): {criterion}\n\n"
    )
    if why_hint:
        prompt += f"# Why this item exists\n{why_hint}\n\n"
    if check_hint:
        prompt += f"# How to judge\n{check_hint}\n\n"
    if is_violation:
        prompt += (
            "This is a VIOLATION item (negative weight). Return pass=true if "
            "the violation is detected (the item fires and deducts). Return "
            "pass=false if the violation is NOT present (no effect).\n\n"
        )
    prompt += (
        "Inspect the video (picture + audio). Return one JSON object — "
        "describe what you literally see AND hear at the relevant moments "
        "BEFORE deciding the pass/fail:\n"
        "{\n"
        '  "what_i_observe": "<2-4 sentences citing both the on-screen content and the audio at specific timestamps>",\n'
        '  "pass": true|false,\n'
        '  "why": "<one sentence grounded in what_i_observe>"\n'
        "}\n\n"
        "Format: return ONLY the JSON object — no code fence, no preamble."
    )

    last_text = ""
    for attempt in range(3):
        try:
            resp = client.models.generate_content(
                model=GEMINI_AUDIO_MODEL,  # same Gemini 3.1 Pro model — it's multimodal
                contents=[uploaded, prompt],
                config=gtypes.GenerateContentConfig(
                    temperature=0.0, max_output_tokens=4096),
            )
            text = (resp.text or "").strip()
            last_text = text
            text_clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE)
            m = re.search(r"\{.*\}", text_clean, re.DOTALL)
            if m:
                try:
                    j = json.loads(m.group(0))
                    passed = bool(j.get("pass", False))
                    sc, mx = _score_max(item, passed)
                    return {
                        "pass": passed,
                        "score": sc,
                        "max": mx,
                        "desc": criterion,
                        "why": j.get("why", ""),
                        "observe": j.get("what_i_observe", ""),
                        "judge_used": "gemini-video",
                        "raw": text,
                    }
                except json.JSONDecodeError:
                    pass
            pass_match = re.search(r'"pass"\s*:\s*(true|false)', text_clean, re.IGNORECASE)
            if pass_match:
                passed = pass_match.group(1).lower() == "true"
                sc, mx = _score_max(item, passed)
                return {
                    "pass": passed,
                    "score": sc,
                    "max": mx,
                    "desc": criterion,
                    "why": "(parse recovered)",
                    "judge_used": "gemini-video-truncated",
                    "raw": text,
                }
        except Exception as e:
            if attempt == 2:
                return {"pass": False, "score": 0, "max": max(0, item["weight"]),
                        "desc": criterion,
                        "why": f"(gemini-video error: {e})",
                        "judge_used": "gemini-video-error"}
            time.sleep(2 * (attempt + 1))
    return {"pass": False, "score": 0, "max": max(0, item["weight"]),
            "desc": criterion,
            "why": f"(gemini-video unparseable; raw: {last_text[:200]})",
            "judge_used": "gemini-video-error", "raw": last_text}


def judge_item(client, evidence: list[dict], item: dict) -> dict:
    # narrative_essential items have negative weight but their criterion describes
    # the GOOD state (e.g. "the convulsion appears"). They use the default
    # positive-criterion framing — the score helper handles the inversion.
    is_violation = item["weight"] < 0 and not item.get("narrative_essential")
    if is_violation:
        violation_framing = (
            "\n\n# SPECIAL: THIS IS A VIOLATION ITEM\n"
            f"The weight is NEGATIVE ({item['weight']}pt). The criterion above "
            "describes a VIOLATION state — a specific failure mode that, if "
            "detected in the reel, should DEDUCT points. This item does NOT "
            "describe what a good reel looks like; it describes a specific "
            "thing that would be wrong with the reel.\n\n"
            "INSTRUCTION:\n"
            "- Return `pass: true` IF AND ONLY IF the violation described by "
            "the criterion is ACTUALLY PRESENT in the reel (you observe the "
            "bad state). Pass=true causes the negative weight to be applied "
            "(deduction).\n"
            "- Return `pass: false` if the violation is NOT present (the reel "
            "avoids the described failure mode). Pass=false causes no effect.\n\n"
            "Judge ONLY on whether the described violation state actually "
            "occurs in the reel. Do NOT re-interpret the criterion as a "
            "positive goal.\n"
        )
    else:
        violation_framing = ""
    user_content = list(evidence) + [{
        "type": "text",
        "text": f"\n# Grade this rubric item\n\n**{item['id']}** ({item['weight']}pt): {item['criterion']}{violation_framing}\n\nReturn one JSON object."
    }]
    for attempt in range(3):
        try:
            resp = client.messages.create(
                model=JUDGE_MODEL, max_tokens=300, system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            text = resp.content[0].text
            m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
            if m:
                j = json.loads(m.group(0))
                passed = bool(j.get("pass", False))
                sc, mx = _score_max(item, passed)
                return {"pass": passed,
                        "score": sc,
                        "max": mx,
                        "desc": item["criterion"],
                        "why": j.get("why", ""),
                        "raw": text}
        except anthropic.APIError as e:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
        except Exception as e:
            if attempt == 2:
                return {"pass": False, "score": 0, "max": max(0, item["weight"]),
                        "desc": item["criterion"],
                        "why": f"(parse error: {e})", "raw": text if 'text' in dir() else ''}
            time.sleep(1)
    return {"pass": False, "score": 0, "max": max(0, item["weight"]),
            "desc": item["criterion"], "why": "(retry exhausted)"}


def judge_pillar(client, pillar: int, evidence: list[dict],
                  items: list[dict], repurpose_path: str = "",
                  max_workers: int = 6) -> dict:
    """Route each item based on its `judge:` annotation. Items within a
    pillar run CONCURRENTLY (ThreadPoolExecutor) since each is an
    independent I/O-bound API call to Anthropic or Gemini. ~5-10x
    speedup on rubrics with many items per pillar.

    - gemini-audio → judge_item_gemini_audio (audio-only mp3, for sound items)
    - gemini-video / gemini-av → judge_item_gemini_video (full repurpose.mp4 with
      both picture and audio, for items that need both — e.g. caption-sync)
    - opus-vision / default → Opus with frame evidence
    - deterministic → we don't handle here (those are done in score_pillar_0);
      if we see them in pillars 1-3 we treat as opus-vision fallback
    """
    from concurrent.futures import ThreadPoolExecutor
    evidence = mark_cache(list(evidence))
    items_out = {}
    # pillar_max = sum of POSITIVE weights only (the achievable ceiling).
    # Negative-weight violation items only ever deduct from pillar_total on fire.
    max_total = sum(it["weight"] for it in items if it["weight"] > 0)

    def _score_one(it):
        judge_type = (it.get("judge", "") or "").strip().lower()
        try:
            if judge_type == "gemini-audio" and repurpose_path:
                r = judge_item_gemini_audio(it, repurpose_path)
            elif judge_type in ("gemini-video", "gemini-av") and repurpose_path:
                r = judge_item_gemini_video(it, repurpose_path)
            else:
                r = judge_item(client, evidence, it)
                r["judge_used"] = judge_type or "opus-vision"
        except Exception as e:
            r = {"pass": False, "score": 0, "max": it.get("weight", 0),
                 "desc": (it.get("criterion") or "")[:140],
                 "why": f"(judge error: {type(e).__name__}: {str(e)[:200]})"}
        return it["id"], r

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        # Submit all items; preserve original order in items_out
        for iid, r in ex.map(_score_one, items):
            items_out[iid] = r

    total = sum(r.get("score", 0) for r in items_out.values())
    return {"items": items_out, "pillar_total": total, "pillar_max": max_total}


def main():
    global BASE, RUBRIC, TASK_CONTEXT
    run_dir = sys.argv[1]
    source = sys.argv[2]
    run_id = sys.argv[3]
    BASE = resolve_workspace_from_run_dir(run_dir)
    RUBRIC, TASK_CONTEXT = load_rubric_and_context(BASE)
    repurpose = str(Path(run_dir) / "output" / "repurpose.mp4")
    results = BASE / "results"
    results.mkdir(parents=True, exist_ok=True)

    # Treat missing / empty / corrupt repurposed cuts as non-completion: all-zero scoring.
    # Empty = 0 bytes. Corrupt = ffprobe can't read duration OR duration is
    # trivially short. Duration target itself is scored by the rubric item.
    def _is_valid_repurpose(path: str) -> tuple[bool, str]:
        p = Path(path)
        if not p.exists():
            return False, "no repurpose.mp4"
        if p.stat().st_size < 10_000:  # < 10KB = certainly broken
            return False, f"repurpose too small ({p.stat().st_size}B)"
        try:
            info = probe(path)
            dur = float(info.get("format", {}).get("duration", 0) or 0)
        except Exception as e:
            return False, f"ffprobe failed: {e}"
        if dur < 2.0:
            return False, f"repurpose duration only {dur:.1f}s"
        return True, f"duration={dur:.1f}s size={p.stat().st_size}B"

    valid, reason = _is_valid_repurpose(repurpose)
    if not valid:
        all_pillars = sorted({it["pillar"] for it in RUBRIC["items"]})
        for p in all_pillars:
            items_p = [it for it in RUBRIC["items"] if it["pillar"] == p]
            zeroed_items = {}
            for it in items_p:
                # No-repurpose = penalty fires on narrative_essential items
                # (repurpose is missing the beat by definition).
                sc, mx = _score_max(it, passed=False)
                zeroed_items[it["id"]] = {
                    "pass": False, "score": sc, "max": mx,
                    "desc": it["criterion"],
                    "why": f"rollout did not produce a valid repurpose: {reason}",
                }
            (results / f"{run_id}_p{p}.json").write_text(json.dumps(
                {"run_id": run_id, "pillar": p,
                 "items": zeroed_items,
                 # narrative_essential penalties fire when no repurpose was produced
                 "pillar_total": sum(v["score"] for v in zeroed_items.values()),
                 # Positive-only ceiling (violation pillars have pillar_max=0)
                 "pillar_max": sum(it["weight"] for it in items_p if it["weight"] > 0),
                 "error": reason}, indent=2))
        print(f"{run_id}: NO-VALID-REPURPOSE ({reason}) — all pillars scored 0")
        return

    # Skip pillars whose result files already exist (allows targeted re-runs:
    # delete only the pillar files you want re-judged, leave others to skip).
    def _result_exists(pillar: int) -> bool:
        return (results / f"{run_id}_p{pillar}.json").exists()

    # P0
    if _result_exists(0):
        p0 = json.loads((results / f"{run_id}_p0.json").read_text())
        print(f"{run_id}: P0 (cached) {p0['pillar_total']}/{p0['pillar_max']}")
    else:
        p0 = score_pillar_0(repurpose, source)
        p0["run_id"] = run_id; p0["pillar"] = 0
        (results / f"{run_id}_p0.json").write_text(json.dumps(p0, indent=2))
        print(f"{run_id}: P0 {p0['pillar_total']}/{p0['pillar_max']}")

    segments = p0.get("segments", [])

    client = anthropic.Anthropic()
    # Auto-detect golden human-reference repurpose (golden-task variants only).
    # Path is workspace-relative `golden/repurpose.mp4`. Pre-existing 36 tasks have no
    # such file; golden_path stays None and behavior is unchanged.
    golden_candidate = BASE / "golden" / "repurpose.mp4"
    golden_path: str | None = str(golden_candidate) if golden_candidate.exists() and not REPURPOSE_ONLY else None
    if golden_path:
        print(f"{run_id}: golden reference detected at {golden_path}")
    # P1
    if _result_exists(1):
        p1 = json.loads((results / f"{run_id}_p1.json").read_text())
        print(f"{run_id}: P1 (cached) {p1['pillar_total']}/{p1['pillar_max']}")
    else:
        p1_ev = build_pillar_1_evidence(repurpose, source, golden_path=golden_path)
        p1_items = [it for it in RUBRIC["items"] if it["pillar"] == 1]
        p1 = judge_pillar(client, 1, p1_ev, p1_items, repurpose)
        p1["run_id"] = run_id; p1["pillar"] = 1
        (results / f"{run_id}_p1.json").write_text(json.dumps(p1, indent=2))
        print(f"{run_id}: P1 {p1['pillar_total']}/{p1['pillar_max']}")
    # P2
    if _result_exists(2):
        p2 = json.loads((results / f"{run_id}_p2.json").read_text())
        print(f"{run_id}: P2 (cached) {p2['pillar_total']}/{p2['pillar_max']}")
    else:
        p2_ev = build_pillar_2_evidence(repurpose, segments, golden_path=golden_path)
        p2_items = [it for it in RUBRIC["items"] if it["pillar"] == 2]
        p2 = judge_pillar(client, 2, p2_ev, p2_items, repurpose)
        p2["run_id"] = run_id; p2["pillar"] = 2
        (results / f"{run_id}_p2.json").write_text(json.dumps(p2, indent=2))
        print(f"{run_id}: P2 {p2['pillar_total']}/{p2['pillar_max']}")
    # P3
    if _result_exists(3):
        p3 = json.loads((results / f"{run_id}_p3.json").read_text())
        print(f"{run_id}: P3 (cached) {p3['pillar_total']}/{p3['pillar_max']}")
    else:
        p3_ev = build_pillar_3_evidence(repurpose, segments)
        p3_items = [it for it in RUBRIC["items"] if it["pillar"] == 3]
        p3 = judge_pillar(client, 3, p3_ev, p3_items, repurpose)
        p3["run_id"] = run_id; p3["pillar"] = 3
        (results / f"{run_id}_p3.json").write_text(json.dumps(p3, indent=2))
        print(f"{run_id}: P3 {p3['pillar_total']}/{p3['pillar_max']}")
    # P4 — Violations pillar (negative-weight items). Route each item as its
    # `judge:` annotation says. Visual violations use P1 evidence (1fps frames
    # + source refs); audio violations use P3 evidence if we were to use any,
    # but in practice each item's judge call fetches what it needs.
    p4_items = [it for it in RUBRIC["items"] if it["pillar"] == 4]
    if p4_items:
        p4 = judge_pillar(client, 4, p1_ev, p4_items, repurpose)
        p4["run_id"] = run_id; p4["pillar"] = 4
        (results / f"{run_id}_p4.json").write_text(json.dumps(p4, indent=2))
        print(f"{run_id}: P4 {p4['pillar_total']}/{p4['pillar_max']}")


if __name__ == "__main__":
    main()
