#!/usr/bin/env node
"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const { SlippiGame, characters, moves, stages } = require("@slippi/slippi-js/node");

const GAMES = [
  {
    file: "ferriswheel-zain-g1.slp",
    replayId: "69beac275febbbc18f6b02a4",
    sha256: "b9ffae237ee3c4a4577ccdd4e41b8228a6d404967c18a4b2c303e0eee04edc16",
    startedAt: "2025-04-26T19:57:34.014Z",
    stage: "Battlefield",
    players: [["Ferriswheel", "Falco"], ["Zain", "Marth"]],
  },
  {
    file: "ferriswheel-zain-g2.slp",
    replayId: "69beac275febbbc18f6b02a5",
    sha256: "0278ffa2a20bb950b4f3e49b511b570f069ddefc34f3c25bb81b79f5e8514f83",
    startedAt: "2025-04-26T19:59:55.014Z",
    stage: "Dream Land N64",
    players: [["Ferriswheel", "Falco"], ["Zain", "Marth"]],
  },
  {
    file: "ferriswheel-zain-g3.slp",
    replayId: "69beac275febbbc18f6b02a6",
    sha256: "3eaaae87bc6241cc95cf8ed1b4812cc4e375f0a69424c83713f47149fb2cf752",
    startedAt: "2025-04-26T20:02:24.014Z",
    stage: "Dream Land N64",
    players: [["Ferriswheel", "Falco"], ["Zain", "Marth"]],
  },
  {
    file: "jojo-bard-g1.slp",
    replayId: "69beac275febbbc18f6b02b7",
    sha256: "6e3ec0ff1cc9233100794f5fc9361d633695a1f5fef25fc874fbb1ec562243fe",
    startedAt: "2025-04-26T22:47:37.220Z",
    stage: "Battlefield",
    players: [["JoJo", "Captain Falcon"], ["Bard", "Fox"]],
  },
  {
    file: "jojo-bard-g2.slp",
    replayId: "69beac275febbbc18f6b02b8",
    sha256: "a1bd4322afbf45e780cd5428d0e49c1506f36fd2df0c5a638d93cacddd97efd1",
    startedAt: "2025-04-26T22:51:17.220Z",
    stage: "Fountain of Dreams",
    players: [["JoJo", "Captain Falcon"], ["Bard", "Fox"]],
  },
  {
    file: "jojo-bard-g3.slp",
    replayId: "69beac275febbbc18f6b02b9",
    sha256: "80ab7e1d94590044fd035506967f136e0ce6a726cf28fff05cacf090cc41b2cd",
    startedAt: "2025-04-26T22:53:44.220Z",
    stage: "Fountain of Dreams",
    players: [["JoJo", "Captain Falcon"], ["Bard", "Fox"]],
  },
  {
    file: "axe-srm13-g1.slp",
    replayId: "69beac275febbbc18f6b0285",
    sha256: "1ee5675517ef6ac08534b9c6f61cdd1413a988b1333d424f474eae64fd9a7443",
    startedAt: "2025-04-26T22:44:59.063Z",
    stage: "Battlefield",
    players: [["Axe", "Pikachu"], ["SRM13", "Jigglypuff"]],
  },
  {
    file: "axe-srm13-g2.slp",
    replayId: "69beac275febbbc18f6b0286",
    sha256: "41a9fba9921f83a571be2ec6f0d26a4ae8b4060267d8555a34255f218b1e7096",
    startedAt: "2025-04-26T22:48:29.063Z",
    stage: "Pokémon Stadium",
    players: [["Axe", "Fox"], ["SRM13", "Jigglypuff"]],
  },
  {
    file: "axe-srm13-g3.slp",
    replayId: "69beac275febbbc18f6b0287",
    sha256: "005007b9b6fb3ddf939dd667373f46b9cf5ec3d15d5c678047d9eb5c1fce761a",
    startedAt: "2025-04-26T22:50:40.063Z",
    stage: "Dream Land N64",
    players: [["Axe", "Fox"], ["SRM13", "Jigglypuff"]],
  },
  {
    file: "axe-srm13-g4.slp",
    replayId: "69beac275febbbc18f6b0288",
    sha256: "ef8ed9b9e64e27a3dfb1c70408f1c95b2963a1e3644fdea714dc8889439e138a",
    startedAt: "2025-04-26T22:53:24.063Z",
    stage: "Dream Land N64",
    players: [["Axe", "Fox"], ["SRM13", "Jigglypuff"]],
  },
];

const VIDEO_SOURCES = [
  {
    games: [1, 3],
    video_id: "3VJYGJ3KrZM",
    title: "Ferriswheel vs Zain - Nouns Bowl 2025 - Winners Round 2",
    bytes: 146426861,
    sha256: "4b9a6da0b6ee68488e2eb32a90fb3319d17b1f7bb1245c437d63dedfba462ec4",
    duration_seconds: 382,
    stage_sequence: ["Battlefield", "Dream Land N64", "Dream Land N64"],
  },
  {
    games: [4, 6],
    video_id: "tmZTwrLVceI",
    title: "JoJo vs Bard - Nouns Bowl 2025 - Winners Round 2",
    bytes: 202671526,
    sha256: "d726413360a809da8a72ec0289c9ab731b9e2b98a4dbee8562e7fe3b3bc9f7d2",
    duration_seconds: 450.52,
    stage_sequence: ["Battlefield", "Fountain of Dreams", "Fountain of Dreams"],
  },
  {
    games: [7, 10],
    video_id: "44jQnPR24zM",
    title: "Axe vs SRM13 - Nouns Bowl 2025 - Winners Round 2",
    bytes: 261562993,
    sha256: "af05250e0c2f7ff9744968a6a1df13bed8de83d6d66db72b731912ad61fe0a01",
    duration_seconds: 676.67,
    stage_sequence: ["Battlefield", "Pokémon Stadium", "Dream Land N64", "Dream Land N64"],
  },
];

function parseArgs() {
  const args = process.argv.slice(2);
  const value = (flag, fallback) => {
    const index = args.indexOf(flag);
    return index === -1 ? fallback : args[index + 1];
  };
  return {
    replayDir: value("--replay-dir", "replays"),
    groundTruth: value("--ground-truth", "ground_truth.json"),
    audit: value("--audit", "ground_truth_audit.json"),
  };
}

function sha256(filePath) {
  return crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
}

function damageBand(damage) {
  if (damage < 25) return "light";
  if (damage < 50) return "heavy";
  return "devastating";
}

function conversionTerminal(conversion, conversions) {
  if (conversion.didKill) return "kill";
  const reversed = conversions.some((other) =>
    other !== conversion &&
    other.lastHitBy === conversion.playerIndex &&
    other.playerIndex === conversion.lastHitBy &&
    other.startFrame >= conversion.startFrame &&
    other.startFrame <= conversion.endFrame
  );
  return reversed ? "reversal" : "escape";
}

function validateGame(game, expected, filePath) {
  if (sha256(filePath) !== expected.sha256) {
    throw new Error(`SHA256 mismatch for ${expected.file}`);
  }
  const settings = game.getSettings();
  const metadata = game.getMetadata();
  const actualPlayers = [...settings.players]
    .sort((a, b) => a.playerIndex - b.playerIndex)
    .map((player) => [player.displayName, characters.getCharacterName(player.characterId)]);
  const actualStage = stages.getStageName(settings.stageId);
  if (metadata.startAt !== expected.startedAt || actualStage !== expected.stage) {
    throw new Error(`metadata mismatch for ${expected.file}`);
  }
  if (JSON.stringify(actualPlayers) !== JSON.stringify(expected.players)) {
    throw new Error(`player mismatch for ${expected.file}: ${JSON.stringify(actualPlayers)}`);
  }
  return { settings, metadata, actualPlayers, actualStage };
}

function round(value, digits = 3) {
  const scale = 10 ** digits;
  return Math.round(value * scale) / scale;
}

function main() {
  const args = parseArgs();
  const events = [];
  const auditGames = [];

  GAMES.forEach((expected, gameIndex) => {
    const filePath = path.join(args.replayDir, expected.file);
    const game = new SlippiGame(filePath);
    const checked = validateGame(game, expected, filePath);
    const stats = game.getStats();
    const frames = game.getFrames();
    const playerByIndex = new Map(
      checked.settings.players.map((player) => [player.playerIndex, player])
    );
    const accepted = [];

    for (const conversion of stats.conversions) {
      const hitCount = conversion.moves.reduce((sum, move) => sum + move.hitCount, 0);
      if (hitCount < 4 && !conversion.didKill) continue;
      if (!conversion.didKill && conversion.endFrame == null) continue;

      const attacker = playerByIndex.get(conversion.lastHitBy);
      const victim = playerByIndex.get(conversion.playerIndex);
      const startFrame = frames[conversion.startFrame];
      const victimPost = startFrame?.players?.[conversion.playerIndex]?.post;
      if (!attacker || !victim || !victimPost) {
        throw new Error(`missing conversion state in ${expected.file} at ${conversion.startFrame}`);
      }
      const damage = conversion.moves.reduce((sum, move) => sum + move.damage, 0);
      const terminal = conversionTerminal(conversion, stats.conversions);
      const scored = {
        game: gameIndex + 1,
        attacker: attacker.displayName,
        victim_stock_before: victimPost.stocksRemaining,
        hit_count: hitCount,
        damage_band: damageBand(damage),
        terminal,
      };
      events.push(scored);
      accepted.push({
        ...scored,
        victim: victim.displayName,
        start_frame: conversion.startFrame,
        end_frame: conversion.endFrame,
        start_game_seconds: round((conversion.startFrame + 123) / 60),
        end_game_seconds: round((conversion.endFrame + 123) / 60),
        damage: round(damage),
        opening_type: conversion.openingType,
        moves: conversion.moves.map((move) => ({
          frame: move.frame,
          name: moves.getMoveName(move.moveId),
          hit_count: move.hitCount,
          damage: round(move.damage),
        })),
      });
    }

    auditGames.push({
      game: gameIndex + 1,
      replay_file: expected.file,
      replay_id: expected.replayId,
      sha256: expected.sha256,
      started_at: checked.metadata.startAt,
      stage: checked.actualStage,
      players: checked.actualPlayers.map(([tag, character], index) => ({
        player_index: index,
        tag,
        character,
      })),
      last_frame: stats.lastFrame,
      all_conversions: stats.conversions.length,
      accepted_events: accepted,
    });
  });

  const groundTruth = { events };
  const audit = {
    schema_version: "1.0",
    generator: "@slippi/slippi-js 9.1.2",
    policy: {
      include: "hit_count >= 4 or didKill == true",
      exclude: "unfinished non-kill conversions",
      hit_count: "sum of move hitCount values in the Slippi conversion",
      damage: "sum of move damage values in the Slippi conversion",
      damage_bands: { light: "<25", heavy: "25 to <50", devastating: ">=50" },
      terminal: {
        kill: "Slippi conversion didKill is true",
        reversal: "the victim starts an overlapping conversion against the attacker",
        escape: "non-kill conversion with no overlapping reversal",
      },
    },
    video_sources: VIDEO_SOURCES,
    event_count: events.length,
    games: auditGames,
  };
  fs.writeFileSync(args.groundTruth, `${JSON.stringify(groundTruth, null, 2)}\n`);
  fs.writeFileSync(args.audit, `${JSON.stringify(audit, null, 2)}\n`);
  console.log(`wrote ${events.length} events from ${GAMES.length} games`);
}

main();
