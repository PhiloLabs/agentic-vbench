// P1 v11: natural first-person Minecraft session for the video-ledger task.
// Fixes over v9/v10: (a) every teleport lands on DRY LAND — v10 kept landing at ocean
// level, so translucent water washed the whole frame blue; (b) the camera never idles on
// empty sky (a survey pan looks slightly down and around instead); (c) mobs are summoned
// out at ~9 blocks and the player WALKS to them instead of popping in at arm's length;
// (d) ores are embedded in the mine walls BEFORE the descent, so nothing appears from
// nowhere on camera; (e) more content so the session runs >=10 min.
// GT = ordered (action, target[, tool]) triples from mineflayer events and the bot's own
// /setblock build — machine truth, no annotation.
const fs = require('fs');
const mineflayer = require('mineflayer');
const { mineflayer: mineflayerViewer } = require('prismarine-viewer');
const { pathfinder, Movements, goals } = require('mineflayer-pathfinder');
const { GoalNear } = goals;
const Vec3 = require('vec3').Vec3;

const OUT = process.argv[2], GO = process.argv[3], DONE = process.argv[4];
const CRASH = OUT + '.crash.log';
const log = m => { try { fs.appendFileSync(CRASH, m + '\n'); } catch (_) {} };
process.on('uncaughtException', e => log('UNCAUGHT ' + (e && e.stack || e)));
process.on('unhandledRejection', e => log('REJECT ' + (e && e.stack || e)));

// Version/port are env-configurable so the same session logic drives both renderers: the headless
// prismarine-viewer path (1.16.5 on 25577) and the authentic real-client path (1.20.4 on 25590).
const MC_VERSION = process.env.MC_VERSION || '1.16.5';
const MC_PORT = parseInt(process.env.MC_PORT || '25577', 10);
const USE_VIEWER = process.env.NO_VIEWER !== '1';
// The real Java client (authentic path) renders EVERY mob, so hostiles are fair there.
// The headless prismarine-viewer draws only 11 of 27 (MOB_RENDER_AUDIT.md), so this stays
// off by default and is enabled per-render via P1_HOSTILES=1 on the authentic path.
const HOSTILES = process.env.P1_HOSTILES === '1';
const EXTRA_BUILDS = process.env.P1_EXTRA_BUILDS === '1';   // desert temple etc. (authentic path)
const bot = mineflayer.createBot({ host:'localhost', port:MC_PORT, username:'Builder', version:MC_VERSION, auth:'offline' });
bot.loadPlugin(pathfinder);
bot.on('error', e => log('BOT_ERR ' + e.message));
bot.on('kicked', r => log('KICKED ' + JSON.stringify(r)));
bot.on('end', r => log('END ' + r));
const sleep = ms => new Promise(r => setTimeout(r, ms));

const events = []; const held = []; let idx = 0; let T0 = 0;
const since = () => T0 ? (Date.now() - T0) : 0;
function flush() {
  fs.writeFileSync(OUT, JSON.stringify({ n_events: events.length, events, held }, null, 2));
}
const AIR_LIKE = new Set(['air', 'cave_air', 'void_air']);
function rec(action, target, tool, viz) {
  // Air is not a nameable block: a mine that resolves to air/cave_air (e.g. the shaft cut an
  // existing cave pocket) is a spurious event the viewer sees nothing of — never record it.
  if (action === 'mine' && AIR_LIKE.has(target)) { log('EV-skip mine ' + target + ' (air, not a block)'); return; }
  const e = { i: idx++, action, target, t_ms: since() }; if (tool) e.tool = tool;
  if (viz) e.viz = viz;   // camera pose so the FX compositor can project the effect onto the block
  events.push(e); flush();
  log('EV ' + action + ' ' + target + (tool ? (' [' + tool + ']') : '') + ' @' + since());
}
// Camera pose + target-block centre at the instant an action is recorded. The FX compositor uses it
// to project the block to its exact screen position, so the break-crack sits ON the mined block
// rather than at a fixed screen point. Attached only to events that composite an effect (mines).
function vizOf(cx, cy, cz) {
  const p = bot.entity.position;
  return { bx: cx, by: cy, bz: cz, ex: p.x, ey: p.y + 1.62, ez: p.z,
           yaw: bot.entity.yaw, pitch: bot.entity.pitch };
}
// Timeline of what the player is holding, so the composited HUD highlights the real slot.
function recHeld(item) {
  if (held.length && held[held.length-1].item === item) return;
  held.push({ item, t_ms: since() }); flush();
}

const cat = {
  wood: new Set(['spruce_log','oak_log','birch_log','jungle_log','acacia_log','dark_oak_log']),
  leaves: new Set(['spruce_leaves','oak_leaves','birch_leaves']),
  grass: new Set(['grass_block']),
  sand: new Set(['sand']), sandstone: new Set(['sandstone']), cactus: new Set(['cactus']),
  snow: new Set(['snow_block','snow']), ice: new Set(['ice','packed_ice']),
  redsand: new Set(['red_sand']),
  terracotta: new Set(['terracotta','orange_terracotta','white_terracotta','red_terracotta','yellow_terracotta']),
};
// blocks that make an acceptable dry standing surface (no water/ice-over-ocean wash)
const DRY = new Set(['grass_block','dirt','coarse_dirt','podzol','sand','red_sand','sandstone',
  'red_sandstone','stone','cobblestone','gravel','snow','snow_block','grass_path','dirt_path','terracotta',
  'orange_terracotta','white_terracotta','red_terracotta','yellow_terracotta','brown_terracotta',
  'light_gray_terracotta','clay','moss_block','andesite','granite','diorite']);
const WET = new Set(['water','flowing_water','kelp','seagrass','tall_seagrass','ice','packed_ice','blue_ice','lava']);

bot.once('spawn', async () => {
  const sp = bot.entity.position;
  log('SPAWNED ' + [Math.floor(sp.x),Math.floor(sp.y),Math.floor(sp.z)]);
  // The authentic path renders in a real client, so the JS viewer is skipped there.
  if (USE_VIEWER) mineflayerViewer(bot, { port:3007, firstPerson:true, viewDistance:8 });
  bot.chat('/gamemode creative Builder');
  // Surface immediately, before waiting for GO. On the authentic path a real client joins and
  // spectates this bot while it is still parked at its spawn point; if that spawn is underground the
  // camera stares at solid rock, and any "is the world rendering?" check cannot tell that apart from
  // a loading screen. Landing dry up front makes the first frame a real view.
  setTimeout(async () => { try { await landDry(bot.entity.position.x, bot.entity.position.z); }
                           catch (_) {} }, 2500);
  // HARD camera-follow (authentic path). /spectate attaches the camera once and then freezes when
  // this bot teleports across the world — verified by frame: the whole render was a static spawn
  // view. Instead, the always-connected bot itself teleports the Camera onto its own position and
  // facing a few times a second, so the camera tracks the action even across long jumps. The Camera
  // renders no chat (chatVisibility:2), so the /tp feedback never appears on the graded frame.
  if (process.env.P1_CAMERA_FOLLOW === '1') {
    setInterval(() => { try {
      bot.chat('/tp Camera Builder');       // copy the bot's position + exact facing (no angle math)
      bot.chat('/tp Camera ~ ~1.62 ~');     // raise to EYE level — feet-level buries the camera in the floor
    } catch (_) {} }, 350);
  }
  bot.chat('/gamerule doDaylightCycle false'); bot.chat('/time set day'); bot.chat('/weather clear');
  bot.chat('/gamerule mobGriefing false'); bot.chat('/gamerule doMobSpawning false'); bot.chat('/gamerule doTileDrops false');
  for (const it of ['diamond_pickaxe','diamond_axe','diamond_shovel','diamond_sword','bow','arrow 64'])
    bot.chat('/give Builder minecraft:' + it);
  for (const b of ['cobblestone 64','stone_bricks 64','andesite 64','diorite 64','granite 64','stone 64','oak_planks 64','spruce_planks 64','birch_planks 64','jungle_planks 64','glass 64','oak_door 8','torch 32','oak_stairs 64','oak_fence 32','oak_log 32'])
    bot.chat('/give Builder minecraft:' + b);
  for (const ef of ['fire_resistance 99999 3','resistance 99999 4','night_vision 99999 1'])
    bot.chat('/effect give Builder minecraft:' + ef + ' true');
  await sleep(2000);

  const moves = new Movements(bot); moves.canDig = true; moves.allowParkour = true; bot.pathfinder.setMovements(moves);
  const gotoNear = async (pos, range=2, timeout=12000) => {
    const r = await Promise.race([ bot.pathfinder.goto(new GoalNear(pos.x, pos.y, pos.z, range)).catch(e=>log('goto '+e.message)), sleep(timeout).then(()=>'t') ]);
    if (r==='t') { try{bot.pathfinder.setGoal(null);}catch(_){} } try{bot.clearControlStates();}catch(_){} await sleep(150);
  };
  async function equip(name){ try{ const it=bot.inventory.items().find(i=>i.name===name); if(it) await bot.equip(it,'hand'); recHeld(name); }catch(e){log('equip '+e.message);} }

  const TAN_MIN_DOWN = 0.18;   // ~10 degrees below the horizon — keeps the ground, not sky, in frame
  // Single eased turn primitive. Every camera aim in the session routes through here, so nothing
  // snaps: a hard `bot.lookAt(v, true)` jump was the main thing that read as "not a real player".
  // The turn accelerates and settles with a cosine ease-in-out, and the step count scales with the
  // angular distance — a small correction is a quick nudge, a full turn is a slow sweep. Fully
  // deterministic (no wall-clock, fixed steps for a given angle), so it never touches the ledger.
  async function turnTo(yaw, pitch, dur=520) {
    const y0 = bot.entity.yaw, p0 = bot.entity.pitch;
    let dyaw = yaw - y0; while (dyaw > Math.PI) dyaw -= 2*Math.PI; while (dyaw < -Math.PI) dyaw += 2*Math.PI;
    const dpitch = pitch - p0;
    const ang = Math.hypot(dyaw, dpitch);
    if (ang < 0.02) { try { await bot.look(yaw, pitch, true); } catch(_){} return; }
    const steps = Math.max(3, Math.min(30, Math.round(ang / 0.08)));
    for (let k = 1; k <= steps; k++) {
      const e = 0.5 - 0.5*Math.cos(Math.PI * k/steps);           // ease-in-out 0..1
      try { await bot.look(y0 + dyaw*e, p0 + dpitch*e, true); } catch(_){}
      await sleep(Math.max(16, Math.round(dur/steps)));
    }
  }
  // Yaw/pitch that aim the eye at `pos`, optionally clamped below the horizon so the frame keeps
  // the ground rather than pitching up into empty sky.
  function aimFor(pos, dy=0.4, clampDown=true) {
    const b = bot.entity.position, eye = b.y + 1.62;
    const p = pos.offset(0, dy, 0);
    const hd = Math.max(1.0, Math.hypot(p.x - b.x, p.z - b.z));
    const ty = clampDown ? Math.min(p.y, eye - TAN_MIN_DOWN*hd) : p.y;
    return { yaw: Math.atan2(-(p.x - b.x), (p.z - b.z)), pitch: Math.atan2(ty - eye, hd) };
  }
  // Look slightly downward at the horizon in a given yaw — keeps the ground in frame.
  async function lookYaw(yaw) {
    const p = bot.entity.position;
    const ax = p.x + Math.sin(-yaw)*6, az = p.z + Math.cos(-yaw)*6;
    const s = surfaceOf(Math.floor(ax), Math.floor(az));           // terrain height ahead
    const eye = p.y + 1.62;
    const ty = Math.min(s ? s.position.y + 1.0 : eye - 1.2, eye - 0.18*6);
    const { yaw: wy, pitch: wp } = aimFor(new Vec3(ax, ty, az), 0, false);
    await turnTo(wy, wp, 620);
  }
  // A player-like survey pan: slow rotation with the ground in frame. Also paces the video.
  async function survey(steps=6, ms=700) {
    steps = Math.min(steps, 4); ms = Math.round(ms * 0.55);   // trim scenery dwell: raises events/min
    for (let k=0;k<steps;k++){ await lookYaw((k/steps)*Math.PI*2); await sleep(ms); }
  }
  // Walk around a finished structure and look at it, standing only where the view is actually
  // clear. A blind spin can spend its whole time facing a tree trunk.
  // Is `centre`'s structure the first thing the camera meets? half = its horizontal half-extent.
  function structureVisible(centre, half) {
    try {
      const eye = bot.entity.position.offset(0, 1.62, 0);
      const d = centre.minus(eye);
      const dist = Math.sqrt(d.x*d.x + d.y*d.y + d.z*d.z);
      if (dist < 1.0) return true;
      const dir = new Vec3(d.x/dist, d.y/dist, d.z/dist);
      const hit = bot.world.raycast(eye, dir, dist + half + 2);
      if (!hit) return false;                       // nothing at all -> not looking at it
      const hp = hit.position || hit;
      if (!hp || typeof hp.x !== 'number') return false;
      // inside the structure's bounding column (+1 block of slack for eaves/steps)?
      return Math.abs(hp.x + 0.5 - centre.x) <= half + 1.5 &&
             Math.abs(hp.z + 0.5 - centre.z) <= half + 1.5;
    } catch (_) { return true; }
  }

  async function orbitAndShow(centre, radius=7, stops=6, half=3) {
    let shown = 0;
    // Sweep many angles, and at each angle try progressively CLOSER radii. A single fixed radius put
    // some stops outside the cleared build site, on adjacent trees or a hillside, so a finished house
    // showed only 2 of 6 stops on rough terrain. Pulling in toward the structure (down to half+2.5)
    // keeps the vantage on the flat ground the site guarantees, and the extra angles give more
    // chances to find a clear one. A stop still needs dry ground AND the structure in clear sight.
    const N = stops * 3;
    for (let k = 0; k < N && shown < stops; k++) {
      const a = (k / N) * Math.PI * 2;
      let placed = false;
      for (const r of [radius, half + 4, half + 2.5]) {
        const x = Math.floor(centre.x + Math.cos(a) * r);
        const z = Math.floor(centre.z + Math.sin(a) * r);
        const su = surfaceOf(x, z);
        if (!su || !DRY.has(su.name)) continue;
        if (Math.abs(su.position.y + 1 - centre.y) > 4) continue;   // not up a cliff
        bot.chat(`/tp Builder ${x + 0.5} ${su.position.y + 1} ${z + 0.5}`);
        await sleep(500);
        await smoothLookAt(centre, 0.5, 5);
        if (structureVisible(centre, half)) { await sleep(650); shown++; placed = true; break; }
      }
      if (!placed) log('orbit-blocked at angle ' + (a * 180 / Math.PI).toFixed(0));
    }
    log('ORBIT_SHOWN ' + shown + '/' + stops);
  }
  // Look at an entity/block WITHOUT pitching up into empty sky: a mob standing on higher
  // ground would otherwise fill the frame with nothing but blue (a quarter of the v13
  // sample frames were sky for exactly this reason).
  async function lookAtLow(pos, dy=0.4) {
    const { yaw, pitch } = aimFor(pos, dy, true);
    await turnTo(yaw, pitch, 480);
  }
  // Back away if the pathfinder parked us right on top of the target — a frame filled with
  // one block texture carries no information.
  async function backOff(pos, min=3.0) {
    for (let k=0;k<6;k++){
      if (bot.entity.position.distanceTo(new Vec3(pos.x, bot.entity.position.y, pos.z)) >= min) return;
      bot.setControlState('back', true); await sleep(220); bot.setControlState('back', false);
      await sleep(120);
    }
  }


  // Kept for its call sites; now a thin eased wrapper. The `steps` argument becomes a duration hint
  // (more requested steps -> a longer, gentler turn) but the actual pacing is turnTo's ease-in-out.
  async function smoothLookAt(target, dy=0.4, steps=6, clampDown=true) {
    const { yaw, pitch } = aimFor(target, dy, clampDown);
    await turnTo(yaw, pitch, Math.max(360, steps * 110));
  }


  // TRUE line of sight, not just "inside the camera cone". v24 built a house that a stand of
  // trees then hid at ~2:40 — the blocks were in frame and still not watchable. A cone test
  // cannot catch that; a ray can.
  const SEE_THROUGH = new Set(['air','cave_air','void_air','water','flowing_water','glass',
    'grass','short_grass','tall_grass','fern','large_fern','dandelion','poppy','torch','wall_torch','snow',
    'oak_leaves','birch_leaves','spruce_leaves','jungle_leaves','vine']);
  function losClear(target, allowLeaves=false) {
    try {
      const eye = bot.entity.position.offset(0, 1.62, 0);
      const d = target.minus(eye);
      const dist = Math.sqrt(d.x*d.x + d.y*d.y + d.z*d.z);
      if (dist < 0.8) return true;
      const dir = new Vec3(d.x/dist, d.y/dist, d.z/dist);
      const hit = bot.world.raycast(eye, dir, dist - 0.55);
      if (!hit) return true;
      const n = hit.name || (hit.block && hit.block.name);
      if (!n) return true;
      if (SEE_THROUGH.has(n)) return true;
      if (allowLeaves && n.endsWith('_leaves')) return true;
      // A blocker sitting essentially AT the target is not an occluder — it is the neighbour the
      // target is being placed against. Only something meaningfully in front counts. Without this
      // the ray to a floor tile grazes the course already laid and rejects nearly every
      // placement (47 of the first ~50 in a trial run).
      const hp = hit.position || hit;
      if (hp && typeof hp.x === 'number') {
        const hd = Math.hypot(hp.x + 0.5 - eye.x, hp.y + 0.5 - eye.y, hp.z + 0.5 - eye.z);
        if (dist - hd < 1.6) return true;
      }
      return false;
    } catch (_) { return true; }        // no raycast -> do not block the session
  }
  // Trees are the usual culprit, so choose somewhere open BEFORE building rather than fighting
  // the occlusion afterwards.
  function siteIsOpen(cx, cz, radius=7) {
    const c = surfaceOf(Math.floor(cx), Math.floor(cz));
    if (!c) return false;
    const base = c.position.y;
    let trees = 0, heights = [], sampled = 0;
    for (let dx = -radius; dx <= radius; dx++) {
      for (let dz = -radius; dz <= radius; dz++) {
        const s = surfaceOf(Math.floor(cx+dx), Math.floor(cz+dz));
        if (!s) continue;
        sampled++;
        const n = s.name;
        if (n.endsWith('_log') || n.endsWith('_leaves')) trees++;
        heights.push(s.position.y);
        if (!DRY.has(n) && !WET.has(n)) continue;
      }
    }
    if (sampled < (radius*2+1)*(radius*2+1)*0.6) return false;   // chunk not fully loaded
    if (trees > 0) return false;                                  // ANY trunk/canopy disqualifies
    // flatness: nearly every column within one block of the centre, and no big outliers
    const within1 = heights.filter(h => Math.abs(h - base) <= 1).length / heights.length;
    const spread = Math.max(...heights) - Math.min(...heights);
    return within1 >= 0.85 && spread <= 3;
  }
  async function moveToOpenSite(radius=7) {
    const p = bot.entity.position;
    if (siteIsOpen(p.x, p.z, radius)) { log('SITE_FLAT in place'); return true; }
    for (const r of [8, 14, 20, 28, 36, 48, 64]) {
      for (const [dx,dz] of [[r,0],[-r,0],[0,r],[0,-r],[r,r],[-r,-r],[r,-r],[-r,r],
                             [r,r>>1],[-r,r>>1],[r>>1,r],[r>>1,-r]]) {
        const x = Math.floor(p.x+dx), z = Math.floor(p.z+dz);
        const su = surfaceOf(x, z);
        if (!su || !DRY.has(su.name)) continue;
        if (!siteIsOpen(x, z, radius)) continue;
        bot.chat(`/tp Builder ${x+0.5} ${su.position.y+1} ${z+0.5}`); await sleep(1400);
        await lookYaw(0); log('SITE_FLAT moved to ' + [x,z] + ' r=' + r);
        return true;
      }
    }
    log('SITE_FLAT_FAIL — levelling the ground and clearing trees');
    // flatten the footprint so the build is not half-buried in a hillside
    const q = bot.entity.position.floored();
    bot.chat(`/fill ${q.x-1} ${q.y} ${q.z-1} ${q.x+7} ${q.y+6} ${q.z+7} minecraft:air replace #minecraft:leaves`);
    bot.chat(`/fill ${q.x-1} ${q.y} ${q.z-1} ${q.x+7} ${q.y+6} ${q.z+7} minecraft:air replace #minecraft:logs`);
    bot.chat(`/fill ${q.x-1} ${q.y-1} ${q.z-1} ${q.x+7} ${q.y-1} ${q.z+7} minecraft:grass_block replace minecraft:air`);
    await sleep(1200);
    await equip('diamond_axe');
    for (let k = 0; k < 14; k++) {
      const b = bot.findBlock({ matching: x => x && (x.name.endsWith('_log') || x.name.endsWith('_leaves')),
                                maxDistance: 10, count: 1 });
      if (!b) break;
      await gotoNear(b.position, 3.5, 6000);
      try {
        const f = bot.blockAt(b.position);
        if (f && bot.canDigBlock(f)) {
          const c = f.position.offset(0.5,0.5,0.5);
          await smoothLookAt(c, 0.0, 5, false); await sleep(650);   // dead-centre + settle for the full
          const nm = f.name; const seen = aimAngle(c).ang < CONE_MINE && losClear(c, false);  // crack window
          const vz = seen ? vizOf(c.x, c.y, c.z) : null;
          await bot.dig(f);                       // dig either way (clears the site)
          if (seen) rec('mine', nm, undefined, vz);   // but RECORD only when centred with clear LOS
          else log('treeclear-occluded-skip ' + nm);
        }
      } catch (_) {}
    }
    log('TREES_CLEARED'); return false;
  }

  // Mine a block ONLY when the camera has clear line of sight to it — a block dug from behind a
  // trunk, leaves, or another block is recorded as `mine` but the viewer sees the occluder, not the
  // target. That is the mining twin of the placement fairness gate. Reposition around the block to
  // find a clear view first; if none exists, do not mine it (return false so the caller finds
  // another). `t` is the block's centre.
  async function mineVisible(f) {
    const t = f.position.offset(0.5, 0.5, 0.5);
    await backOff(t, 2.8);
    await smoothLookAt(t, 0.0, 5, false);                 // dead-centre, allowed to look UP at a log
    const centred = () => { const a = aimAngle(t); return a.ang < CONE_MINE && a.dist <= 4.3 && losClear(t, false); };
    if (!centred()) {
      // step around the block -- out along a few compass directions at its own height -- until it is
      // both centred and in clear sight; if none exists, do not mine it (the crack must sit ON it).
      for (const [ox, oz] of [[3,0],[-3,0],[0,3],[0,-3],[3,2],[-3,-2],[2,-3],[-2,3]]) {
        const sx = Math.floor(f.position.x + 0.5 + ox), sz = Math.floor(f.position.z + 0.5 + oz);
        const surf = surfaceOf(sx, sz);
        if (!surf || !DRY.has(surf.name)) continue;
        bot.chat(`/tp Builder ${sx + 0.5} ${surf.position.y + 1} ${sz + 0.5}`); await sleep(520);
        await smoothLookAt(t, 0.0, 5, false); await sleep(140);
        if (centred()) break;
      }
      if (!centred()) return false;                        // genuinely unshowable -- skip, do not mine
    }
    await sleep(700);                           // settle on the block for the full crack window
    try { bot.swingArm('right'); } catch (_) {}
    const nm = f.name;
    const vz = vizOf(t.x, t.y, t.z);            // capture the aim BEFORE the block vanishes
    try { await bot.dig(f); } catch (e) { log('dig ' + e.message); return false; }
    rec('mine', nm, undefined, vz);
    await sleep(400);
    return true;
  }

  async function gatherCategory(name, count, maxDist=90) {
    const set = cat[name]; let got=0, miss=0;
    const skip = new Set();   // blocks we could not show unoccluded — don't re-pick them
    await equip(name==='wood'?'diamond_axe':'diamond_pickaxe');
    // Match by NAME only: mineflayer runs the matcher during iteration with `position` not yet
    // populated, so referencing x.position in the matcher rejects every block. Use findBlocks
    // (returns populated Vec3 positions) and drop skipped ones in JS.
    const pick = () => bot.findBlocks({ matching:x=>x&&set.has(x.name), maxDistance:maxDist, count:64 })
                          .find(v => !skip.has(v.toString())) || null;
    while (got<count && miss<6) {
      let pos = pick();
      if(!pos){ // nothing pickable from here -- relocate toward the nearest matching block, then retry
        const near = bot.findBlocks({ matching:x=>x&&set.has(x.name), maxDistance:maxDist, count:1 })[0];
        const p = bot.entity.position;
        if(near){ bot.chat(`/tp Builder ${near.x} ${near.y+30} ${near.z}`); }
        else { const ang=miss*1.7; bot.chat(`/tp Builder ${Math.floor(p.x+Math.cos(ang)*24)} ${Math.floor(p.y)+40} ${Math.floor(p.z+Math.sin(ang)*24)}`); }
        await sleep(600); await landDry(bot.entity.position.x, bot.entity.position.z);
        pos = pick();
        if(!pos){ miss++; await sleep(120); continue; }
      }
      const b = bot.blockAt(pos);
      if(!b){ miss++; continue; }
      // A far pick sits in an UNLOADED chunk the pathfinder cannot route to, which used to thrash
      // (~6 slow "decide path" failures per biome-gather = the main render stall). Drop in right next
      // to it first (loads its chunk, makes the approach short), then walk the last few blocks.
      if (bot.entity.position.distanceTo(pos) > 12) {
        bot.chat(`/tp Builder ${pos.x} ${pos.y+30} ${pos.z}`); await sleep(500); await landDry(pos.x, pos.z);
      }
      // Stop ~3.5 blocks short: standing right against the target fills the whole frame
      // with one texture, which is useless footage. Reach is ~5 blocks, so this still digs.
      await gotoNear(b.position,3.5,6000);
      try{ const f=bot.blockAt(b.position);
        if(f&&set.has(f.name)&&bot.canDigBlock(f)){
          if (await mineVisible(f)) got++;                       // only counts when it was visible
          else { skip.add(b.position.toString()); miss++; }      // occluded -> skip, try another
        }
        else miss++;
      }catch(e){log('dig '+e.message); miss++;}
    }
  }

  // Topmost solid block of a column, using the client's loaded chunk data.
  function surfaceOf(x, z, yTop=150) {
    for (let y=yTop; y>40; y--) {
      const b = bot.blockAt(new Vec3(x, y, z));
      if (!b || b.name==='air' || b.name==='void_air' || b.name==='cave_air') continue;
      return b;
    }
    return null;
  }
  // Find a DRY standing column near (cx,cz) and teleport onto it. Rejects ocean/ice/lava
  // columns — v10's blue-washed footage was the bot standing at sea level.
  async function landDry(cx, cz) {
    // Wait for the client to actually receive the chunk — scanning too early sees only
    // nulls and reports "no dry land" for a perfectly good biome (v11 lost snowy + badlands
    // this way).
    for (let a=0; a<5; a++) {
      if (surfaceOf(Math.floor(cx), Math.floor(cz))) break;
      log('chunk-wait ' + a); await sleep(3000);
    }
    const rings = [0,6,12,18,24,32,40];
    for (const r of rings) {
      const pts = r===0 ? [[0,0]] : [[r,0],[-r,0],[0,r],[0,-r],[r,r],[-r,-r],[r,-r],[-r,r]];
      for (const [dx,dz] of pts) {
        const x=Math.floor(cx)+dx, z=Math.floor(cz)+dz;
        const s = surfaceOf(x,z);
        if (!s || WET.has(s.name) || !DRY.has(s.name)) continue;
        const a1 = bot.blockAt(new Vec3(x, s.position.y+1, z));
        const a2 = bot.blockAt(new Vec3(x, s.position.y+2, z));
        if (a1 && a2 && a1.name==='air' && a2.name==='air') {
          bot.chat(`/tp Builder ${x+0.5} ${s.position.y+1} ${z+0.5}`); await sleep(1500);
          log('LAND_DRY ' + [x, s.position.y+1, z] + ' on ' + s.name);
          await lookYaw(0);
          return true;
        }
      }
    }
    log('LAND_DRY_FAIL near ' + [cx,cz]); return false;
  }
  const MC_MAJOR = parseInt(MC_VERSION.split('.')[1] || '16', 10);
  // 1.18 renamed some biomes; map our canonical (1.16) names forward.
  const BIOME_1_18 = { snowy_tundra: 'snowy_plains', badlands: 'badlands', beach: 'beach',
                       wooded_badlands_plateau: 'wooded_badlands', mountains: 'stony_peaks',
                       giant_tree_taiga: 'old_growth_pine_taiga' };
  function biomeId(b) { return (MC_MAJOR >= 18 && BIOME_1_18[b]) ? BIOME_1_18[b] : b; }
  function locateCmd(b) { return MC_MAJOR >= 19 ? `/locate biome minecraft:${biomeId(b)}`
                                                : `/locatebiome minecraft:${biomeId(b)}`; }

  function locateOnce(biome, ms) {
    return new Promise(resolve=>{ const h=(msg)=>{ try{ const j=JSON.stringify(msg.json||msg);
      const m=j.match(/tp @s (-?\d+) (~|-?\d+) (-?\d+)/); if(m&&/locate|nearest/i.test(j)){ bot.removeListener('message',h); resolve([+m[1],+m[3]]); } }catch(e){} };
      bot.on('message',h); bot.chat(locateCmd(biome)); setTimeout(()=>{bot.removeListener('message',h);resolve(null);},ms); });
  }
  async function tpToBiome(biome) {
    // Read /locate biome output for the nearest match. This REQUIRES sendCommandFeedback on (the
    // authentic session sets it; turning it off to stop a chat leak silently broke biome travel on
    // every Java render). One generous attempt, then one retry in place for a transient miss — no
    // long teleport, which previously flung the bot into ungenerated chunks and guaranteed a miss.
    let found = await locateOnce(biome, 12000);
    if (!found) { await sleep(500); found = await locateOnce(biome, 12000); }
    if(!found){ log('biome-miss '+biome); return false; }
    bot.chat(`/tp Builder ${found[0]} 150 ${found[1]}`); await sleep(4000);   // load the chunk
    const ok = await landDry(found[0], found[1]);
    log('tp '+biome+' '+found+' dry='+ok);
    return ok;
  }

  // Summon the mob out at ~9 blocks and walk to it — no arm's-length pop-in.
  async function spawnFar(mob, dist=9) {
    const yaw = bot.entity.yaw, p = bot.entity.position;
    const x = p.x + Math.sin(-yaw)*dist, z = p.z + Math.cos(-yaw)*dist;
    const s = surfaceOf(Math.floor(x), Math.floor(z));
    let y = s ? s.position.y+1 : Math.floor(p.y);
    if (Math.abs(y - p.y) > 4) y = Math.floor(p.y);   // don't put mobs up a cliff
    bot.chat(`/summon minecraft:${mob} ${x.toFixed(1)} ${y} ${z.toFixed(1)}`);
    await sleep(1200);
    return Object.values(bot.entities).find(e=>e.name===mob && e.position.distanceTo(p) < dist+8) || null;
  }
  // Under a dense canopy the computed far spot can be inside foliage and the summon fails;
  // fall back to progressively closer spots, then to a relative summon that always works.
  async function spawnAny(mob) {
    for (const d of [9, 5]) { const e = await spawnFar(mob, d); if (e) return e; }
    bot.chat(`/summon minecraft:${mob} ~ ~1 ~3`); await sleep(1300);
    return Object.values(bot.entities).find(e=>e.name===mob &&
      e.position.distanceTo(bot.entity.position) < 16) || null;
  }
  // Was the mob in frame when it died? A kill that happens off-camera (the animal wandered
  // behind a hill or drowned in a river) is unanswerable from the video, so it must NOT be
  // scored. v15 recorded a panda kill with the panda visible in no frame of the fight.
  function inView(pos, maxDist=17, maxDeg=48) {
    if (!pos) return false;
    const eye = bot.entity.position.offset(0, 1.62, 0);
    const d = pos.minus(eye);
    const dist = Math.sqrt(d.x*d.x + d.y*d.y + d.z*d.z);
    if (dist > maxDist) return false;
    // mineflayer pitch is positive UP (measured: lookAt above => +0.82, below => -0.75).
    const yaw = bot.entity.yaw, pitch = bot.entity.pitch;
    const f = { x: -Math.sin(yaw)*Math.cos(pitch), y: Math.sin(pitch), z: Math.cos(yaw)*Math.cos(pitch) };
    const dot = (d.x*f.x + d.y*f.y + d.z*f.z) / (dist || 1);
    if (Math.acos(Math.max(-1, Math.min(1, dot))) >= maxDeg * Math.PI / 180) return false;
    try {   // line of sight: nothing solid between the eye and the mob
      const hit = bot.world.raycast(eye, new Vec3(d.x/dist, d.y/dist, d.z/dist), dist - 0.6);
      if (hit) return false;
    } catch (_) {}
    return true;
  }
  // Record a kill only if it was witnessed; hold the camera on the spot so the mob is seen
  // to vanish.
  async function finishKill(mob, weapon, lastPos, seen) {
    if (lastPos) { await lookAtLow(lastPos); await sleep(800); }
    if (lastPos) {
      const eye = bot.entity.position.offset(0, 1.62, 0), d = lastPos.minus(eye);
      const dist = Math.sqrt(d.x*d.x+d.y*d.y+d.z*d.z);
      const yaw = bot.entity.yaw, pitch = bot.entity.pitch;
      const f = { x:-Math.sin(yaw)*Math.cos(pitch), y:Math.sin(pitch), z:Math.cos(yaw)*Math.cos(pitch) };
      const ang = Math.acos(Math.max(-1,Math.min(1,(d.x*f.x+d.y*f.y+d.z*f.z)/(dist||1))))*180/Math.PI;
      log(`KILLCHK ${mob} ${weapon} dist=${dist.toFixed(1)} seen=${seen}`);
    } else log(`KILLCHK ${mob} ${weapon} NO_LAST_POS`);
    if (seen) rec('kill', mob, weapon);
    else log('kill-offcamera ' + mob + ' ' + weapon);
  }
  async function huntMelee(mob, n=1) {
    await equip('diamond_sword');
    for (let k=0;k<n;k++){
      let e = await spawnAny(mob);
      if(!e){ log('mob-miss '+mob); continue; }
      await gotoNear(e.position,2,9000);
      let last=null, seen=false, ticks=0;
      for(let s=0;s<20;s++){ const c=Object.values(bot.entities).find(x=>x.id===e.id); if(!c||!c.isValid) break;
        last=c.position.clone(); await smoothLookAt(c.position, 0.4, 3);
        if (c.position.distanceTo(bot.entity.position) < 16 && losClear(c.position.offset(0,0.6,0), true)) ticks++;
        try{ bot.attack(c); }catch(_){} await sleep(520); }
      seen = ticks >= 3;
      await sleep(300);   // let the recoil/knockback of the final hit render
      await finishKill(mob,'sword',last,seen);
    }
  }
  async function huntBow(mob) {
    await equip('bow');
    const e = await spawnAny(mob);
    if(!e){ log('bowmob-miss '+mob); return; }
    let last=null, seen=false, ticks=0;
    for(let s=0;s<8;s++){ const c=Object.values(bot.entities).find(x=>x.id===e.id); if(!c||!c.isValid) break;
      last=c.position.clone(); await lookAtLow(c.position, 0.3);
      if (c.position.distanceTo(bot.entity.position) < 26 && losClear(c.position.offset(0,0.6,0), true)) ticks++;
      try{ bot.activateItem(); await sleep(1100); bot.deactivateItem(); }catch(_){} await sleep(800); }
    seen = ticks >= 2;
    await finishKill(mob,'bow',last,seen);
  }


  // Place a block only when the player can actually SEE it. A structure whose far wall goes
  // up off-camera puts unanswerable rows in the ledger, exactly like an off-camera kill.
  // If the block is not visible from where we stand, walk around to its own side of the
  // build first — which is also how a real player builds.
  // Visibility test for a placement. Deliberately NOT the kill test: a block being built is
  // often only 2-3 m away and low, so a line-of-sight ray grazes the ground or the course
  // already laid and reports a false occlusion (v21 rejected 9 of its first 10 placements
  // this way). What matters here is that the block is in front of the player and near
  // enough to read, with the walk-to-its-own-side step below handling real occlusion by the
  // structure itself.
  function placeWhy(t) {
    const eye = bot.entity.position.offset(0, 1.62, 0);
    const d = t.minus(eye);
    const dist = Math.sqrt(d.x*d.x + d.y*d.y + d.z*d.z);
    const yaw = bot.entity.yaw, pitch = bot.entity.pitch;
    const f = { x:-Math.sin(yaw)*Math.cos(pitch), y:Math.sin(pitch), z:Math.cos(yaw)*Math.cos(pitch) };
    const ang = Math.acos(Math.max(-1,Math.min(1,(d.x*f.x+d.y*f.y+d.z*f.z)/(dist||1))))*180/Math.PI;
    return `dist=${dist.toFixed(1)} ang=${ang.toFixed(0)}`;
  }
  const DEFERRED = [];                        // blocks the camera missed; placed in a second pass
  // Every scored action must sit clearly inside the frame, not at its edge. The viewer's vertical FOV
  // is 75 deg (half 37.5), so a target beyond ~26 deg off the view axis is near the frame edge. These
  // cones keep each placement/mine inside the readable central region; MAXD_PLACE keeps it near enough
  // to read. (The break-crack is then projected onto the mined block's exact screen position by
  // fx_overlay, so it lands ON the block wherever in the frame it is.)
  const CONE_PLACE = 24, CONE_MINE = 26, MAXD_PLACE = 9;
  // Angle (deg) of `t` off the current view axis, and its distance from the eye.
  function aimAngle(t) {
    const eye = bot.entity.position.offset(0, 1.62, 0);
    const d = t.minus(eye);
    const dist = Math.sqrt(d.x*d.x + d.y*d.y + d.z*d.z) || 1e-6;
    const yaw = bot.entity.yaw, pitch = bot.entity.pitch;
    const f = { x: -Math.sin(yaw)*Math.cos(pitch), y: Math.sin(pitch), z: Math.cos(yaw)*Math.cos(pitch) };
    const dot = (d.x*f.x + d.y*f.y + d.z*f.z) / dist;
    return { ang: Math.acos(Math.max(-1, Math.min(1, dot))) * 180 / Math.PI, dist };
  }
  // Put the camera where `t` is centred in frame with clear line of sight, THEN the caller acts.
  // The vantage is at the block's OWN height -- creative flight for anything well above the ground --
  // and backed off along the block's outward normal (from the structure centre cx,cz), so the look is
  // near-level and the block lands dead-centre. This is what makes every placement unmistakably seen
  // and the composited break-crack sit ON the mined block. Returns false if no such vantage exists
  // (the caller then skips the block rather than acting off-camera). `ds` = back-off distances to try;
  // `maxD` = the farthest the block may be and still count as readable.
  async function frameFromHeight(t, cx, cz, tightDeg, ds, maxD) {
    const gs = surfaceOf(Math.round(t.x), Math.round(t.z));
    const gy = gs ? gs.position.y + 1 : Math.round(t.y);
    const high = t.y > gy + 2.5;
    const ok = () => { const a = aimAngle(t); return a.ang < tightDeg && a.dist >= 1.5 && a.dist <= maxD && losClear(t, true); };
    // 1) already framed from here? just re-aim dead-centre -- keeps a run a smooth pan, no jump cut.
    await smoothLookAt(t, 0, 5, false); await sleep(90);
    if (ok()) return true;
    // 2) reposition to a height-matched vantage backed off along the block's outward normal.
    let nx = t.x - cx, nz = t.z - cz; const L = Math.hypot(nx, nz) || 1; nx /= L; nz /= L;
    if (high) bot.creative.startFlying(); else bot.creative.stopFlying();
    const lat = [[0,0], [-nz,nx], [nz,-nx], [-nz*1.8,nx*1.8], [nz*1.8,-nx*1.8]];
    for (const d of ds) {
      for (const [lx, lz] of lat) {
        const vx = t.x + nx*d + lx, vz = t.z + nz*d + lz;
        let vy;
        if (high) vy = Math.max(gy, Math.round(t.y - 1.4));
        else { const su = surfaceOf(Math.round(vx), Math.round(vz)); vy = su ? su.position.y + 1 : gy; }
        bot.chat(`/tp Builder ${vx.toFixed(2)} ${vy} ${vz.toFixed(2)}`); await sleep(high ? 240 : 300);
        await smoothLookAt(t, 0, 5, false); await sleep(110);
        if (ok()) return true;
      }
    }
    return false;
  }
  // Natural terrain that must never sit ON TOP of a block we are placing: a placed block with grass
  // or a leaf directly above it looks tucked under an overhang and is hard to read. Clear it first.
  const OVERHEAD = new Set(['grass_block','dirt','coarse_dirt','podzol','grass','tall_grass','short_grass',
    'fern','large_fern','snow','snow_block','sand','red_sand','gravel','clay','moss_block','dead_bush',
    'oak_leaves','birch_leaves','spruce_leaves','jungle_leaves','acacia_leaves','dark_oak_leaves',
    'oak_log','birch_log','spruce_log','jungle_log','acacia_log','dark_oak_log','poppy','dandelion','vine']);
  async function clearAbove(x, y, z) {
    for (const dy of [1, 2, 3]) {
      const a = bot.blockAt(new Vec3(x, y + dy, z));
      if (a && OVERHEAD.has(a.name)) bot.chat(`/setblock ${x} ${y + dy} ${z} air`);
    }
    await sleep(50);
  }

  async function placeVisible(x, y, z, block, cx, cz) {
    const t = new Vec3(x + 0.5, y + 0.5, z + 0.5);
    await clearAbove(x, y, z);                  // no grass/overhang tucked above the placed block
    // Frame the block dead-centre from a height-matched vantage (flying for high courses like the
    // roof). If it cannot be framed with clear LOS from any vantage, DEFER it -- never place unseen,
    // so world state and the ledger always agree.
    if (!(await frameFromHeight(t, cx, cz, CONE_PLACE, [4.5, 5.5, 3.8, 6.5], MAXD_PLACE))) {
      DEFERRED.push({ x, y, z, block, cx, cz });
      log('place-deferred ' + block + ' ' + [x, y, z] + ' ' + placeWhy(t));
      return;
    }
    try { bot.swingArm('right'); } catch(_){}   // a real building motion the camera sees
    bot.chat(`/setblock ${x} ${y} ${z} minecraft:${block}`);
    await sleep(400);
    rec('place', block.split('[')[0], undefined, vizOf(t.x, t.y, t.z));   // base name, not [facing=..]
  }

  // Second pass over everything the camera missed: reposition until each block is genuinely in
  // view, then place and record it. Anything still impossible after this is placed and logged as
  // an accepted residual, and it is asserted to be a small number.
  async function finishDeferred() {
    bot.creative.stopFlying();                        // land after the (possibly flying) inline pass
    if (!DEFERRED.length) { log('DEFERRED none'); return; }
    const todo = DEFERRED.splice(0, DEFERRED.length);
    log('DEFERRED_PASS ' + todo.length);
    // bottom-to-top so a course is never framed through the course above it that is not placed yet.
    todo.sort((a, b) => (a.y - b.y) || (a.x - b.x) || (a.z - b.z));
    let done = 0, residual = 0;
    for (const b of todo) {
      const t = new Vec3(b.x + 0.5, b.y + 0.5, b.z + 0.5);
      if (await frameFromHeight(t, b.cx, b.cz, CONE_PLACE, [4.5, 5.5, 3.8, 6.5, 3.0], MAXD_PLACE)) {
        try { bot.swingArm('right'); } catch(_){}
        bot.chat(`/setblock ${b.x} ${b.y} ${b.z} minecraft:${b.block}`);
        await sleep(340);
        rec('place', b.block.split('[')[0], undefined, vizOf(t.x, t.y, t.z)); done++;
      } else {
        // Unshowable from every vantage: SKIP entirely -- not placed, not recorded -- so world ==
        // ledger and every recorded placement is provably on-camera. A few skipped decor/edge blocks
        // leave at worst a tiny cosmetic gap; fairness (every scored action visible) wins.
        residual++;
        log('deferred-skip-unshown ' + b.block + ' ' + [b.x, b.y, b.z]);
      }
    }
    bot.creative.stopFlying();
    log('DEFERRED_DONE recorded=' + done + ' skipped_unshown=' + residual);
  }


  // Place a batch of blocks as ONE natural run: stand at a fixed vantage on `faceDir` side of the
  // structure, then place the blocks in screen-left-to-right, bottom-to-top order from that view.
  // This fixes two unnatural artifacts: (a) the fill direction matching the camera (a row placed
  // left-to-right in the world used to read right-to-left when placeVisible put the camera on the far
  // side per block), and (b) each block cleared of anything overhead. The camera stays on one side
  // for the whole element, so it reads like a person building a wall while looking at it.
  async function placeRun(blocks, faceDir, cx, cz) {
    const [fx, fz] = faceDir;
    const half = 2.5;
    const vx = Math.floor(cx + fx * (half + 4)), vz = Math.floor(cz + fz * (half + 4));
    const surf = surfaceOf(vx, vz);
    if (surf) { bot.chat(`/tp Builder ${vx + 0.5} ${surf.position.y + 1} ${vz + 0.5}`); await sleep(700); await lookAtLow(new Vec3(cx, blocks[0] ? blocks[0].y + 0.5 : 64, cz), 0.0); }
    // screen-right for a camera at the vantage looking back at the centre (view dir = -faceDir):
    // right = (-faceDir) x up = (fz, 0, -fx)
    const rx = fz, rz = -fx;
    blocks.sort((a, b) => {
      const sa = (a.x - cx) * rx + (a.z - cz) * rz, sb = (b.x - cx) * rx + (b.z - cz) * rz;
      if (Math.abs(sa - sb) > 0.01) return sa - sb;   // left -> right on screen
      return a.y - b.y;                                // then bottom -> top
    });
    for (const bl of blocks) await placeVisible(bl.x, bl.y, bl.z, bl.b, cx, cz);
  }

  async function buildHouse(lap = 0) {
    await moveToOpenSite(8);
    const q = bot.entity.position.floored(); const X=q.x+2, Y=q.y, Z=q.z;
    const CX = X + 2.5, CZ = Z + 2.5;
    const P=(x,y,z,b)=>placeVisible(x,y,z,b,CX,CZ);
    await lookYaw(0);
    const S=5;
    const floorMat = (dx,dz)=>['stone_bricks','cobblestone','andesite','stone'][(dx+2*dz)%4];
    const timber=['birch_planks','oak_planks','spruce_planks','jungle_planks'];
    // Floor as one run, viewed from the south, filling left->right.
    const floor=[]; for(let dx=0;dx<S;dx++)for(let dz=0;dz<S;dz++) floor.push({x:X+dx,y:Y-1,z:Z+dz,b:floorMat(dx,dz)});
    await placeRun(floor, [0,1], CX, CZ);
    // Each of the four walls as its own run, viewed from OUTSIDE that wall so the camera faces the
    // blocks head-on and the row fills left->right. A cell is placed by whichever wall reaches it
    // first (corners belong to one run only).
    const done = new Set();
    const wallBlock=(dx,dz,h)=>{
      const corner=(dx===0||dx===S-1)&&(dz===0||dz===S-1);
      return corner ? 'oak_log' : (h===1&&(dx===2||dz===2) ? 'glass' : timber[(dx+2*dz+h)%3]);
    };
    const edges = [
      { face:[0,-1], cells:()=>{const c=[];for(let dx=0;dx<S;dx++)for(let h=0;h<3;h++){if(dx===2&&h<2)continue;c.push([dx,0,h]);}return c;} },   // north wall (dz=0), doorway gap
      { face:[0, 1], cells:()=>{const c=[];for(let dx=0;dx<S;dx++)for(let h=0;h<3;h++)c.push([dx,S-1,h]);return c;} },                              // south wall
      { face:[-1,0], cells:()=>{const c=[];for(let dz=0;dz<S;dz++)for(let h=0;h<3;h++)c.push([0,dz,h]);return c;} },                                // west wall
      { face:[ 1,0], cells:()=>{const c=[];for(let dz=0;dz<S;dz++)for(let h=0;h<3;h++)c.push([S-1,dz,h]);return c;} },                               // east wall
    ];
    for(const e of edges){
      const run=[];
      for(const [dx,dz,h] of e.cells()){
        const key=dx+','+dz+','+h; if(done.has(key)) continue; done.add(key);
        run.push({x:X+dx,y:Y+h,z:Z+dz,b:wallBlock(dx,dz,h)});
      }
      if(run.length) await placeRun(run, e.face, CX, CZ);
    }
    await P(X+2,Y,Z,'oak_door');
    // A proper gable roof: two stair slopes ascending to a ridge, oriented so each reads as a slope,
    // with a one-block eave overhang front and back and the triangular gable ends filled so it looks
    // like a closed roof rather than a skeleton. Built from elevated (flying) vantages via
    // frameFromHeight, so every roof block is framed dead-centre and none is skipped off-camera.
    // Roof timber ROTATES per lap so no single (place, <wood>_stairs) token dominates the ledger --
    // a 42-stair gable repeated in ONE wood across 5 laps was the most-common token at 17.8% (mono
    // ablation 0.15). Rotating over 5 woods spreads it to ~42 each. All are vanilla 1.16 blocks the
    // viewer renders; recorded as the base name (the [facing=..] state is stripped in rec()).
    const RW = ['oak','spruce','birch','jungle','acacia'][((lap % 5) + 5) % 5];
    const roofW=[], roofE=[], ridge=[];
    for(let dz=-1;dz<=S;dz++){                                     // dz -1..S = 1-block eave overhang
      const zz=Z+dz;
      roofW.push({x:X-1,y:Y+3,z:zz,b:`${RW}_stairs[facing=east]`});     // west eave, then slope up to ridge
      roofW.push({x:X+0,y:Y+3,z:zz,b:`${RW}_stairs[facing=east]`});
      roofW.push({x:X+1,y:Y+4,z:zz,b:`${RW}_stairs[facing=east]`});
      roofE.push({x:X+S,  y:Y+3,z:zz,b:`${RW}_stairs[facing=west]`});   // east eave, then slope up to ridge
      roofE.push({x:X+S-1,y:Y+3,z:zz,b:`${RW}_stairs[facing=west]`});
      roofE.push({x:X+S-2,y:Y+4,z:zz,b:`${RW}_stairs[facing=west]`});
      ridge.push({x:X+2,y:Y+5,z:zz,b:`${RW}_planks`});
    }
    const gable=[];
    for(const zz of [Z-1, Z+S]){                                  // fill each triangular gable end
      gable.push({x:X+1,y:Y+3,z:zz,b:`${RW}_planks`});
      gable.push({x:X+2,y:Y+3,z:zz,b:`${RW}_planks`});
      gable.push({x:X+3,y:Y+3,z:zz,b:`${RW}_planks`});
      gable.push({x:X+2,y:Y+4,z:zz,b:`${RW}_planks`});
    }
    await placeRun(roofW, [-1,0], CX, CZ);
    await placeRun(roofE, [ 1,0], CX, CZ);
    await placeRun(gable, [0,-1], CX, CZ);
    await placeRun(ridge, [0, 1], CX, CZ);
    await P(X+4,Y+3,Z+1,'cobblestone'); await P(X+4,Y+4,Z+1,'cobblestone');     // chimney
    await P(X+2,Y,Z+2,'torch'); await P(X+2,Y+2,Z+2,'torch');
    for(let dx=0;dx<3;dx++) await P(X+dx,Y,Z-2,'oak_fence');                    // garden fence
    log('HOUSE_DONE');
    await finishDeferred();
    bot.creative.stopFlying();
    await orbitAndShow(new Vec3(X + 2.5, Y + 1, Z + 2.5), 9, 6, 3);   // 7x7 house
  }
  // A stone watchtower: a second, different structure so the build vocabulary is not just
  // the cabin's palette.
  async function buildTower() {
    await moveToOpenSite(6);
    const q = bot.entity.position.floored(); const X=q.x+3, Y=q.y, Z=q.z+1;
    const CX = X + 0.5, CZ = Z + 0.5;
    const P=(x,y,z,b)=>placeVisible(x,y,z,b,CX,CZ);
    await lookYaw(0);
    for (let h=0; h<5; h++) {
      for (const [dx,dz] of [[0,0],[1,0],[0,1],[1,1]]) {
        const b = (h===4) ? 'stone_bricks' : (h===2 && dx===0 && dz===0 ? 'glass'
              : ['cobblestone','andesite','diorite','granite'][(h+dx+dz)%4]);
        await P(X+dx, Y+h, Z+dz, b);
      }
    }
    await P(X, Y+5, Z, 'torch');
    for (let dx=0; dx<2; dx++) await P(X+dx, Y, Z-1, 'oak_fence');
    log('TOWER_DONE');
    await finishDeferred();
    await orbitAndShow(new Vec3(X + 0.5, Y + 2, Z + 0.5), 7, 5, 1);   // 3x3 tower
  }
  // A village well: a third structure, small and with yet another palette.
  async function buildWell() {
    await moveToOpenSite(5);
    const q = bot.entity.position.floored(); const X=q.x+3, Y=q.y, Z=q.z+2;
    const CX = X + 1.0, CZ = Z + 1.0;
    const P=(x,y,z,b)=>placeVisible(x,y,z,b,CX,CZ);
    await lookYaw(0);
    for (const [dx,dz] of [[0,0],[1,0],[2,0],[0,1],[2,1],[0,2],[1,2],[2,2]])
      await P(X+dx, Y, Z+dz, ['cobblestone','stone_bricks','andesite','granite'][(dx+2*dz)%4]);
    await P(X, Y+1, Z, 'oak_fence'); await P(X+2, Y+1, Z+2, 'oak_fence');
    await P(X+1, Y+1, Z+1, 'torch');
    log('WELL_DONE');
    await finishDeferred();
    await orbitAndShow(new Vec3(X + 1, Y + 1, Z + 1), 6, 5, 2);       // 3x3 well
  }
  // A desert temple: a stepped sandstone ziggurat, a third structure type with a wholly different
  // palette (sandstone / red_sandstone bands) and silhouette from the cabin and tower. Built tier by
  // tier, bottom to top, each tier's shell as one screen-ordered run so it reads as real building.
  async function buildDesertTemple() {
    await moveToOpenSite(7);
    const q = bot.entity.position.floored(); const X = q.x + 2, Y = q.y, Z = q.z;
    const CX = X + 3.5, CZ = Z + 3.5;                                 // 7x7 base
    const band = h => (h === 1 ? 'red_sandstone' : 'sandstone');      // one red accent course
    for (let h = 0; h < 4; h++) {
      const lo = h, hi = 6 - h;                                       // 7x7 -> 5x5 -> 3x3 -> 1x1
      const ring = [];
      for (let dx = lo; dx <= hi; dx++) for (let dz = lo; dz <= hi; dz++) {
        if (dx === lo || dx === hi || dz === lo || dz === hi || h === 3)
          ring.push({ x: X + dx, y: Y + h, z: Z + dz, b: band(h) });
      }
      await placeRun(ring, [0, 1], CX, CZ);                           // fill each tier from the south
    }
    // a small entrance frame on the south face + a torch, so it reads as a temple not a mound
    await placeVisible(X + 3, Y, Z + 6, 'sandstone', CX, CZ);
    await placeVisible(X + 3, Y + 1, Z + 6, 'red_sandstone', CX, CZ);
    await placeVisible(X + 3, Y + 2, Z + 6, 'torch', CX, CZ);
    log('TEMPLE_DONE');
    await finishDeferred();
    await orbitAndShow(new Vec3(CX, Y + 1, CZ), 10, 6, 4);            // 7x7 base
  }
  // Ride a boat across the water for a few seconds. prismarine-viewer DOES render boats and
  // riders, so this adds real, natural first-person variety. Produces no ledger events (it is
  // travel, not a mine/place/kill), so it is kept short.
  async function boatRide() {
    const p = bot.entity.position.floored();
    // find water in front and drop a boat on it
    let spot = null;
    for (let d = 2; d <= 8 && !spot; d++) {
      for (const [ex, ez] of [[d,0],[0,d],[d,d],[-d,0],[0,-d]]) {
        const b = bot.blockAt(new Vec3(p.x+ex, p.y-1, p.z+ez));
        if (b && (b.name === 'water' || b.name === 'seagrass')) { spot = [p.x+ex, p.y, p.z+ez]; break; }
      }
    }
    if (!spot) { log('boat-no-water'); return; }
    bot.chat(`/summon minecraft:boat ${spot[0]+0.5} ${spot[1]} ${spot[2]+0.5}`);
    await sleep(1200);
    const boat = Object.values(bot.entities).find(e => e.name === 'boat' &&
      e.position.distanceTo(bot.entity.position) < 12);
    if (!boat) { log('boat-miss'); return; }
    await gotoNear(boat.position, 1, 6000);
    try { bot.mount(boat); } catch (_) {}
    await sleep(800);
    bot.setControlState('forward', true); bot.setControlState('jump', false);
    for (let k = 0; k < 8; k++) { await smoothLookAt(bot.entity.position.offset(Math.sin(k), 0, 4), 0.2, 2); await sleep(700); }
    bot.setControlState('forward', false);
    try { bot.dismount(); } catch (_) {}
    await sleep(600); log('BOAT_DONE');
  }
  // Dig a staircase mine. Ores are embedded in the walls FIRST (off-camera, below ground),
  // so the player discovers them while digging instead of watching them appear.
  async function digMine() {
    const q = bot.entity.position.floored();
    const ores = ['coal_ore','iron_ore','gold_ore','redstone_ore','lapis_ore','diamond_ore','emerald_ore'];
    // Cast the whole tunnel volume as solid stone first. v11 dug near a jungle shoreline and
    // the mine flooded, washing minutes of footage blue; a rock mass cannot flood and looks
    // like a real mine shaft.
    // Layered rock, so the shaft yields several distinct block types instead of 21x "stone".
    const strata = ['stone','andesite','granite','diorite'];
    for (let s=1;s<=9;s++){                       // one rock type per depth row, no overlap
      const rock = strata[(s-1)%strata.length], y = q.y-s;
      for (const what of ['water','air','cave_air','stone','gravel','dirt','sand'])
        bot.chat(`/fill ${q.x} ${y} ${q.z-3} ${q.x+12} ${y} ${q.z+3} minecraft:${rock} replace minecraft:${what}`);
    }
    await sleep(1500);
    for (let s=1;s<=9;s++)   // ore in the wall of each step (7 ore types, then repeats)
      bot.chat(`/setblock ${q.x+s+1} ${q.y-s} ${q.z} minecraft:${ores[(s-1)%ores.length]}`);
    await sleep(900);
    await equip('diamond_pickaxe');
    for (let s=1;s<=9;s++){
      const x=q.x+s, y=q.y-s, z=q.z;
      for (let yy=y; yy<=y+2; yy++){
        const b=bot.blockAt(new Vec3(x,yy,z));
        if (b && b.name!=='air' && bot.canDigBlock(b)) {
          // the frontmost shaft block the bot is cutting into — visible by construction, but gate on
          // LOS anyway so nothing behind an already-cut face is recorded unseen.
          const t=b.position.offset(0.5,0.5,0.5); await smoothLookAt(t,0.0,5,false); await sleep(650);
          if (aimAngle(t).ang < CONE_MINE && losClear(t,false)) { const vz=vizOf(t.x,t.y,t.z); try{ bot.swingArm('right'); await bot.dig(b); rec('mine',b.name,undefined,vz); }catch(_){} }
        }
      }
      // Light the step we just cut. This is visible on camera, so it is a real ledger event.
      await placeVisible(x, y, z, 'torch', x + 2, z);
      await gotoNear({x,y:y+1,z},1,5000);
      // mine the ore exposed in the side wall of this step, only when it is in clear sight
      const o = bot.blockAt(new Vec3(x+1,y,z));
      if (o && o.name.endsWith('_ore') && bot.canDigBlock(o)) {
        const ot=o.position.offset(0.5,0.5,0.5); await smoothLookAt(ot,0.0,5,false); await sleep(650);
        if (aimAngle(ot).ang < CONE_MINE && losClear(ot,false)) { const vz=vizOf(ot.x,ot.y,ot.z); try{ bot.swingArm('right'); await bot.dig(o); rec('mine',o.name,undefined,vz); }catch(_){} }
      }
    }
    // Climb back to the surface before the phase's closing survey. Ending the session deep in the
    // shaft made the last ~12 s frame a single tunnel-wall block (100% one-block frames on the
    // tail); returning to open ground gives an informative final shot instead.
    const su = surfaceOf(q.x, q.z);
    if (su) { bot.chat(`/tp Builder ${q.x + 0.5} ${su.position.y + 1} ${q.z + 0.5}`); await sleep(900); await lookYaw(0); }
    log('MINE_DONE');
  }

  while (!fs.existsSync(GO)) await sleep(200);
  T0 = Date.now();   // t=0 of the ledger; the capture side records its own GO offset
  const only = (process.env.P1_PHASES||'').split(',').filter(Boolean);
  // Match P1_PHASES against the BASE name: phases on laps 2+ are prefixed ('lap2_forest'), and
  // comparing the prefixed name would silently skip every phase of every extra lap.
  const phase = async (n,f)=>{ const base = n.replace(/^lap\d+_/, '');
    if(only.length && !only.includes(base)){ log('PHASE-SKIP '+n); return; }
    log('PHASE '+n); try{await f();}catch(e){log('PHASE-ERR '+n+' '+e.message);} };

  const LAPS = Math.max(1, parseInt(process.env.P1_LAPS || '1', 10));

  // Start in a fresh forest (the shared dev world has old builds near spawn).
  await phase('start', async()=>{
    if (!await tpToBiome('forest')) await landDry(bot.entity.position.x, bot.entity.position.z);
    await survey(6,600);
  });
  // Mob roster: ONLY mobs this renderer actually draws (audited 2026-07-22 —
  // see MOB_RENDER_AUDIT.md). Hostiles, villagers, foxes, rabbits, horses and llamas are
  // invisible here, so scoring a kill on them would be unfair; they are excluded.
  for (let lap = 0; lap < LAPS; lap++) {
    const L = lap === 0 ? '' : 'lap' + (lap + 1) + '_';
    log('LAP ' + (lap + 1) + '/' + LAPS);
    await phase(L + 'forest', async()=>{ await gatherCategory('wood',4); await gatherCategory('leaves',3);
      await huntMelee('cow'); await huntMelee('pig'); await huntMelee('sheep'); await survey(4,600); });
    await phase(L + 'build_village', async()=>{
      // build on open terrain, not among the trees we were just chopping
      if(!await tpToBiome('plains')) await tpToBiome('savanna');
      await survey(4,500);
      await buildHouse(lap);
      bot.chat('/summon minecraft:iron_golem ~ ~1 ~5'); await sleep(1500);   // village guardian
      await survey(6,700); });
    await phase(L + 'combat_showcase', async()=>{ await huntMelee('chicken'); await huntBow('cow');
      await huntMelee('wolf'); await huntBow('pig');
      // Hostiles render only on the real Java client; on the authentic path fight the classics too.
      if (HOSTILES) { bot.chat('/time set night'); await sleep(400);
        await huntMelee('zombie'); await huntBow('skeleton'); await huntMelee('spider');
        await huntMelee('creeper'); await huntBow('husk');
        bot.chat('/time set day'); await sleep(400); }
      await gatherCategory('grass',3); });
    await phase(L + 'beach', async()=>{ if(await tpToBiome('beach')){ await survey(6,600);
      await gatherCategory('sand',4,120); await gatherCategory('grass',2,120);
      await huntMelee('turtle'); await boatRide(); await huntBow('cow'); await huntMelee('pig'); } });
    await phase(L + 'desert', async()=>{ if(await tpToBiome('desert')){ await survey(6,600);
      await gatherCategory('sand',4,120); await gatherCategory('cactus',2,120); await gatherCategory('sandstone',3,120);
      if (EXTRA_BUILDS && lap === 0) await buildDesertTemple();
      await huntMelee('sheep'); await huntBow('chicken');
      if (HOSTILES) { bot.chat('/time set night'); await sleep(400); await huntMelee('husk'); await huntBow('skeleton'); bot.chat('/time set day'); await sleep(400); } } });
    await phase(L + 'snowy', async()=>{ if(await tpToBiome('snowy_tundra')){ await survey(6,600);
      await gatherCategory('snow',4,120); await gatherCategory('ice',2,120);
      await huntBow('cow'); await huntMelee('pig'); await huntMelee('mooshroom'); } });
    await phase(L + 'jungle', async()=>{ if(await tpToBiome('jungle')){ await survey(6,600);
      await gatherCategory('wood',4,120); await gatherCategory('leaves',3,120);
      await huntMelee('panda'); await huntBow('mooshroom'); } });
    await phase(L + 'plains', async()=>{ if(await tpToBiome('plains')){ await survey(6,600);
      await gatherCategory('grass',3,120); await gatherCategory('wood',3,120);
      await buildWell();
      await huntBow('polar_bear'); await huntMelee('pig'); await huntMelee('chicken'); } });
    await phase(L + 'savanna', async()=>{ if(await tpToBiome('savanna')){ await survey(6,600);
      await gatherCategory('wood',3,140); await gatherCategory('grass',3,140);
      await huntMelee('cow'); await huntBow('sheep'); await huntMelee('mooshroom'); } });
    await phase(L + 'badlands', async()=>{ if(await tpToBiome('badlands')){ await survey(6,600);
      await gatherCategory('redsand',4,160); await gatherCategory('terracotta',4,160);
      await buildTower();
      await huntMelee('mooshroom'); await huntBow('sheep'); } });
  }
  await phase('mine', async()=>{ await digMine(); await survey(4,700); });

  await sleep(1200); log('PLAY_DONE '+events.length); fs.writeFileSync(DONE, String(events.length));
});
