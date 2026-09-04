#!/usr/bin/env python3
"""Derive the HUD powerup-indicator rectangle for a given render size.

The numbers come from SuperTuxKart 1.5's own drawing code, not from measurement:

  RaceGUI::renderPlayerView   scaling starts at (1,1) for a single local player
                              (Camera::setupCamera: screen size / viewport, equal
                              when there is no splitscreen), then is multiplied by
                              sqrt(W/800) and by sqrt(H/450) -- both factors apply
                              to both components, so scale = sqrt(W*H/360000).
  RaceGUIBase::drawPowerupIcons
                              nSize       = int(powerup_size * scale)   [size 64]
                              itemSpacing = int(scale * powerup_size / 2)
                              y1          = int(20 * scale)
                              x1          = W/2 - (n*itemSpacing)/2     [display 0]
                              icon i      = x1 + i*itemSpacing - itemSpacing/2,
                                            width nSize
                              n > 5       collapses to one icon plus an "xN" label
                                            drawn in [x2+nSize, x2+2*nSize]
  items/powerup.hpp           MAX_POWERUPS = 5, and the collect path clamps to it,
                              so n = 5 is reachable and is the widest icon row.

All divisions are integer divisions, matching the C++.
"""
import argparse
import math

POWERUP_SIZE = 64.0


def indicator_extent(w, h, powerup_size=POWERUP_SIZE):
    """Return (left, right, top, bottom) of the union of indicator layouts n=1..5.

    The union is what a mask has to cover, because the row is centred and so it
    grows outward as the held-item count rises.
    """
    scale = math.sqrt((w * h) / 360000.0)
    n_size = int(powerup_size * scale)
    spacing = int(scale * powerup_size / 2.0)
    y1 = int(20 * scale)

    lefts, rights = [], []
    for n in range(1, 6):
        x1 = w // 2 - (n * spacing) // 2
        first = x1 - spacing // 2
        last = x1 + (n - 1) * spacing - spacing // 2
        lefts.append(first)
        rights.append(last + n_size)
    # The ">5" case draws one icon and then a count label one icon-width further right.
    x2_one = w // 2 - (1 * spacing) // 2 - spacing // 2
    rights.append(x2_one + 2 * n_size)
    return min(lefts), max(rights), y1, y1 + n_size


def mask_box(w, h, margin_x=18, top=5, bottom_margin=16):
    """Return (x, y, box_w, box_h) covering the indicator with margin."""
    left, right, _, bottom = indicator_extent(w, h)
    x = max(0, left - margin_x)
    right_edge = min(w, right + margin_x + 8)
    y = top
    box_h = (bottom + bottom_margin) - y
    return x, y, right_edge - x, box_h


def _selftest():
    """Check the derivation against the shipped 1280x720 render size."""
    left, right, top, bottom = indicator_extent(1280, 720)
    assert (left, right, top, bottom) == (488, 794, 32, 134), (left, right, top, bottom)
    # The box that shipped before this fix started at x=505, which clips the n=5 row.
    assert left < 505, "n=5 row must start left of the old box for the bug to be real"
    x, y, bw, bh = mask_box(1280, 720)
    assert x <= left and x + bw >= right, (x, bw, left, right)
    assert y <= top and y + bh >= bottom, (y, bh, top, bottom)
    print("selftest ok: 1280x720 indicator x=[488,794) y=[32,134); "
          "box x=%d y=%d w=%d h=%d" % (x, y, bw, bh))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--shell", action="store_true", help="emit MASK_* shell assignments")
    a = ap.parse_args()
    if a.selftest:
        _selftest()
    else:
        left, right, top, bottom = indicator_extent(a.width, a.height)
        x, y, bw, bh = mask_box(a.width, a.height)
        if a.shell:
            print("MASK_X=%d MASK_Y=%d MASK_W=%d MASK_H=%d" % (x, y, bw, bh))
        else:
            print("indicator x=[%d,%d) y=[%d,%d)" % (left, right, top, bottom))
            print("mask box  x=%d y=%d w=%d h=%d" % (x, y, bw, bh))
