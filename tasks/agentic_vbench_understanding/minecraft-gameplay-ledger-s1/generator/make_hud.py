#!/usr/bin/env python3
"""Render an authentic Minecraft HUD overlay (transparent PNG) for the headless capture.

    make_hud.py OUT.png [SELECTED_ITEM]

prismarine-viewer draws only the 3D world, so the familiar HUD has to be composited back on.
It is built from the *real* game GUI sprites that ship with prismarine-viewer (the same
texture set already rendering the blocks in the video) at vanilla geometry, rather than
hand-drawn shapes:

  widgets.png  (0,0,182,22)   hotbar          (0,22,24,24) selected-slot highlight
  icons.png    (16,0,9,9)     heart outline   (52,0,9,9)   full heart
               (16,27,9,9)    hunger outline  (52,27,9,9)  full haunch
               (0,64,182,5)   xp bar empty    (0,69,182,5) xp bar filled
  items/*.png, blocks/*.png   16x16 item sprites drawn in the slots

Vanilla layout at GUI scale 3 on a 1280x720 screen (GUI space is 426x240):
  hotbar   x = centre-91, y = 240-22        hearts y = 240-39 (left of centre)
  xp bar   y = 240-32                       hunger y = 240-39 (right of centre)

The highlighted slot is an argument: one PNG is rendered per item the player actually holds
and the overlays are time-gated from the bot's held-item timeline, so the hotbar is evidence
for the weapon used, not decoration.
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

TEX = Path(__file__).resolve().parent / "node_modules/prismarine-viewer/public/textures/1.16.4"
SCALE = 3
W, H = 1280, 720
GW, GH = W // SCALE, H // SCALE          # 426 x 240 GUI space

# slot index -> (sprite path, mineflayer item name that selects it)
SLOTS = [
    ("items/diamond_sword.png",   "diamond_sword"),
    ("items/diamond_pickaxe.png", "diamond_pickaxe"),
    ("items/diamond_axe.png",     "diamond_axe"),
    ("items/diamond_shovel.png",  "diamond_shovel"),
    ("items/bow.png",             "bow"),
    ("blocks/oak_planks.png",     "oak_planks"),
    ("blocks/stone_bricks.png",   "stone_bricks"),
    ("blocks/glass.png",          "glass"),
    ("blocks/torch.png",         "torch"),
]

widgets = Image.open(TEX / "gui/widgets.png").convert("RGBA")
icons = Image.open(TEX / "gui/icons.png").convert("RGBA")

def sprite(img, x, y, w, h, scale=SCALE):
    return img.crop((x, y, x + w, y + h)).resize((w * scale, h * scale), Image.NEAREST)

hud = Image.new("RGBA", (W, H), (0, 0, 0, 0))

hb_x = (GW // 2 - 91) * SCALE
hb_y = (GH - 22) * SCALE
hud.alpha_composite(sprite(widgets, 0, 0, 182, 22), (hb_x, hb_y))

for i, (rel, _) in enumerate(SLOTS):
    p = TEX / rel
    if not p.exists():
        continue
    item = Image.open(p).convert("RGBA").resize((16 * SCALE, 16 * SCALE), Image.NEAREST)
    hud.alpha_composite(item, (hb_x + (3 + i * 20) * SCALE, hb_y + 3 * SCALE))

sel = sys.argv[2] if len(sys.argv) > 2 else "diamond_sword"
k = next((i for i, (_, name) in enumerate(SLOTS) if name == sel), 0)
hud.alpha_composite(sprite(widgets, 0, 22, 24, 24), (hb_x + (i_off := (k * 20 - 1)) * SCALE, hb_y - 1 * SCALE))

xp_y = (GH - 32) * SCALE
hud.alpha_composite(sprite(icons, 0, 64, 182, 5), (hb_x, xp_y))
hud.alpha_composite(sprite(icons, 0, 69, int(182 * 0.62), 5), (hb_x, xp_y))

# Vitals sit two rows higher than the strict-vanilla offset so the hearts/hunger clear the
# hotbar comfortably (requested — they read as "a little above").
row_y = (GH - 43) * SCALE
for i in range(10):                                   # health, left of centre
    x = hb_x + i * 8 * SCALE
    hud.alpha_composite(sprite(icons, 16, 0, 9, 9), (x, row_y))
    hud.alpha_composite(sprite(icons, 52, 0, 9, 9), (x, row_y))
for i in range(10):                                   # hunger, right of centre
    x = hb_x + (91 + 91 - 9 - i * 8) * SCALE
    hud.alpha_composite(sprite(icons, 16, 27, 9, 9), (x, row_y))
    hud.alpha_composite(sprite(icons, 52, 27, 9, 9), (x, row_y))

# First-person held item. prismarine-viewer renders no hand or held item, so — like the rest
# of the HUD — it is composited from the real item texture. Drawn large in the lower-right at
# the vanilla-ish first-person angle, over a simple arm, so the player is visibly holding
# (and, per equip, switching to) the sword / bow / pickaxe. This rides the same per-item HUD
# spans, so it costs no extra compositing pass and always matches the highlighted slot.
def first_person_item(rel):
    p = TEX / rel
    if not p.exists():
        return
    big = 26 * SCALE
    item = Image.open(p).convert("RGBA").resize((big, big), Image.NEAREST).rotate(-40, expand=True)
    ax, ay = W - int(big * 1.15), H - int(big * 1.15)
    arm = Image.new("RGBA", (int(big * 0.55), int(big * 1.3)), (0, 0, 0, 0))
    ad = ImageDraw.Draw(arm)
    ad.rectangle([0, 0, arm.width - 1, arm.height - 1], fill=(199, 149, 111, 255),
                 outline=(120, 80, 55, 255), width=SCALE)                    # skin arm
    ad.rectangle([0, 0, arm.width - 1, int(arm.height * 0.30)], fill=(60, 130, 160, 255))  # sleeve cuff
    arm = arm.rotate(28, expand=True)
    hud.alpha_composite(arm, (W - arm.width - int(big * 0.35), H - arm.height))
    hud.alpha_composite(item, (ax, ay))

first_person_item(SLOTS[k][0])

out = sys.argv[1] if len(sys.argv) > 1 else "hud.png"
hud.save(out)
print("wrote", out, "selected", SLOTS[k][1])
