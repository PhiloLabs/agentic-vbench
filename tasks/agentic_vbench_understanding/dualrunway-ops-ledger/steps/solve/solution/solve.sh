#!/bin/bash
# Oracle: write the verified runway-operations ledger as solution.json.
#
# This is the verified answer key, not an echo of the input -- the agent's image never
# contains it. Every row was built from the live ADS-B state-vector capture taken
# during the recording (icao24 -> registration -> the on-screen tracking panel for
# identity and type, debounced on_ground transitions for the operation and its time),
# then filtered down to the operations the camera can be SHOWN to have tracked.
#
# Must stay byte-identical in content to GROUND_TRUTH in tests/judge.py, or the oracle
# stops scoring 1.0.
set -euo pipefail

mkdir -p /workspace/output

python3 - <<'PY'
import json
from pathlib import Path

OPERATIONS = [
    {"video_time": "00:03:51", "operation": "landing", "aircraft_type": "regional-jet", "callsign": "SKW4179"},
    {"video_time": "00:08:51", "operation": "landing", "aircraft_type": "A320-family", "callsign": "FFT2017"},
    {"video_time": "00:10:35", "operation": "landing", "aircraft_type": "B737-family", "callsign": "SWA2177"},
    {"video_time": "00:12:07", "operation": "landing", "aircraft_type": "B757", "callsign": "DAL544"},
    {"video_time": "00:13:29", "operation": "landing", "aircraft_type": "B737-family", "callsign": "UAL1995"},
    {"video_time": "00:17:17", "operation": "landing", "aircraft_type": "A320-family", "callsign": "FFT3738"},
    {"video_time": "00:20:11", "operation": "landing", "aircraft_type": "B737-family", "callsign": "ASA531"},
    {"video_time": "00:30:13", "operation": "landing", "aircraft_type": "regional-jet", "callsign": "QXE2274"},
    {"video_time": "00:35:33", "operation": "landing", "aircraft_type": "A320-family", "callsign": "AAL2785"},
    {"video_time": "00:38:25", "operation": "landing", "aircraft_type": "regional-jet", "callsign": "JSX311"},
    {"video_time": "00:40:44", "operation": "takeoff", "aircraft_type": "regional-jet", "callsign": "JSX626"},
    {"video_time": "00:46:03", "operation": "landing", "aircraft_type": "B737-family", "callsign": "SWA3675"},
    {"video_time": "00:55:35", "operation": "landing", "aircraft_type": "B737-family", "callsign": "SWA5051"},
    {"video_time": "00:57:11", "operation": "landing", "aircraft_type": "B737-family", "callsign": "SWA1169"},
    {"video_time": "01:00:27", "operation": "landing", "aircraft_type": "B737-family", "callsign": "SWA3745"},
    {"video_time": "01:05:34", "operation": "landing", "aircraft_type": "B737-family", "callsign": "SWA596"},
    {"video_time": "01:13:15", "operation": "landing", "aircraft_type": "A320-family", "callsign": "AAY28"},
    {"video_time": "01:25:11", "operation": "landing", "aircraft_type": "B737-family", "callsign": "AAL2025"},
    {"video_time": "01:26:05", "operation": "landing", "aircraft_type": "A320-family", "callsign": "AAY76"},
    {"video_time": "01:26:26", "operation": "landing", "aircraft_type": "B737-family", "callsign": "SWA3788"},
    {"video_time": "01:28:15", "operation": "landing", "aircraft_type": "B757", "callsign": "DAL825"},
    {"video_time": "01:29:51", "operation": "landing", "aircraft_type": "A330", "callsign": "ASA876"},
    {"video_time": "01:31:42", "operation": "landing", "aircraft_type": "B737-family", "callsign": "SWA3935"},
    {"video_time": "01:36:03", "operation": "landing", "aircraft_type": "B737-family", "callsign": "SWA365"},
    {"video_time": "01:37:35", "operation": "landing", "aircraft_type": "B737-family", "callsign": "SWA287"},
    {"video_time": "01:39:58", "operation": "takeoff", "aircraft_type": "A320-family", "callsign": "AAL1121"},
    {"video_time": "01:42:21", "operation": "landing", "aircraft_type": "B737-family", "callsign": "DAL2653"},
    {"video_time": "01:43:53", "operation": "landing", "aircraft_type": "B737-family", "callsign": "SWA372"},
    {"video_time": "01:45:20", "operation": "landing", "aircraft_type": "A320-family", "callsign": "AAY59"},
    {"video_time": "01:46:31", "operation": "landing", "aircraft_type": "B737-family", "callsign": "SWA799"},
    {"video_time": "01:46:58", "operation": "takeoff", "aircraft_type": "B737-family", "callsign": "SWA2871"},
    {"video_time": "01:48:03", "operation": "landing", "aircraft_type": "A320-family", "callsign": "AAL2872"},
    {"video_time": "01:49:39", "operation": "landing", "aircraft_type": "B737-family", "callsign": "SWA1567"},
    {"video_time": "01:50:51", "operation": "landing", "aircraft_type": "A320-family", "callsign": "FFT4156"},
    {"video_time": "01:54:20", "operation": "takeoff", "aircraft_type": "B737-family", "callsign": "SWA1056"},
    {"video_time": "01:58:03", "operation": "landing", "aircraft_type": "A320-family", "callsign": "AAY83"},
    {"video_time": "02:02:50", "operation": "takeoff", "aircraft_type": "B737-family", "callsign": "SWA4226"},
    {"video_time": "02:07:01", "operation": "landing", "aircraft_type": "B757", "callsign": "DAL955"},
    {"video_time": "02:08:49", "operation": "takeoff", "aircraft_type": "B737-family", "callsign": "AAL556"},
    {"video_time": "02:10:59", "operation": "landing", "aircraft_type": "B737-family", "callsign": "AAL1465"},
    {"video_time": "02:11:31", "operation": "takeoff", "aircraft_type": "B737-family", "callsign": "SWA2784"},
    {"video_time": "02:13:29", "operation": "landing", "aircraft_type": "B737-family", "callsign": "SWA1454"},
    {"video_time": "02:18:28", "operation": "landing", "aircraft_type": "A320-family", "callsign": "FFT2408"},
    {"video_time": "02:19:51", "operation": "landing", "aircraft_type": "B737-family", "callsign": "UAL406"},
    {"video_time": "02:21:42", "operation": "landing", "aircraft_type": "B737-family", "callsign": "SWA369"},
    {"video_time": "02:23:42", "operation": "landing", "aircraft_type": "B737-family", "callsign": "SWA963"},
    {"video_time": "02:26:19", "operation": "landing", "aircraft_type": "B737-family", "callsign": "DAL2949"},
    {"video_time": "02:27:07", "operation": "takeoff", "aircraft_type": "B757", "callsign": "DAL502"},
    {"video_time": "02:28:35", "operation": "landing", "aircraft_type": "B737-family", "callsign": "SWA4378"},

]

Path("/workspace/output/solution.json").write_text(
    json.dumps({"operations": OPERATIONS}, indent=2))
PY

echo "oracle: wrote /workspace/output/solution.json"
