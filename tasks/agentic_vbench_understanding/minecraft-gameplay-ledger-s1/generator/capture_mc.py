#!/usr/bin/env python3
"""Orchestrate the P1 capture: connect Playwright to the prismarine-viewer, start
recording, trigger the bot build (GO file), wait for DONE, close recording. Prints the
sync offset = seconds from recording frame0 to build start, so GT event times can be
shifted to video time."""
import sys, time, os
from pathlib import Path
from playwright.sync_api import sync_playwright

viewer_url = "http://localhost:3007"
outdir = Path(sys.argv[1]); outdir.mkdir(parents=True, exist_ok=True)
GO = sys.argv[2]; DONE = sys.argv[3]
max_s = int(sys.argv[4]) if len(sys.argv) > 4 else 900
for f in (GO, DONE):
    try: os.remove(f)
    except OSError: pass

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox","--disable-dev-shm-usage","--use-gl=swiftshader"])
    t_ctx = time.time()
    ctx = b.new_context(viewport={"width":1280,"height":720},
                        record_video_dir=str(outdir),
                        record_video_size={"width":1280,"height":720})
    page = ctx.new_page()
    page.goto(viewer_url, wait_until="load")
    time.sleep(8)   # let three.js load chunks/textures before the build starts
    Path(GO).write_text("go")
    t_go = time.time()
    print(f"OFFSET_S {t_go - t_ctx:.2f}", flush=True)
    # wait for DONE
    waited = 0
    while not Path(DONE).exists() and waited < max_s:
        time.sleep(2); waited += 2
    time.sleep(4)   # tail: let last block animation render
    vid = page.video.path()
    ctx.close(); b.close()
    print("VIDEO", vid, flush=True)
    print("DONE_SEEN", Path(DONE).exists(), flush=True)
