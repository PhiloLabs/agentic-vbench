#!/usr/bin/env python3
"""Classify a captured Minecraft frame as `world`, `ui` or `flat`, so a recording is never started
against a screen that is not the game.

    screen_state.py FRAME.png       -> "world dominant=0.13 colours=161 menu_buttons=0"
                                       exit 0 if the frame is the world, 1 otherwise

Both signals were calibrated against real frames, and the obvious cheap checks were tried and
rejected first:

  * **Brightness / std / raw colour count do not work.** A death screen dims the world under a
    translucent red wash and measures brightness 99, std 45 — indistinguishable from healthy
    gameplay. Trusting those numbers is exactly how a 378 s recording of the death screen got
    reported as a successful render.
  * **"any UI slab present" does not work either.** `bands.py` reports one large slab for *every*
    frame, world frames included (1132x573 on a HUD'd render, and one on a bare render too), so
    `buttons > 0` rejects everything.

What does separate them, measured on every frame that has come up so far:

  | frame                          | dominant | quantised colours | menu-button-shaped slabs |
  |--------------------------------|----------|-------------------|--------------------------|
  | death screen                   | 0.35     | 21                | 1 (594x54)               |
  | loading terrain                | 0.66     | 12                | 0                        |
  | camera in undownloaded chunks  | 0.60     | 6                 | 0                        |
  | world, bare render (open)      | 0.13     | 161               | 0                        |
  | world, HUD composited          | 0.25     | 226               | 0                        |
  | world, real client mid-forest  | 0.19     | 52                | 0                        |

So: a *stock menu button* is ~600x40 at GUI scale 3 and nothing in a world view has that shape,
while flat screens collapse into very few quantised colours and one dominant colour. Both clusters
are well separated on both axes, so the thresholds sit between them rather than next to either.
"""
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# Thresholds sit between the two observed clusters with margin on BOTH sides. COLOURS_MIN was first
# set to 60 from a two-frame sample (161 and 226) and promptly misjudged a legitimate close-range
# forest view at 45-52 colours as flat -- an over-tight threshold from too few samples.
#   world frames measured: dominant 0.13 0.16 0.19 0.20 0.25   colours 45 52 87 161 226
#   flat  frames measured: dominant 0.60 0.66                  colours 6 12
DOMINANT_MAX = 0.40
COLOURS_MIN = 30
BUTTON_W = (555, 625)  # a stock menu button is 200 px * GUI scale 3
BUTTON_H = (26, 74)


def menu_buttons(path):
    """Number of slabs shaped like a stock Minecraft menu button (Respawn, Title Screen, ...)."""
    here = Path(__file__).resolve().parent
    out = subprocess.run(["/usr/bin/python3", str(here / "bands.py"), str(path)],
                         capture_output=True, text=True).stdout
    n = 0
    for w, h in re.findall(r"size=(\d+)x(\d+)", out):
        w, h = int(w), int(h)
        if BUTTON_W[0] <= w <= BUTTON_W[1] and BUTTON_H[0] <= h <= BUTTON_H[1]:
            n += 1
    return n


def classify(path):
    """(state, dominant_share, n_quantised_colours, n_menu_buttons) for one frame."""
    a = np.asarray(Image.open(path).convert("RGB"))
    q = (a // 32).reshape(-1, 3)
    _, counts = np.unique(q, axis=0, return_counts=True)
    dominant = counts.max() / counts.sum()
    colours = len(counts)
    buttons = menu_buttons(path)

    if buttons > 0:
        state = "ui"
    elif dominant > DOMINANT_MAX or colours < COLOURS_MIN:
        state = "flat"
    else:
        state = "world"
    return state, dominant, colours, buttons


def main():
    state, dom, cols, btn = classify(sys.argv[1])
    print(f"{state} dominant={dom:.2f} colours={cols} menu_buttons={btn}")
    sys.exit(0 if state == "world" else 1)


if __name__ == "__main__":
    main()
