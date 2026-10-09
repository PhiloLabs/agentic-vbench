# How the recording was made

A scripted camera rig inside a Luanti 5.x server running VoxeLibre, captured
off an Xvfb display with software rendering. Nothing is hand-authored: the
world comes from mapgen v7 at `fixed_map_seed = 7`, the rig picks its own
centre and route, and the event log it writes is the ground truth.

| file | what it is |
|---|---|
| `avbcam_init.lua` | the rig mod. Walk, view cone, block palette and its drifting shares, lifetimes, HUD suppression, weather hold, event and camera-pose logging. |
| `h200_run2.sh` | the capture: reset the world, start Xvfb, server and client, start ffmpeg, drop the GO file the rig waits on, stop everything, report. |
| `h200_server.conf`, `h200_client.conf` | the settings that matter, notably `fixed_map_seed = 7`, `avb_centre = 0,0`, `node_highlighting = none` and `selectionbox_width = 0` so the client draws no wireframe around the block under the crosshair. |
| `rig_events.tsv` | the raw log this recording produced. Columns: time, action, node name, position, extra, camera pose. |
| `gt6_fixed.py` | replays that log forward into the census the verifier grades against. |
| `make_gt3.py` | the log reader and node-name labelling that `gt6_fixed.py` imports. |
| `judge6.py` | the six-type vocabulary and scorer that `controls6b.py` imports. |
| `controls6b.py` | every attack in `calibration/scores.md`. |
| `project.py` | projects each logged event onto its own frame from the recorded camera pose, which is how "was it on screen" was answered. |

The calibration harness, which is how every agent in `calibration/scores.md` reached the task only
through the built image:

| file | what it is |
|---|---|
| `container_mcp.py` | an MCP server with two tools, `exec` (a command inside the container) and `fetch` (copy one file out to look at it). Used by Codex and Claude Code. |
| `run_arm.sh`, `run_claude.sh` | the runners for those two: start the frozen `--network none` container, lock the truth directories, run the agent, copy the answer out. |
| `bridge_daemon.py`, `task_bridge_client.sh` | the file bridge Antigravity used instead, because its own sandbox denies the docker socket: the agent writes a command into a file and reads the result back, and only this daemon talks to docker. |
| `up.sh`, `PROMPT_container.md` | start the container by hand; the task statement with the two tools described. |

## Reproducing

    AVB_LUANTI_ROOT=/path/to/luanti-build bash h200_run2.sh 1800   # capture, needs an x11grab ffmpeg
    python3 gt6_fixed.py rig_events.tsv 4.13 write                 # gt_v6_1800.json == steps/solve/tests/census_truth.json
    python3 project.py rig_events.tsv unused 4.13                  # on-screen statistics
    python3 controls6b.py rig_events.tsv 4.13                      # every attack in calibration/scores.md

Everything below the capture runs from this directory with no other setup, and the replayed census
matches the shipped truth in all 180 cells.

Nothing here carries a machine-specific path. The scripts read these instead:

| variable | used by | default |
|---|---|---|
| `AVB_LUANTI_ROOT` | `h200_run2.sh` (required), and where the Python scripts look for their modules | this directory |
| `FFMPEG`, `FFPROBE` | `project.py`, `make_gt3.py` | `ffmpeg`, `ffprobe` on `PATH` |
| `AVB_LOCK_DIRS` | `run_arm.sh`, `run_claude.sh` (required, no default, so a calibration cannot run unlocked) | none |
| `AVB_CALIB_ROOT` | the runners, where run directories go | `./avb_calib` |
| `AVB_IMAGE`, `AVB_CT` | the runners | `avb-standing-census:v6`, `avb_task` |

The clock offset is `go.epoch - ffmpeg_start.epoch` plus up to one 0.25 s poll
before the rig notices the GO file. `SPEC.md` records the three independent
ways that offset was checked.

## Known imperfections

Twelve of 863 placements fall just below the bottom edge of the frame at the
moment they happen, and come into view on a later pass. The rig's three
full-screen sync flashes, which earlier captures used to align the clock,
rendered only once in this take; the offset comes from the capture script's
own timestamps instead and is corroborated as described in `SPEC.md`.
