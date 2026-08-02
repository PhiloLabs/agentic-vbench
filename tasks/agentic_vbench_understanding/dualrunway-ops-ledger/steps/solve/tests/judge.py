#!/usr/bin/env python3
"""Grade a runway-operations-ledger reconstruction. Pure Python stdlib, deterministic.

The agent must list every runway operation with video_time, operation, aircraft_type
and callsign. A prediction is a true positive only when it FULLY reconstructs the
event: same operation, same aircraft family, same callsign, and a video_time within
TOL seconds. reward = F1 over the verified ledger.

Why this metric: no single field is recoverable from one modality alone. callsign
exists only in the tower audio; operation, aircraft_type and video_time exist only in
the picture; and the two files carry no shared clock, so the agent must recover the
offset between them before any pairing is possible. A full-conjunction match is what
forces genuine audio<->video correspondence instead of partial credit from one channel.

DON'T-CARE SET -- why predictions can be excused rather than penalised
---------------------------------------------------------------------
GROUND_TRUTH holds only the operations we could VERIFY in the picture: the PTZ camera
demonstrably tracked that aircraft (a contiguous on-screen tracking segment of >=15 s)
and an ADS-B state transition for the same airframe lands within 30 s of it. The
recording also contains real operations that the camera was NOT pointed at -- it pans
to the Strip, to parking lots, and it follows one aircraft while another one lands.
Those are real events an agent may legitimately report from the tower audio, but we
cannot confirm them from the video, so they are neither scored as correct nor punished
as hallucinations. DONT_CARE holds them; a prediction matching one is dropped from the
precision denominator entirely.

Without this, F1 against a partial ledger would punish an agent for being RIGHT about
an operation our ground truth simply cannot see -- the "unobservable ground truth"
pitfall in the family README, in its second form.

A `runway` field was in an earlier draft and was REMOVED after measuring the source
recording: the tower states the runway in nearly every clearance and it is very nearly
constant across the window, so an agent could answer it for free. It added no
discrimination and is not scored.

GROUND_TRUTH is never shipped into the agent's image; only /tests mounts this file
during the verify step. See calibration/ for how it was built and what it cost.
"""
import argparse
import json
import re
from pathlib import Path

# Tolerance is set from MEASUREMENT, not taste. Two independent limits force it wide:
#   1. ADS-B report sparsity. The median gap between an aircraft's last airborne
#      state vector and its first on-ground one is 22 s in this capture, so the
#      transition instant is only ever known to about +/-11 s from machine truth.
#   2. PTZ acquisition. Hand-pinning five operations against the frames showed the
#      visible touchdown/liftoff leads the raw ADS-B-derived time by 10-35 s; the
#      stored times are bias-corrected by 12 s, leaving roughly +/-15 s of scatter.
# 45 s covers both with margin. It is deliberately NOT tight: this task's difficulty
# lives in pairing a heard callsign to a seen aircraft across two unsynchronised
# files, not in sub-second frame-picking on 2 Mbps night footage.
TOL = 45

VALID_OPERATIONS = {"landing", "takeoff"}
VALID_TYPES = {
    "A220", "A320-family", "A330", "A340", "A350", "A380",
    "B737-family", "B747", "B757", "B767", "B777", "B787",
    "regional-jet", "other",
}

# Built from three sources that must agree:
#   callsign      -- OpenSky live state-vector capture run against the runway complex
#                    throughout the recording, joined icao24 -> registration -> the
#                    on-screen tracking panel (machine truth). The join is on airframe
#                    identity, never on "who was landing around then".
#   operation     -- debounced on_ground transition in that same capture.
#   aircraft_type -- registration -> type from the tracking panel, collapsed to the
#                    closed family vocabulary above.
#   video_time    -- ADS-B transition midpoint, bias-corrected; see TOL above.
# Times are on the shipped runway.mp4 timeline (the first 105 s of the raw capture,
# which shows the recording window being opened, are cut and are not in the file).
GROUND_TRUTH = [
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

# Real operations in the capture that the camera was NOT verifiably pointed at.
# Matched loosely (callsign + operation, generous window) purely to excuse them.
DONT_CARE = [
    {"t": 55, "operation": "landing", "callsign": "SWA5126"},
    {"t": 73, "operation": "landing", "callsign": "SWA5126"},
    {"t": 193, "operation": "takeoff", "callsign": "N353FS"},
    {"t": 243, "operation": "takeoff", "callsign": "N708SH"},
    {"t": 299, "operation": "takeoff", "callsign": "N407SL"},
    {"t": 308, "operation": "takeoff", "callsign": "N407SL"},
    {"t": 453, "operation": "landing", "callsign": "SWA1195"},
    {"t": 658, "operation": "takeoff", "callsign": "SWA208"},
    {"t": 817, "operation": "takeoff", "callsign": "N856MH"},
    {"t": 917, "operation": "landing", "callsign": "GCK18"},
    {"t": 967, "operation": "landing", "callsign": "SWA660"},
    {"t": 1025, "operation": "landing", "callsign": "N350FS"},
    {"t": 1030, "operation": "landing", "callsign": "SWA4056"},
    {"t": 1039, "operation": "takeoff", "callsign": "UAL2282"},
    {"t": 1050, "operation": "takeoff", "callsign": "SWA2163"},
    {"t": 1116, "operation": "takeoff", "callsign": "FFT2333"},
    {"t": 1160, "operation": "takeoff", "callsign": "FFT2333"},
    {"t": 1161, "operation": "landing", "callsign": "SWA354"},
    {"t": 1175, "operation": "takeoff", "callsign": "N350FS"},
    {"t": 1175, "operation": "landing", "callsign": "N885MH"},
    {"t": 1215, "operation": "landing", "callsign": "N857MH"},
    {"t": 1340, "operation": "landing", "callsign": "DAL2202"},
    {"t": 1412, "operation": "takeoff", "callsign": "SWA4587"},
    {"t": 1499, "operation": "landing", "callsign": "SWA1128"},
    {"t": 1522, "operation": "landing", "callsign": "SWA1128"},
    {"t": 1589, "operation": "landing", "callsign": "SWA2844"},
    {"t": 1737, "operation": "landing", "callsign": "AAY9206"},
    {"t": 1768, "operation": "landing", "callsign": "AAY9206"},
    {"t": 1813, "operation": "landing", "callsign": "N708SH"},
    {"t": 1899, "operation": "takeoff", "callsign": "SWA2281"},
    {"t": 1963, "operation": "landing", "callsign": "N350FS"},
    {"t": 1968, "operation": "landing", "callsign": "MXY350"},
    {"t": 1998, "operation": "takeoff", "callsign": "SWA1590"},
    {"t": 2055, "operation": "landing", "callsign": "SWA3003"},
    {"t": 2154, "operation": "landing", "callsign": "N353FS"},
    {"t": 2211, "operation": "landing", "callsign": "SWA330"},
    {"t": 2239, "operation": "takeoff", "callsign": "N350FS"},
    {"t": 2244, "operation": "takeoff", "callsign": "N857MH"},
    {"t": 2248, "operation": "takeoff", "callsign": "SWA2177"},
    {"t": 2254, "operation": "takeoff", "callsign": "N885MH"},
    {"t": 2289, "operation": "takeoff", "callsign": "N353FS"},
    {"t": 2298, "operation": "landing", "callsign": "UAL2242"},
    {"t": 2354, "operation": "takeoff", "callsign": "N708SH"},
    {"t": 2447, "operation": "landing", "callsign": "SWA2256"},
    {"t": 2507, "operation": "takeoff", "callsign": "N882WR"},
    {"t": 2539, "operation": "takeoff", "callsign": "N882WR"},
    {"t": 2676, "operation": "landing", "callsign": "UAL1764"},
    {"t": 2788, "operation": "landing", "callsign": "N353FS"},
    {"t": 2865, "operation": "landing", "callsign": "SWA1323"},
    {"t": 2880, "operation": "landing", "callsign": "SWA1323"},
    {"t": 2889, "operation": "takeoff", "callsign": "FFT1896"},
    {"t": 2969, "operation": "landing", "callsign": "UAL1360"},
    {"t": 3020, "operation": "landing", "callsign": "SWA210"},
    {"t": 3083, "operation": "takeoff", "callsign": "SWA354"},
    {"t": 3085, "operation": "landing", "callsign": "AAL2855"},
    {"t": 3086, "operation": "takeoff", "callsign": "SWA4268"},
    {"t": 3090, "operation": "takeoff", "callsign": "N881MH"},
    {"t": 3141, "operation": "takeoff", "callsign": "KLM636"},
    {"t": 3208, "operation": "takeoff", "callsign": "SWA2289"},
    {"t": 3445, "operation": "landing", "callsign": "N886MH"},
    {"t": 3527, "operation": "landing", "callsign": "FFT4242"},
    {"t": 3536, "operation": "landing", "callsign": "N854MH"},
    {"t": 3541, "operation": "landing", "callsign": "FFT4242"},
    {"t": 3735, "operation": "takeoff", "callsign": "OCN12"},
    {"t": 3769, "operation": "takeoff", "callsign": "SWA4339"},
    {"t": 3796, "operation": "landing", "callsign": "SWA1324"},
    {"t": 3796, "operation": "landing", "callsign": "SWA2288"},
    {"t": 3863, "operation": "takeoff", "callsign": "SWA199"},
    {"t": 3903, "operation": "landing", "callsign": "ROU1709"},
    {"t": 3956, "operation": "landing", "callsign": "N708SH"},
    {"t": 3971, "operation": "landing", "callsign": "N708SH"},
    {"t": 4051, "operation": "landing", "callsign": "ROU1705"},
    {"t": 4079, "operation": "takeoff", "callsign": "SWA4340"},
    {"t": 4102, "operation": "landing", "callsign": "N350FS"},
    {"t": 4184, "operation": "takeoff", "callsign": "SWA660"},
    {"t": 4225, "operation": "landing", "callsign": "N856MH"},
    {"t": 4260, "operation": "takeoff", "callsign": "SWA2256"},
    {"t": 4268, "operation": "takeoff", "callsign": "N1560V"},
    {"t": 4275, "operation": "landing", "callsign": "AAL1797"},
    {"t": 4308, "operation": "takeoff", "callsign": "N350FS"},
    {"t": 4321, "operation": "takeoff", "callsign": "N708SH"},
    {"t": 4455, "operation": "takeoff", "callsign": "SWA4397"},
    {"t": 4699, "operation": "landing", "callsign": "POE655"},
    {"t": 4703, "operation": "takeoff", "callsign": "N854MH"},
    {"t": 4718, "operation": "takeoff", "callsign": "N856MH"},
    {"t": 4824, "operation": "landing", "callsign": "LN481HC"},
    {"t": 4828, "operation": "takeoff", "callsign": "N886MH"},
    {"t": 4832, "operation": "landing", "callsign": "CMP456"},
    {"t": 4869, "operation": "landing", "callsign": "N708SH"},
    {"t": 4999, "operation": "landing", "callsign": "JSX108"},
    {"t": 5051, "operation": "takeoff", "callsign": "SWA2371"},
    {"t": 5124, "operation": "landing", "callsign": "DAL916"},
    {"t": 5247, "operation": "takeoff", "callsign": "N708SH"},
    {"t": 5297, "operation": "landing", "callsign": "N856MH"},
    {"t": 5334, "operation": "landing", "callsign": "N854MH"},
    {"t": 5369, "operation": "landing", "callsign": "N886MH"},
    {"t": 5429, "operation": "landing", "callsign": "WJA1092"},
    {"t": 5449, "operation": "takeoff", "callsign": "SWA992"},
    {"t": 5562, "operation": "takeoff", "callsign": "FFT1876"},
    {"t": 5639, "operation": "landing", "callsign": "JBU607"},
    {"t": 5665, "operation": "landing", "callsign": "JBU607"},
    {"t": 5685, "operation": "takeoff", "callsign": "AAL1080"},
    {"t": 5777, "operation": "takeoff", "callsign": "SWA2230"},
    {"t": 5967, "operation": "landing", "callsign": "N919ML"},
    {"t": 6000, "operation": "landing", "callsign": "N919ML"},
    {"t": 6005, "operation": "landing", "callsign": "DAL568"},
    {"t": 6008, "operation": "landing", "callsign": "N350FS"},
    {"t": 6025, "operation": "takeoff", "callsign": "SWA596"},
    {"t": 6075, "operation": "landing", "callsign": "FFT1647"},
    {"t": 6141, "operation": "landing", "callsign": "AAY54"},
    {"t": 6177, "operation": "takeoff", "callsign": "N353FS"},
    {"t": 6185, "operation": "takeoff", "callsign": "N353FS"},
    {"t": 6220, "operation": "takeoff", "callsign": "SWA185"},
    {"t": 6230, "operation": "takeoff", "callsign": "SWA2179"},
    {"t": 6250, "operation": "takeoff", "callsign": "N350FS"},
    {"t": 6265, "operation": "takeoff", "callsign": "ASA613"},
    {"t": 6335, "operation": "takeoff", "callsign": "FFT4552"},
    {"t": 6516, "operation": "takeoff", "callsign": "N886MH"},
    {"t": 6596, "operation": "takeoff", "callsign": "N856MH"},
    {"t": 6606, "operation": "takeoff", "callsign": "N854MH"},
    {"t": 6726, "operation": "landing", "callsign": "N353FS"},
    {"t": 6829, "operation": "landing", "callsign": "FFT4113"},
    {"t": 6932, "operation": "landing", "callsign": "ASA704"},
    {"t": 6978, "operation": "landing", "callsign": "AAY1708"},
    {"t": 7041, "operation": "landing", "callsign": "N885MH"},
    {"t": 7052, "operation": "takeoff", "callsign": "SWA2214"},
    {"t": 7067, "operation": "landing", "callsign": "N886MH"},
    {"t": 7072, "operation": "takeoff", "callsign": "N353FS"},
    {"t": 7104, "operation": "landing", "callsign": "N857MH"},
    {"t": 7127, "operation": "takeoff", "callsign": "BAW4LV"},
    {"t": 7177, "operation": "landing", "callsign": "JBU777"},
    {"t": 7194, "operation": "takeoff", "callsign": "UAL1681"},
    {"t": 7272, "operation": "takeoff", "callsign": "SWA2362"},
    {"t": 7433, "operation": "landing", "callsign": "AAY1633"},
    {"t": 7447, "operation": "landing", "callsign": "AAY1633"},
    {"t": 7513, "operation": "landing", "callsign": "UAL1800"},
    {"t": 7575, "operation": "takeoff", "callsign": "SWA287"},
    {"t": 7737, "operation": "landing", "callsign": "AAL2106"},
    {"t": 7753, "operation": "landing", "callsign": "AAL2106"},
    {"t": 7873, "operation": "landing", "callsign": "N353FS"},
    {"t": 7898, "operation": "takeoff", "callsign": "N353FS"},
    {"t": 7923, "operation": "takeoff", "callsign": "N885MH"},
    {"t": 8053, "operation": "takeoff", "callsign": "DAL2794"},
    {"t": 8153, "operation": "takeoff", "callsign": "AAL1454"},
    {"t": 8157, "operation": "landing", "callsign": "FFT1821"},
    {"t": 8168, "operation": "landing", "callsign": "FFT1821"},
    {"t": 8188, "operation": "takeoff", "callsign": "AAL1454"},
    {"t": 8381, "operation": "landing", "callsign": "N443PR"},
    {"t": 8409, "operation": "landing", "callsign": "N443PR"},
    {"t": 8424, "operation": "landing", "callsign": "N353FS"},
    {"t": 8456, "operation": "takeoff", "callsign": "N857MH"},
    {"t": 8484, "operation": "takeoff", "callsign": "N886MH"},
    {"t": 8705, "operation": "landing", "callsign": "FFT1326"},
    {"t": 8944, "operation": "landing", "callsign": "N881MH"},
    {"t": 8974, "operation": "landing", "callsign": "N854MH"},
    {"t": 9015, "operation": "landing", "callsign": "N857MH"},
    {"t": 9057, "operation": "landing", "callsign": "AAY50"},
    {"t": 9063, "operation": "landing", "callsign": "SWA3119"},
    {"t": 9070, "operation": "landing", "callsign": "AAY50"},
    {"t": 9159, "operation": "landing", "callsign": "SWA1566"},
    {"t": 9171, "operation": "landing", "callsign": "SWA976"},

]
DONT_CARE_TOL = 120


def norm_callsign(s):
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


def video_time_secs(v):
    v = str(v).strip()
    try:
        parts = [int(p) for p in v.split(":")]
        while len(parts) < 3:
            parts.insert(0, 0)
        h, m, s = parts[-3:]
        return h * 3600 + m * 60 + s
    except (ValueError, AttributeError):
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", required=True, type=Path)
    ap.add_argument("--reward-json", required=True, type=Path)
    ap.add_argument("--reward-txt", required=True, type=Path)
    args = ap.parse_args()

    reason = "ok"
    preds = []
    try:
        sol = json.loads(args.solution.read_text())
        preds = sol.get("operations", [])
        if not isinstance(preds, list):
            raise ValueError("operations is not a list")
    except Exception as exc:  # noqa: BLE001 - malformed output scores 0
        reason, preds = f"unreadable solution.json: {exc}", []

    used = [False] * len(GROUND_TRUTH)
    tp = 0
    excused = 0
    scored_preds = 0
    for pr in preds:
        if not isinstance(pr, dict):
            continue
        pt = video_time_secs(pr.get("video_time"))
        if pt is None:
            continue
        pr_op = str(pr.get("operation", "")).strip().lower()
        pr_type = str(pr.get("aircraft_type", "")).strip()
        pr_call = norm_callsign(pr.get("callsign", ""))

        hit = False
        for i, gt in enumerate(GROUND_TRUTH):
            if used[i]:
                continue
            gt_t = video_time_secs(gt["video_time"])
            if (pr_op == gt["operation"]
                    and pr_type == gt["aircraft_type"]
                    and pr_call == norm_callsign(gt["callsign"])
                    and gt_t is not None
                    and abs(pt - gt_t) <= TOL):
                used[i] = True
                tp += 1
                hit = True
                break
        if hit:
            scored_preds += 1
            continue

        if any(pr_op == dc["operation"]
               and pr_call == norm_callsign(dc["callsign"])
               and abs(pt - dc["t"]) <= DONT_CARE_TOL
               for dc in DONT_CARE):
            excused += 1
            continue
        scored_preds += 1

    n_gt = len(GROUND_TRUTH)
    precision = tp / scored_preds if scored_preds else 0.0
    recall = tp / n_gt if n_gt else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    details = {
        "reason": reason,
        "n_ground_truth": n_gt,
        "n_predicted": len(preds),
        "n_scored_predictions": scored_preds,
        "n_excused_dont_care": excused,
        "true_positives": tp,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "video_time_tolerance_s": TOL,
    }
    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps({"reward": round(f1, 4), "details": details}, indent=2))
    args.reward_txt.write_text(f"{round(f1, 4)}\n")


if __name__ == "__main__":
    main()
