# P1 — Minecraft gameplay ledger: generator

Programmatic generator for the `minecraft-gameplay-ledger-s1` task. It plays a scripted but
naturalistic Minecraft session, records the video, and emits a **machine-exact** event ledger as
ground truth: every scored label comes from the bot's own `rec()` call at the moment it acted, so the
ground truth is never annotated and cannot drift from the footage.

Because it is a program, one command yields a new episode with a different world seed, biome route,
material palette and ledger — the family scales to as many independent instances as there is compute
for, with no human labelling.

## Two renderers

| | headless (shipping) | authentic (real client) |
|---|---|---|
| renderer | `prismarine-viewer` (three.js) via Playwright/swiftshader | the **real Minecraft Java client** |
| version | Paper 1.16.5, port 25577 | Paper 1.20.4, port 25590 |
| composited | HUD, held item, block-crack, hit-flash | HUD only — a `/spectate` camera draws no hotbar |
| mob vocabulary | restricted: only 11 of 27 mobs render (`MOB_RENDER_AUDIT.md`) | unrestricted |
| entry point | `bot_play8.js` + `capture_mc.py` | `authentic_session.sh` |

Both drive the **same** `bot_play8.js`; only `MC_VERSION`, `MC_PORT` and `NO_VIEWER` differ. See
`AUTHENTIC_RENDER_ROUTES.md` for the authentic recipe and the three blockers it cost.

## Headless pipeline

1. Paper 1.16.5 on :25577, `online-mode=false`, `doTileDrops=false` — dropped items render as magenta
   boxes in prismarine-viewer.
2. `bot_play8.js <out.json> <GO> <DONE>` — waits for `GO`, then gathers in a forest, hunts with sword
   and bow, builds a cabin / watchtower / well, digs a staircase mine, and tours eight biomes. Writes the
   ledger to `out.json` and a verbose decision log to `out.json.crash.log`.
3. `capture_mc.py <outdir> <GO> <DONE> <max_s>` — records the viewer page, writes `GO`, waits for
   `DONE`.
4. `make_hud.py` + `composite_hud.py` — overlay a HUD built from the game's own GUI sprites
   (`gui/widgets.png`, `gui/icons.png`) at GUI scale 3, switching the held item per event.
5. `fx_overlay.py` — composite the real `destroy_stage_0..9` crack before each mine and a red
   hurt-flash at each kill, timed from the ledger.
6. `build_p1_gt_v11.py` — emit ground truth + oracle and run the anti-shortcut ablations.
7. `frame_audit.py` — objective check that the footage is informative: share of frames dominated by a
   single colour, split into `sky` and `one_block`.

## Fairness gates

The scored ledger must contain exactly what a viewer could have watched happen. Each gate below was
added after measuring a specific failure, and each prints a counter so a session can be audited from
its log without watching it.

- **Kills** count only if the mob was in range *and* in line of sight for ≥3 ticks of the fight (≥2
  for bow). A post-hoc geometry check was tried first and is invalid: animals flee, so where one died
  says nothing about where it was fought.
- **Placements** are framed dead-centre before they happen: the bot flies to a vantage at the block's
  own height, backs off along its outward normal, and aims within ~24° with clear line of sight (the
  viewer's vertical FOV is 75°, so a wider cone would put the block at the frame edge). A block that
  cannot be framed that way from any vantage is **skipped entirely — not placed and not recorded**
  (`finishDeferred()`), so the finished world and the ledger stay identical and every recorded
  placement is provably on-camera. Each mined block's break-crack is projected onto its screen position.
- **Build sites** must be flat and clear: no log or leaf anywhere in the footprint, ≥85% of columns
  within one block of centre height, spread ≤3. Otherwise the walls end up half-buried or screened by
  trees. If nothing nearby qualifies the ground is levelled and the trees felled — itself real
  gameplay, and it yields `mine` events.
- **Structure visibility** raycasts to the structure and checks the first solid block hit belongs to
  it. Probing a point a fixed 2.5 blocks in front of the centre was wrong: for a 7×7 house that point
  is *inside* the walls, so the house occluded its own test point and reported `ORBIT_SHOWN 0/6` for a
  building that was in fact perfectly framed.

## Authentic-render helpers

- `fetch_client.sh <dir> [version]` — build a self-contained offline client from Mojang's piston-meta
  manifests (jar + libraries + assets + LWJGL natives).
- `make_ops.py <server_dir> [names…]` — write `ops.json` from offline-mode UUIDs
  (`uuid3(md5, "OfflinePlayer:<name>")`). Required: without it every privileged command answers
  *"Unknown command"*, because Brigadier hides commands the caller may not run — indistinguishable
  from a removed command, and it cost one whole session.
- `probe_1204.js` — test each world primitive (locate syntax, summon, setblock, dig) against a live
  server. Run before any full session on a new version or server directory.
- `xtest_click.py`, `bands.py` — ctypes XTEST injection and blind screen fingerprinting. Unnecessary
  on 1.20.4 (`--quickPlayMultiplayer` auto-joins); kept for any client that must be clicked in.

## Notes

- The render is variable-FPS under software GL, so scoring is an **order-preserving LCS on
  `(action, target)` within a ±10 s time window** (recall-weighted F2 + a weapon score): the window
  makes the order real without depending on exact frame timing. `build_p1_gt_v11.py` maps each event's
  `t_ms` to a video time `t` via the capture OFFSET; `composite_hud.py` re-encodes to CFR 25 fps.
- Launch server, bot and capture as detached processes; the bot blocks on the `GO` file, so recording
  always starts before the first action.
