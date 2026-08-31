# Kickoff: refining the authentic Java Minecraft render

Read this first if you're picking up the **authentic (real Minecraft Java client) render** for the
`minecraft-gameplay-ledger-s1` task. It is the *showcase* renderer; the shipped/graded task uses the
headless first-person render, which is solid and independent of everything here.

## What it is
The same bot (`bot_play8.js`) that drives the headless path also plays on a **real Minecraft 1.20.4
client**, so cracks, hurt flashes, hand-swing, particles and lighting are the game's own. The client
joins as a second player ("Camera") and is kept on the bot's viewpoint. One command runs it all:

```
bash authentic_session.sh <OUTDIR> start,forest,build_village,combat_showcase,beach,desert,snowy,jungle,plains,savanna,badlands,mine
```
Output: `<OUTDIR>/authentic.mp4` + `<OUTDIR>/play.json` (the machine-exact ledger) + `play.json.crash.log`
(verbose decision log). Runs on the SSD only; needs Java 21 (`$HOME/jdk-21.0.11+10`), the 1.20.4 client
(`$WORK/mc-client-1204`), Paper server (`$WORK/p1-mc-server-1204`).

## Current state (2026-07-24)
Works end to end above ground; verified **by viewing frames** (do this — logs and colour metrics
cannot tell a frozen-but-valid frame from a following one; that mistake cost many renders):
- camera follows the bot at eye level across all biomes, the build, and combat;
- 300 events, all 8 biomes, all 4 structures (house / desert temple / well / tower), 6 hostile kills.

Latest uploaded sample (updated in place):
`https://huggingface.co/datasets/explcre/agenticvbench-understanding-materials/resolve/main/minecraft-gameplay-ledger-s1/authentic_java_natural.mp4`

Task proposal issue: **PhiloLabs/agentic-vbench#74** (headless v31 is the graded instance).

## The one open blemish
**The mine phase (last ~3 min) renders dark.** It is underground and the Camera is a *spectator*, which
does not receive the bot's night-vision effect, so the tunnel is near-black. Two clean fixes:
1. Drop `mine` from the authentic phase list (surface-only showcase). Simplest.
2. Light it: make the Camera a night-vision **creative** player instead of a spectator (spectators
   ignore potion effects), or fill the shaft with glowstone. Then keep `mine`.

## How the camera actually works (and the trap that wasted days)
`/spectate Builder Camera` **freezes**: it attaches the camera once and does NOT follow when the bot
teleports across the world — every render was a static spawn view. The working approach is **hard
follow**: the always-connected bot teleports the Camera onto itself every 350 ms and raises it to eye
level (`bot_play8.js`, gated by `P1_CAMERA_FOLLOW=1`, set in `authentic_session.sh`):
```
/tp Camera Builder        # copy position + exact facing (no yaw/pitch math)
/tp Camera ~ ~1.62 ~      # raise to eye level — feet level buries the camera in the floor (black frame)
```
Do **not** go back to `/spectate` for following.

## Hard-won gotchas (all fixed, do not reintroduce)
- **`sendCommandFeedback` must stay ON.** The bot reads `/locate biome` output to travel; turning it
  off (to stop a chat leak) silently made every biome trip miss. The leak is instead prevented by
  `chatVisibility:2` (Camera renders no chat) + Camera not being op + `logAdminCommands false`.
- **Camera is never op'd**, or Paper broadcasts `Builder issued server command: /setblock … oak_planks`
  to it and the answers leak onto the graded frame.
- **ops.json is written before the server starts** (`make_ops.py`), else Brigadier hides `/setblock`,
  `/summon`, `/locate` as "Unknown command".
- **World spawn has drifted ~38 000 blocks** over runs (each sets worldspawn to the bot's spot). Not
  fatal, but reset it to a fixed sane location for reproducibility if you touch the world.
- **Don't teleport far to "recover" a missed biome** — it lands in ungenerated chunks and guarantees
  a miss. `tpToBiome` uses a 12 s locate + one in-place retry.
- Verify camera state with `screen_state.py` (world / ui / flat) and by extracting real frames with
  ffmpeg + Read — never trust colour variance alone.

## Files
- `bot_play8.js` — the bot (both renderers; env: `MC_VERSION`, `MC_PORT`, `NO_VIEWER`, `P1_PHASES`,
  `P1_LAPS`, `P1_HOSTILES`, `P1_EXTRA_BUILDS`, `P1_CAMERA_FOLLOW`).
- `authentic_session.sh` — the full authentic pipeline with preflight asserts.
- `make_ops.py`, `probe_1204.js`, `screen_state.py`, `bands.py` — helpers.
- `AUTHENTIC_RENDER_ROUTES.md` — the long history of what was tried and why.
- `README.md` — the headless pipeline and fairness gates.
