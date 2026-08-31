# UPDATE — the /spectate camera does NOT follow a teleporting bot (frozen render)

Verified by frame, not metric: in a full authentic render the frame at a house-build event and the
frame at the orbit are **pixel-identical** — the camera is frozen on the spawn-forest view the whole
session while the bot builds, mines and fights elsewhere. `/spectate Builder Camera` fixes the camera
at the bot's *initial* position and does not track subsequent moves/teleports in this headless
offline 1.20.4 setup. A persistent re-spectate follower did not help (and disconnected after ~3 s).
Colour-variance and screen_state checks all passed because a frozen frame is still a valid *world*
view — they cannot detect "frozen but valid", which is why this went unnoticed for many renders.

Consequence: the authentic route is NOT usable as a shipped video with the current far-teleporting
session. The graded task uses the headless first-person render, whose camera IS the bot and therefore
cannot desync (verified frame-by-frame). If the authentic route is revived, the camera-follow must be
solved first — candidates not yet tried to completion: `/tp Camera Builder` every tick (hard-follow
instead of /spectate), or restructuring the session to stay in a compact area (fabricated local biome
patches) so a spectator can keep up.

---

# Authentic Minecraft rendering — routes, evidence, and recommendation

The shipped task (v23) renders with **prismarine-viewer**, a headless JS world renderer, and
composites back the things it does not draw (HUD, held item, block-break crack, hit flash) from
the bot's own event log. That is honest and it works — but it is not the real game's output. This
note records what was actually tried for a genuinely authentic render, what the evidence says, and
which route is worth the effort.

## RESOLVED — Route A works on Minecraft 1.20.4 (no input injection needed)

The blocker was never rendering, and in the end it was not input injection either. Two facts, in
order:

1. **`--server`/`--port` genuinely do nothing in 1.16.5.** Auto-join arrived with **quickPlay in
   1.20**. Confirmed by string-dumping `Main.class`: 1.16.5 has only `server`/`port`, while 1.20.4
   has `quickPlayMultiplayer`, `quickPlaySingleplayer`, `quickPlayRealms`, `quickPlayPath`.
2. **1.20.2+ shows a first-launch accessibility onboarding screen that blocks quickPlay.** It is
   dismissed non-interactively by writing `onboardAccessibility:false` into `options.txt`. Before
   that fix the client sat on a four-button dialog; after it, the log shows
   `Connecting to 127.0.0.1, 25590`.

### Working recipe (verified end to end)

- **Client:** vanilla **1.20.4** via `fetch_client.sh <dir> 1.20.4` (712 MB: jar + libraries +
  3811 assets + natives). Asset index id is written to `asset_index.txt` — 1.20.4 uses `12`, not
  the version string.
- **Java:** 1.20.x needs **JDK 17+**; this box has only 8 and 11, so a Temurin **JDK 21** tarball
  is extracted into `$HOME` (no root required). Both client and Paper run on it.
- **Server:** Paper **1.20.4**, `online-mode=false`, on a separate port (25590) so it cannot
  collide with the 1.16.5 world.
- **`options.txt`:** `onboardAccessibility:false` — the actual unblock — plus `guiScale:3`,
  `renderDistance:8`.
- **Launch:** `--quickPlayMultiplayer 127.0.0.1:25590`, no menu interaction at all.
- **Camera control:** a mineflayer `Director` bot issues `/op Camera`, `/time set day`,
  `/weather clear`, `/gamemode spectator Camera` — all server-side, no client input.

Measured result: `Camera joined the game` **15 s** after launch, and the captured frame goes from a
flat loading screen (brightness 25, 5 distinct colours) to a **rendered world** (brightness 80,
std 29, 32 distinct colours) within 30 s of the Director setting daylight. Software GL is the only
cost.

### Third blocker: the bot was silently unprivileged (cost one whole session)

The first end-to-end run reached `SPECTATE_LOCKED` and recorded **0 events**. The bot log blamed
the world: `biome-miss forest`, `mob-miss cow/pig/sheep`, `PLAY_DONE 0`. The obvious hypothesis was
a version incompatibility — `/locatebiome` *was* replaced by `/locate biome` in 1.19 — but that was
only half the story, and on its own it would not explain the mob misses.

`probe_1204.js` was written to test each primitive separately against the live server instead of
reasoning about it, and it settled the question in 60 seconds:

| primitive | before `ops.json` | after |
|---|---|---|
| `/locatebiome minecraft:forest` | `Unknown command` | `Unknown command` (genuinely gone in 1.19+) |
| `/locate biome minecraft:forest` | **`Unknown command`** | `/tp @s 551 68 443` ✅ |
| `/summon` cow / pig / sheep / chicken | 1 found (a *natural* cow), 3 MISS | **4/4 found** ✅ |
| `/setblock` then `dig` | silently did nothing | `oak_log` placed, `DIG_OK` ✅ |

**Root cause: a fresh Paper server has `ops: []`, and Brigadier hides commands a player is not
permitted to run — so every privileged command comes back as "Unknown command", which is
indistinguishable from a removed command.** The 1.16.5 server had `Builder` in `ops.json` from
months of use; the new 1.20.4 server did not. `make_ops.py` now writes it before the server starts,
deriving the offline-mode UUID as `uuid3(md5, "OfflinePlayer:<name>")` (self-tested against the
known-good 1.16.5 entry), and `authentic_session.sh` asserts it as a preflight.

The version rename is real and also fixed: `locateCmd()`/`biomeId()` in `bot_play8.js` pick
`/locate biome` on ≥1.19 and map the 1.18 biome renames (`snowy_tundra`→`snowy_plains`, etc.).

**Lesson for the notes:** "Unknown command" from a Minecraft server means *unknown **to you***. Check
permission before version.

### Fourth and fifth blockers, both caught by looking at the picture

The first session that produced a real ledger (378 s, 75 events) was still **unusable**, and neither
fault showed up in any log line I was checking:

**(a) The whole recording was the death screen.** `Camera` joined at 03:27:35 and was only made a
spectator at 03:27:39 — four seconds in *survival*, at a default world spawn that `probe_1204.js`
had already measured as `SURFACE stone`, i.e. inside terrain. It suffocated. `/spectate` then failed
with `Attempt to teleport removed player Camera restricted`, because a dead player cannot be
teleported, and the client sat on the death screen for the entire capture.

My verification was the problem: the script printed `SPECTATE_LOCKED` unconditionally after issuing
the command, so a dead camera looked like a success. And the pixel check I ran — brightness 99, std
45, ~1129 distinct colours — **cannot** distinguish a live world from a world dimmed under a
translucent overlay, so it "confirmed" a rendered world that was not there. `bands.py` settles it
objectively: an in-world view has **0** UI button slabs, that frame had **3**, including a 594×54
slab (a stock menu button at GUI scale 3), with mean R=110 against G=84 — the death screen's red
wash.

Fixes: `/setworldspawn` onto the bot's own open dry ground; a watcher that is *already connected*
when the client joins so spectator mode is set within a tick; `/spectate` re-issued until the server
confirms it by the camera's position tracking the bot; and a `bands.py` precheck that aborts the run
unless `buttons=0`. The precheck was verified against the offending frame — it rejects it.

**(b) The footage leaked the answers in chat.** `Camera` was `/op`'d, and Paper broadcasts
`Builder issued server command: /setblock … minecraft:oak_planks` to **every op**. With
`chatVisibility:0` in `options.txt`, the exact ground-truth block names were being printed on screen
in the graded video.

Fixes: never op the Camera (it needs no permission — the Director executes `/spectate`),
`/gamerule sendCommandFeedback false`, `/gamerule logAdminCommands false`, and
`chatVisibility:2` in `options.txt`. All four are now asserted as preflights, and the run aborts if
`Camera` appears in `ops.json`.

This class of bug does not exist on the headless path, which renders no chat at all.

### Known limitation of the `/spectate` camera: no player HUD

`/spectate` puts the camera *inside* the bot's view, which is exactly the framing we want — but a
**spectator draws no hotbar, no hearts, no hunger and no XP bar**, because those belong to the
spectating player and a spectator has none. So the authentic route gives us real crack animations,
real hurt flashes, real hand swing, real particles and real sound, but the HUD still has to come
from `make_hud.py`/`composite_hud.py`. That is a smaller compositing surface than the headless path
(which composites HUD *and* effects), not zero.

If a fully-native HUD is wanted, the options are (a) run the Camera in survival and drive it with
XTEST mouse-look instead of `/spectate` — `xtest_click.py` already proves injection works, but the
camera then has to be steered rather than slaved to the bot; or (b) accept the spectator view and
keep the HUD composite. (b) is the honest and cheap choice, and the SPEC already discloses what is
composited.

### What is still to do on this route
- Measure the software-GL frame rate over a full session and decide whether it is watchable or
  whether a GPU path (VirtualGL/EGL) is worth adding.
- Redo the ledger/GT plumbing on 1.20.4 ids if this becomes the shipping renderer. On a real client
  every mob renders, which retires the 11-of-27 vocabulary restriction the headless path needs.

### The X11 injection work (kept, no longer on the critical path)
`xtest_click.py` remains useful for any client that *does* need clicking: XTEST is available
(v2.2), `focus` fixes the missing-window-manager problem under Xvfb (`XSetInputFocus` +
`XRaiseWindow`), and clicks provably register (pixel diff 44.6 after a click). `bands.py`
fingerprints a screen by locating button slabs, which is how the onboarding dialog was identified
blind. None of it is needed on 1.20.4.

## Route A history — real Java client + X11 input injection (1.16.5; superseded)

Launch the vanilla 1.16.5 client headless, have it join the Paper server the mineflayer bot is
already playing on, and lock its camera to the bot with `/spectate`.

Established by experiment:
- ✅ The real client **downloads and renders under software GL** (`LIBGL_ALWAYS_SOFTWARE=1
  GALLIUM_DRIVER=llvmpipe`): OpenGL initialises, the sound engine starts, all 10 texture atlases
  load, it reaches the main menu, no crash. `fetch_client.sh` builds the whole 392 MB tree
  (client jar + 41 libraries + 2 615 assets + LWJGL/GLFW natives) from Mojang's manifests.
- ✅ **The bot logic is reused unchanged** — only the renderer differs.
- ✅ **Spectator-follow needs no client mod**: the server issues `/gamemode spectator Camera`
  then `/spectate Builder Camera`.
- ❌ **`--server`/`--port` do not auto-connect in 1.16.5.** The flags parse but nothing happens —
  no connection attempt, no exception, the client idles at the menu. Auto-join arrived with
  quickPlay in 1.20. This cost two SLURM attempts before it was pinned down; an earlier guess
  that the client was merely CPU-starved was **wrong** (a dedicated 32-core allocation stalled at
  exactly the same point).
- ⚠️ So the client must be *clicked* in. `xtest_click.py` does that with ctypes only (no xdotool,
  no python-xlib): XTEST is present (v2.2) and synthetic motion, clicks and typing are accepted.
  Xvfb has **no window manager**, so nothing assigns input focus — `focus` sets it explicitly
  (`XSetInputFocus` + `XRaiseWindow`). With focus set, a click **does** change the screen (pixel
  diff 44.6, unambiguous), so injection works end to end.
- ❌ Remaining gap: the menu layout does not match the assumed coordinates. A frame grab finds
  only **two** UI bands (y≈350 and y≈602, ~600×48 px) where a scale-3 main menu should show
  several 600×60 buttons, so the clicks land on the wrong control. Fixing this blind means
  identifying each screen from its pixels and building a small state machine — feasible, but
  fiddly, and it is *incidental* work: it is menu automation, not rendering.

## Route B — MineRL / MCP-Reborn (recommended if authenticity is the goal)

**MineRL embeds the real Minecraft client and exposes a programmatic `step(action)` API, launching
directly into a world.** There is no menu, so Route A's entire remaining problem disappears.

- `minerl` on PyPI stops at **0.4.4** (MC 1.11, Malmo). The VPT-compatible **1.0.x / MCP-Reborn**
  line (MC **1.16.5**) is GitHub-install only and wants **JDK 8** (this box has 11) plus a Gradle
  build — multi-GB, multi-hour, non-trivial failure risk.
- Gives authentic rendering *and* scripted control, so the ledger stays as dense and as
  deliberately diverse as the current one.

## Route C — pretrained text-conditioned agents (STEVE-1 / VPT / Voyager)

- **STEVE-1** is the "text prompt → Minecraft behaviour" model (instruction-tuned VPT via
  MineCLIP). Runs on the Route-B env. Would look the most human.
- **VPT** is behaviour-cloned from human video but is not text-conditioned.
- **Voyager** drives **mineflayer** — the same library as our bot — so it changes how actions are
  *chosen*, not how they are *rendered*. It offers no authenticity benefit here.

**The trade-off to weigh before choosing C:** a learned policy buys realism at the cost of
control. The scripted bot guarantees dense, diverse coverage (237 events, 44 target types, all
seven biomes, three structures, sword *and* bow) with ground truth taken straight from its own
`rec()` calls. STEVE-1 does what it does — it may never build a house or visit six biomes, and the
ground truth would have to be reconstructed from environment state (inventory deltas, entity
deaths). For a benchmark that needs dense, verifiable labels, that is a real regression even
though the footage would look better. Policy input is also 640×360, below the ≥720p the family
wants.

## Recommendation

1. **Keep v23 as a shipped outcome.** It is validated (oracle 1.0), honest about what is
   composited, and it is the only route that currently delivers a dense labelled ledger.
2. If authenticity is worth a multi-hour build, take **Route B** (MineRL 1.0 + our scripted
   action plan) — authentic pixels *and* retained control.
3. Treat **Route C** as a separate research artifact, not a benchmark generator, unless the
   ground-truth-from-env-state plumbing is built and its coverage measured.
4. Route A is ~90% done and cheap to finish if someone can *see* the screen; it is parked rather
   than abandoned, and the tooling (`fetch_client.sh`, `xtest_click.py`,
   `authentic_render.sbatch`) is kept.

## Files

- `fetch_client.sh` — build a self-contained offline 1.16.5 client from Mojang manifests.
- `xtest_click.py` — ctypes XTEST injection: `probe`, `windows`, `focus`, `move`, `click`, `type`, `key`.
- `probe_1204.js` — isolates each world primitive (locate syntax, summon, setblock, dig) against a
  live server. Run this before any full session on a new version or a new server directory.
- `make_ops.py` — writes `ops.json` with offline-mode UUIDs so the bots are op'd before first join.
- `authentic_session.sh` — the full pipeline: preflight, Xvfb, Paper, bot, real client via
  quickPlay, Director `/spectate`, `x11grab`.
- `authentic_render.sbatch` — CPU-only SLURM job (a GPU would sit idle: GLFW goes through GLX and
  Xvfb offers only software GLX) that starts server + bot + client + capture with fail-fast guards.
