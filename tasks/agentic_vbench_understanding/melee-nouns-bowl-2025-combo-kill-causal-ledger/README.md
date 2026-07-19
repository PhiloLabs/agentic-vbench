# Nouns Bowl 2025 Melee Combo-and-Kill Causal Ledger

This task reconstructs 104 qualifying punish conversions across ten Super Smash
Bros. Melee games. The input is a 25-minute anthology of three public Nouns Bowl
2025 set VODs. Ground truth is generated independently from the corresponding
public Slippi replay files, not from OCR or manual transcription of the broadcast.

## Public sources

Set VODs from [The Melee Archive](https://www.youtube.com/@TheMeleeArchive):

| games | set | public VOD |
|---:|---|---|
| 1-3 | Ferriswheel vs Zain | <https://www.youtube.com/watch?v=3VJYGJ3KrZM> |
| 4-6 | JoJo vs Bard | <https://www.youtube.com/watch?v=tmZTwrLVceI> |
| 7-10 | Axe vs SRM13 | <https://www.youtube.com/watch?v=44jQnPR24zM> |

The videos identify Nouns Bowl 2025 and the players. The event bracket linked by
the uploader is <https://www.start.gg/tournament/nouns-bowl-2025>.

Replay files come from the public [Lunar Melee Database](https://lunarmelee.com/database).
They are available through the site's public replay endpoint with these IDs:

| games | Lunar replay IDs | replay stage sequence |
|---:|---|---|
| 1-3 | `69beac275febbbc18f6b02a4`, `69beac275febbbc18f6b02a5`, `69beac275febbbc18f6b02a6` | Battlefield, Dream Land, Dream Land |
| 4-6 | `69beac275febbbc18f6b02b7`, `69beac275febbbc18f6b02b8`, `69beac275febbbc18f6b02b9` | Battlefield, Fountain of Dreams, Fountain of Dreams |
| 7-10 | `69beac275febbbc18f6b0285`, `69beac275febbbc18f6b0286`, `69beac275febbbc18f6b0287`, `69beac275febbbc18f6b0288` | Battlefield, Pokemon Stadium, Dream Land, Dream Land |

For example, a replay is fetched from
`https://lunarmelee.com/api/download?action=replay&replayId=REPLAY_ID`.

The replay metadata matches each VOD's two player tags and characters. The ten-game
stage order was also checked visually against the VODs. This prevents the common
failure mode of attaching machine truth from a different game with the same matchup.

## Media construction

The Docker build downloads YouTube adaptive format `itag 298` for each source,
checks each digest, and concatenates the three H.264 video-only streams without
re-encoding. `MATERIALS_URL` can override this process when the exact final bytes are
re-hosted at a stable direct URL. The agent receives only the resulting
`/workspace/materials/match.mp4`; it does not receive replay files or this README.

| artifact | bytes | SHA256 |
|---|---:|---|
| `ferriswheel-zain.mp4` | 146,426,861 | `4b9a6da0b6ee68488e2eb32a90fb3319d17b1f7bb1245c437d63dedfba462ec4` |
| `jojo-bard.mp4` | 202,671,526 | `d726413360a809da8a72ec0289c9ab731b9e2b98a4dbee8562e7fe3b3bc9f7d2` |
| `axe-srm13.mp4` | 261,562,993 | `af05250e0c2f7ff9744968a6a1df13bed8de83d6d66db72b731912ad61fe0a01` |
| concatenated `match.mp4` | 610,171,132 | `02f18fd7f4796800eece0400b1b1f315a36778b57b9ef4a64d1b30aa3b539749` |

The local concatenated digest above was produced with FFmpeg 7.1. Container builds
pin and verify the three source representations; their decoded concatenation is
stable, although MP4 container bytes may differ across FFmpeg muxer versions. A
direct `MATERIALS_URL` override must match the listed final digest.

The source pages do not advertise an open redistribution license. This task keeps
large media out of version control and downloads the public representations during
the image build. Benchmark publication still requires the organizer's normal media
rights review; public accessibility alone is not asserted to grant redistribution
rights.

## Ground truth

`tools/build_ground_truth.js` uses `@slippi/slippi-js` 9.1.2. A conversion is
retained when it contains at least four damage-producing contacts or ends in a stock
loss. The script derives hit count, starting stock, summed damage band, and terminal
cause from frame state. An overlapping counter-conversion marks `reversal`; a stock
loss marks `kill`; all other completed conversions mark `escape`. Unfinished
non-kill conversions at a replay boundary are excluded.

The scored key is verifier-side at `steps/solve/tests/ground_truth.json`.
`tools/ground_truth_audit.json` records replay hashes, metadata, frames, exact damage,
moves, and derivation for all 104 accepted events.

Rebuild from downloaded replay files:

```bash
cd tools
pnpm install --frozen-lockfile
node build_ground_truth.js \
  --replay-dir /path/to/replays \
  --ground-truth ../steps/solve/tests/ground_truth.json \
  --audit ground_truth_audit.json
```

## Why OCR is insufficient

The broadcast overlay exposes player tags, timer, stocks, and the current percent.
It does not expose conversion boundaries, the 45-frame actionable reset, the count
of damaging contacts inside multi-hit moves and pummels, summed conversion damage,
or whether a non-kill sequence ended by escape or an overlapping reversal. OCR can
help locate games, but cannot produce the event ledger without temporal gameplay
analysis.

## Validation

Run deterministic scorer regression tests with:

```bash
python3 tools/test_judge.py
```

Three retained local agent outputs have been scored by the formal verifier:

| harness | reward | auditable tool calls |
|---|---:|---:|
| Codex Desktop (`gpt-5.6-sol`, high) | 0.0899 | 145 |
| Claude local agent (`claude-sonnet-5`) | 0.0 | 83 |
| Antigravity (model metadata unavailable) | 0.0169 | 90 |

See `calibration/scores.md` for diagnostics, counting rules, and qualification
caveats. These are the final results reported by this submission. The runs were
outside the shipped Harbor image, and no measured anti-shortcut ablation results are
claimed.
