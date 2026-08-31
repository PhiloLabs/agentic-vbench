// Probe what actually works on a 1.20.4 server before spending a full authentic session on it.
// The first authentic run recorded 0 events; this isolates which primitive broke.
const mineflayer = require('mineflayer');
const PORT = parseInt(process.env.MC_PORT || '25590', 10);
const VER = process.env.MC_VERSION || '1.20.4';
const bot = mineflayer.createBot({host:'localhost', port:PORT, username:'Probe', version:VER, auth:'offline'});
const s = ms => new Promise(r => setTimeout(r, ms));
function chatOnce(cmd, re, ms=8000) {
  return new Promise(res => {
    const h = m => { const j = JSON.stringify(m.json||m); if (re.test(j)) { bot.removeListener('message',h); res(j.slice(0,220)); } };
    bot.on('message', h); bot.chat(cmd); setTimeout(()=>{bot.removeListener('message',h); res(null);}, ms);
  });
}
bot.once('spawn', async () => {
  console.log('SPAWN at', bot.entity.position.floored(), 'ver', bot.version);
  bot.chat('/gamerule doTileDrops false'); await s(500);
  // 1) which locate syntax does this server accept?
  const oldSyntax = await chatOnce('/locatebiome minecraft:forest', /locate|nearest|Unknown|Incorrect/i);
  console.log('OLD /locatebiome ->', oldSyntax);
  const newSyntax = await chatOnce('/locate biome minecraft:forest', /locate|nearest|Unknown|Incorrect/i);
  console.log('NEW /locate biome ->', newSyntax);
  // 2) does a summon produce a findable entity?
  for (const mob of ['cow','pig','sheep','chicken']) {
    bot.chat(`/summon minecraft:${mob} ~ ~1 ~3`); await s(1500);
    const e = Object.values(bot.entities).find(x => x && x.name === mob);
    console.log('SUMMON', mob, e ? `FOUND at ${e.position.floored()}` : 'MISS',
                '| entity names nearby:', [...new Set(Object.values(bot.entities).map(x=>x&&x.name).filter(Boolean))].slice(0,8).join(','));
  }
  // 3) can we dig, and what is the surface block called?
  const p = bot.entity.position.floored();
  const under = bot.blockAt(p.offset(0,-1,0));
  console.log('SURFACE', under && under.name);
  bot.chat(`/setblock ${p.x+2} ${p.y} ${p.z} minecraft:oak_log`); await s(800);
  const t = bot.blockAt(p.offset(2,0,0));
  console.log('SETBLOCK ->', t && t.name, 'canDig', t && bot.canDigBlock(t));
  if (t && bot.canDigBlock(t)) { try { await bot.dig(t); console.log('DIG_OK'); } catch(e){ console.log('DIG_FAIL', e.message); } }
  console.log('PROBE_DONE'); process.exit(0);
});
bot.on('error', e => { console.log('PROBE_ERR', e.message); process.exit(1); });
setTimeout(()=>{console.log('PROBE_TIMEOUT');process.exit(2);}, 120000);
