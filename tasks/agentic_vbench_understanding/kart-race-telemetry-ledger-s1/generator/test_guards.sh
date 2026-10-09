#!/bin/bash
# Prove the generator's two guards FIRE, not merely that they pass on good input. A guard that has
# only ever been run against the case it approves is not evidence of anything; both of these were
# weaker than they looked until this test existed:
#   * check_hud_config.sh matched the STRING PREFIX powerup-icon-size="64, which also accepts 640.
#   * run_race.sh happily re-used a populated output directory, so a re-run would assert on the
#     PREVIOUS race's config.xml and could concatenate a stale race_raw.mp4.
#
# Usage: test_guards.sh          (exit 0 = every case behaved as required)
set -uo pipefail
HERE=$(cd "$(dirname "$(readlink -f "$0")")" && pwd)
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
PASS=0; FAIL=0

want() {  # want <expected-exit> <label> -- <command...>
  local exp="$1" label="$2"; shift 3
  "$@" >"$TMP/out" 2>&1; local got=$?
  if [ "$got" = "$exp" ]; then
    PASS=$((PASS+1)); printf '  [PASS] %-52s exit %s\n' "$label" "$got"
  else
    FAIL=$((FAIL+1)); printf '  [FAIL] %-52s exit %s, wanted %s\n' "$label" "$got" "$exp"
    sed 's/^/         /' "$TMP/out"
  fi
}

mkcfg() {  # mkcfg <dir> <display> <size>
  local d="$TMP/$1/.config/supertuxkart/config-0.10"
  mkdir -p "$d"
  cat > "$d/config.xml" <<XML
<?xml version="1.0"?>
<stkconfig>
    <PowerUp
        display="$2"
        powerup-icon-size="$3"
    >
    </PowerUp>
</stkconfig>
XML
}

echo "check_hud_config.sh — the size is compared numerically against hud_mask.POWERUP_SIZE"
mkcfg good 0 "64.000000";      want 0  "default config (display 0, 64.000000)"        -- bash "$HERE/check_hud_config.sh" "$TMP/good"
mkcfg side 1 "64.000000";      want 12 "indicator moved to the side (display 1)"      -- bash "$HERE/check_hud_config.sh" "$TMP/side"
mkcfg hidden 2 "64.000000";    want 12 "indicator hidden (display 2)"                 -- bash "$HERE/check_hud_config.sh" "$TMP/hidden"
mkcfg big 0 "96.000000";       want 12 "icon resized to 96"                           -- bash "$HERE/check_hud_config.sh" "$TMP/big"
mkcfg pfx640 0 "640.000000";   want 12 "icon 640 — the old prefix match ACCEPTED this" -- bash "$HERE/check_hud_config.sh" "$TMP/pfx640"
mkcfg pfx649 0 "64999";        want 12 "icon 64999 — same prefix-match class"          -- bash "$HERE/check_hud_config.sh" "$TMP/pfx649"
mkcfg small 0 "63.999000";     want 12 "icon 63.999 — just off the derived size"       -- bash "$HERE/check_hud_config.sh" "$TMP/small"
mkdir -p "$TMP/empty";         want 11 "no config.xml at all"                          -- bash "$HERE/check_hud_config.sh" "$TMP/empty"
d="$TMP/malformed/.config/supertuxkart/config-0.10"; mkdir -p "$d"
printf '<stkconfig>\n    <PowerUp\n    >\n</stkconfig>\n' > "$d/config.xml"
want 13 "<PowerUp> without the attributes"                                             -- bash "$HERE/check_hud_config.sh" "$TMP/malformed"

echo
echo "run_race.sh / run_suite.sh — a used output directory is refused"
export AGENTICVBENCH_PRECHECK_ONLY=1 STK_DISP=99
mkdir -p "$TMP/fresh"
want 0  "fresh (empty) output directory is accepted"    -- bash "$HERE/run_race.sh" "$TMP/fresh" scotland 1 tux 3 tux
mkdir -p "$TMP/dirty"; echo stale > "$TMP/dirty/race_raw.mp4"
want 14 "populated output directory is refused"         -- bash "$HERE/run_race.sh" "$TMP/dirty" scotland 1 tux 3 tux
AGENTICVBENCH_ALLOW_DIRTY_OUT=1 \
want 0  "…unless AGENTICVBENCH_ALLOW_DIRTY_OUT=1"       -- env AGENTICVBENCH_ALLOW_DIRTY_OUT=1 bash "$HERE/run_race.sh" "$TMP/dirty" scotland 1 tux 3 tux
mkdir -p "$TMP/suite"; echo stale > "$TMP/suite/race0.log"
want 14 "run_suite.sh refuses a populated directory too" -- bash "$HERE/run_suite.sh" "$TMP/suite"

echo
echo "$PASS passed, $FAIL failed"
[ "$FAIL" = 0 ]
