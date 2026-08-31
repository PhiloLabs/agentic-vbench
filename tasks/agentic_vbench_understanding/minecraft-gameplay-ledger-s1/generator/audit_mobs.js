// Mob-render audit: stand on a clean stone platform built at the bot's OWN column (so the
// chunk is guaranteed loaded — /fill silently fails in unloaded chunks) and show each
// candidate mob 3 blocks in front for HOLD_MS. Purpose: find which mobs prismarine-viewer
// draws recognizably; a mob rendered as an untextured magenta box would make the video
// ledger unsolvable and must be dropped from the task vocabulary.
const fs = require('fs');
const mineflayer = require('mineflayer');
const { mineflayer: mineflayerViewer } = require('prismarine-viewer');

const GO = process.argv[2], DONE = process.argv[3];
const LOG = process.env.LOG || 'audit_mobs.log';
const log = m => { try { fs.appendFileSync(LOG, m + '\n'); } catch (_) {} };
process.on('uncaughtException', e => log('UNCAUGHT ' + (e && e.stack || e)));

const MOBS = ['cow','pig','sheep','chicken','rabbit','wolf','fox','llama','mooshroom',
  'horse','cat','ocelot','polar_bear','turtle','panda','bee','villager','iron_golem',
  'zombie','skeleton','creeper','spider','enderman','witch','pillager','slime','squid'];
const HOLD_MS = 6000;

const bot = mineflayer.createBot({ host:'localhost', port:25577, username:'Builder', version:'1.16.5', auth:'offline' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
bot.on('error', e => log('ERR ' + e.message));

bot.once('spawn', async () => {
  mineflayerViewer(bot, { port:3009, firstPerson:true, viewDistance:4 });
  bot.chat('/gamemode creative'); bot.chat('/gamerule doMobSpawning false'); bot.chat('/gamerule doTileDrops false');
  bot.chat('/gamerule doDaylightCycle false'); bot.chat('/time set noon'); bot.chat('/weather clear');
  await sleep(800);
  bot.chat('/tp Builder ~ 120 ~');                                   // same column => loaded
  await sleep(2000);
  bot.chat('/fill ~-7 ~-2 ~-7 ~7 ~-2 ~7 minecraft:smooth_stone');    // platform under us
  bot.chat('/fill ~-7 ~-1 ~-7 ~7 ~4 ~7 minecraft:air');              // clear the space
  await sleep(2500);
  const p = bot.entity.position;
  log('STANDING ' + [Math.floor(p.x), Math.floor(p.y), Math.floor(p.z)]);

  while (!fs.existsSync(GO)) await sleep(200);
  const CUR = process.argv[4];   // marker file: capture side screenshots when this changes
  for (const m of MOBS) {
    bot.chat('/kill @e[type=!player,distance=..25]');
    await sleep(500);
    const b = bot.entity.position.floored();
    bot.chat(`/summon minecraft:${m} ${b.x + 0.5} ${b.y} ${b.z + 3.5}`);
    await sleep(1200);
    // Track the mob with the camera, exactly as the player does while fighting it — mobs
    // that flee or charge to point-blank are otherwise never in frame.
    const ent = Object.values(bot.entities).find(e => e.name === m && e.position.distanceTo(bot.entity.position) < 12);
    const track = async () => {
      const t = ent && Object.values(bot.entities).find(e => e.id === ent.id);
      const at = (t && t.isValid) ? t.position.offset(0, 0.4, 0) : bot.entity.position.offset(0, 0.1, 3);
      try { await bot.lookAt(at, true); } catch (_) {}
    };
    await track(); await sleep(500); await track();
    fs.writeFileSync(CUR, m);       // mob summoned and framed
    log('SHOWING ' + m + (ent ? '' : ' NO_ENTITY'));
    while (fs.readFileSync(CUR, 'utf8') === m) { await track(); await sleep(150); }
  }
  bot.chat('/kill @e[type=!player,distance=..25]');
  fs.writeFileSync(DONE, 'ok');
  log('AUDIT_DONE');
});
