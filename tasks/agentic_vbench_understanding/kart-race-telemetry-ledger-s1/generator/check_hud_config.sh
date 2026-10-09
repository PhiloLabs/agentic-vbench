#!/bin/bash
# Assert that the SuperTuxKart config written under a race's config home leaves the powerup
# indicator at its DEFAULT placement and size.
#
# generator/hud_mask.py derives the mask rectangle for the default centred indicator (display 0) at
# hud_mask.POWERUP_SIZE. A config that moved the indicator to the side (display 1), hid it
# (display 2) or resized it would put sprites outside that rectangle, so the shipped media would
# leak the very thing the mask exists to hide. This is asserted on the config the race actually
# wrote, not on the environment it inherited.
#
# The comparison is EXACT and numeric, and the expected size is read from hud_mask.py rather than
# repeated here, so the guard cannot drift from the box it is protecting. An earlier version matched
# the string prefix `powerup-icon-size="64`, which also accepted 640 and 64999 -- a guard that looks
# strict and is not.
#
# Usage: check_hud_config.sh STKHOME_DIR
#   exit 0  = defaults
#        11 = no config.xml (nothing to assert on)
#        12 = present but NOT the defaults the mask assumes
#        13 = could not parse the config or read hud_mask.POWERUP_SIZE
set -uo pipefail
HOME_DIR=${1:?usage: check_hud_config.sh STKHOME_DIR}
HERE=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)

CFG=$(find "$HOME_DIR" -name config.xml -print -quit 2>/dev/null || true)
if [ -z "$CFG" ]; then
  echo "check_hud_config: no config.xml under $HOME_DIR; cannot confirm default HUD placement"
  exit 11
fi

/usr/bin/python3 - "$CFG" "$HERE" <<'PY'
import re, sys
cfg, here = sys.argv[1], sys.argv[2]
sys.path.insert(0, here)
try:
    import hud_mask
    expect = float(hud_mask.POWERUP_SIZE)
except Exception as exc:                       # the guard must not silently pass without its target
    print("check_hud_config: cannot read POWERUP_SIZE from hud_mask.py (%s)" % exc)
    sys.exit(13)

text = open(cfg, errors="ignore").read()
m = re.search(r"<PowerUp\b(.*?)>", text, re.S)
if not m:
    print("check_hud_config: no <PowerUp> element in %s" % cfg)
    sys.exit(13)
body = m.group(1)

def attr(name):
    a = re.search(r'(?:^|\s)%s="([^"]*)"' % re.escape(name), body)
    return a.group(1) if a else None

disp, size = attr("display"), attr("powerup-icon-size")
if disp is None or size is None:
    print("check_hud_config: <PowerUp> lacks display/powerup-icon-size in %s" % cfg)
    sys.exit(13)
try:
    size_f = float(size)
except ValueError:
    print("check_hud_config: powerup-icon-size=%r is not a number in %s" % (size, cfg))
    sys.exit(13)

if disp.strip() != "0":
    print('check_hud_config: powerup indicator display=%s, not the default 0, in %s' % (disp, cfg))
    sys.exit(12)
if abs(size_f - expect) > 1e-6:
    print("check_hud_config: powerup icon size is %s, not the default %.6f that hud_mask.py "
          "derives the box from, in %s" % (size, expect, cfg))
    sys.exit(12)
print("check_hud_config: OK, default centred indicator at %.6f px (%s)" % (size_f, cfg))
PY
