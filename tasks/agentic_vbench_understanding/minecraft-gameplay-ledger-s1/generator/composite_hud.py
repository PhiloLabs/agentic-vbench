#!/usr/bin/env python3
"""Composite the Minecraft-style HUD onto the headless render, with the highlighted hotbar
slot tracking what the player was actually holding.

    composite_hud.py RAW_VIDEO PLAY_JSON OFFSET_S OUT_MP4

PLAY_JSON carries the bot's `held` timeline ({item, t_ms} since the capture's GO), and
OFFSET_S is the seconds from the first recorded frame to GO (printed by capture_mc.py), so
video_time = offset + t_ms/1000. One HUD PNG is rendered per held item and gated with
overlay `enable='between(t,a,b)'`; the last state runs to the end of the video.

Also normalises to constant frame rate — the browser recording is variable-FPS.
"""
import json, subprocess, sys
from pathlib import Path

raw, play, offset, out = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3]), Path(sys.argv[4])
here = Path(__file__).resolve().parent
work = out.parent / "hud_frames"; work.mkdir(parents=True, exist_ok=True)

FF = subprocess.run(["/usr/bin/python3", "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
                    capture_output=True, text=True, check=True).stdout.strip()

held = json.loads(play.read_text()).get("held", [])
if not held:
    held = [{"item": "diamond_sword", "t_ms": 0}]

def duration_of(path):
    """Seconds of video. The imageio ffmpeg build ships no ffprobe, so parse ffmpeg's own
    header dump; fall back to a huge value so the last HUD span simply runs to the end."""
    for probe in ("/pkg/ffmpeg/4.2.2/bin/ffprobe", "ffprobe"):
        r = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", str(path)], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            try:
                return float(r.stdout.strip())   # 'N/A' (unfinalised webm header) -> fall through
            except ValueError:
                pass
        # fall back to counting decoded frames when the container carries no duration
        r = subprocess.run([probe, "-v", "error", "-count_frames", "-select_streams", "v:0",
                            "-show_entries", "stream=nb_read_frames,avg_frame_rate",
                            "-of", "csv=p=0", str(path)], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            try:
                nf, rate = r.stdout.strip().split(",")[:2]
                num, den = (rate.split("/") + ["1"])[:2]
                fps = float(num) / float(den or 1)
                if fps > 0:
                    return int(nf) / fps
            except (ValueError, ZeroDivisionError):
                pass
    return 1e6

dur = duration_of(raw)

# collapse the timeline into [start, end, item] windows in VIDEO time
spans = []
for i, h in enumerate(held):
    a = offset + h["t_ms"] / 1000.0
    b = (offset + held[i+1]["t_ms"] / 1000.0) if i + 1 < len(held) else dur
    if b > a:
        spans.append((max(0.0, a), b, h["item"]))
if spans:
    spans[0] = (0.0, spans[0][1], spans[0][2])   # cover the pre-first-equip head of the video

pngs = {}
for _, _, item in spans:
    if item in pngs: continue
    p = work / f"hud_{item}.png"
    subprocess.run(["/usr/bin/python3", str(here / "make_hud.py"), str(p), item], check=True,
                   capture_output=True)
    pngs[item] = p

# Drop the dead head: recording starts ~10s before the session does, and frame_audit shows
# those seconds are always flat sky. Spans shift with it so the HUD stays aligned.
_ev0 = json.loads(play.read_text()).get("events", [])
# Cut the prologue, not just the pre-roll: the session opens with a biome teleport and chunk
# load during which the camera has nothing to frame, and frame_audit flags those seconds as
# flat sky in every single run. Keep 8s of lead-in before the first real action.
head = max(0.0, offset + (_ev0[0]["t_ms"]/1000.0 - 8.0 if _ev0 else -1.0))
spans = [(max(0.0, a - head), b - head, it) for a, b, it in spans if b > head]
if spans: spans[0] = (0.0, spans[0][1], spans[0][2])

inputs = ["-ss", f"{head:.2f}", "-i", str(raw)]
order = list(pngs)
for item in order:
    inputs += ["-i", str(pngs[item])]

chain, cur = [], "0:v"
for k, item in enumerate(order, start=1):
    windows = "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b, it in spans if it == item)
    nxt = f"v{k}"
    chain.append(f"[{cur}][{k}:v]overlay=0:0:enable='{windows}'[{nxt}]")
    cur = nxt
fc = ";".join(chain)

# Trim the dead tail: Playwright's recording runs on past the last gameplay event.
# Verified against landmarks that video_time == offset + t_ms (no time stretch), so the
# last event's time is a trustworthy cut point.
ev = json.loads(play.read_text()).get("events", [])
end = (offset - head + ev[-1]["t_ms"] / 1000.0 + 6.0) if ev else dur
limit = ["-t", f"{min(end, dur):.2f}"] if end < dur else []

cmd = [FF, "-v", "error", *inputs, "-filter_complex", fc, "-map", f"[{cur}]",
       *limit, "-r", "25", "-vsync", "cfr", "-c:v", "libx264", "-crf", "22", "-pix_fmt", "yuv420p",
       str(out), "-y"]
subprocess.run(cmd, check=True)
print("wrote", out)
print("spans:", [(round(a,1), round(b,1), it) for a, b, it in spans])
