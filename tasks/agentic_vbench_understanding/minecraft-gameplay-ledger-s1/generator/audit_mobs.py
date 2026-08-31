#!/usr/bin/env python3
"""Screenshot each mob the audit bot shows. Marker-driven (not time-driven): the bot writes
the mob name to CUR once the mob is summoned and framed; we shoot, then clear CUR to let the
bot advance. No drift, so every PNG is guaranteed to show the mob it is named after."""
import sys, time, os
from pathlib import Path
from playwright.sync_api import sync_playwright

outdir = Path(sys.argv[1]); outdir.mkdir(parents=True, exist_ok=True)
GO, DONE, CUR = sys.argv[2], sys.argv[3], sys.argv[4]
for f in (GO, DONE, CUR):
    try: os.remove(f)
    except OSError: pass

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox","--disable-dev-shm-usage","--use-gl=swiftshader"])
    page = b.new_page(viewport={"width":640,"height":480})
    page.goto("http://localhost:3009", wait_until="load")
    time.sleep(10)
    Path(GO).write_text("go")
    n, t0 = 0, time.time()
    while not Path(DONE).exists() and time.time() - t0 < 600:
        cur = Path(CUR)
        name = cur.read_text().strip() if cur.exists() else ""
        if not name:
            time.sleep(0.2); continue
        time.sleep(1.0)                      # let the render settle on this mob
        page.screenshot(path=str(outdir / f"{n:02d}_{name}.png"))
        print("shot", name, flush=True)
        n += 1
        cur.write_text("")                   # release the bot
    b.close()
print("AUDIT_SHOTS_DONE", n, flush=True)
