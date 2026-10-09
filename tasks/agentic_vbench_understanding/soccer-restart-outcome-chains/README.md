# soccer-restart-outcome-chains

An `agentic_vbench_understanding` task in the Harbor task layout. Over the full broadcast
of one Bundesliga match, Borussia Dortmund 6-2 Bayer 04 Leverkusen from the 2016-17 season,
the agent writes the match's **action ledger**: every visible action of the seventeen
classes SoccerNet-v2 annotates, 216 in this match, each with the moment it happens and the
team that performs it. Spotting one action is the easy part. The ledger needs all of them,
the team held consistent for 107 minutes, and classes told apart by what surrounds the
moment: a free kick is direct only with a shot or a wall, a foul belongs to the side that
commits it, and a clearance is a goalkeeper's kick.

Task Proposal issue: PhiloLabs/agentic-vbench #50. First merged in #51, where it asked about
restarts only; the task keeps that name.

## Media

The clip is the Bundesliga's own full-game upload on YouTube, `U-Glif5abSY`, fetched as
format 136: 1280x720 H.264 at 25 fps, video only, 6426.52 s and 1,836,710,763 bytes, SHA256
`7648b622c196ca5c844eb6162dfda2532d8e46ced99728f720f62fb6d3d695e2`. It is baked exactly as
served, with no re-encode, trim or remux, so anyone with yt-dlp can re-derive the digest.
`environment/Dockerfile` fetches it with a pinned yt-dlp, and `MATERIALS_URL` can point the
build at a mirror of the same bytes. The digest check is the same either way.

## Why the match and the question changed

The version merged in #51 used Mainz 05 1-1 Borussia Dortmund. The only full-length copy of
that match is SoccerNet's, which is distributed under an NDA that forbids sharing it, so its
Dockerfile could only ever hold a placeholder. This version moves to a SoccerNet-v2 match
whose full broadcast the league has published itself.

The question grew too. Asked only for restarts, a Codex run inside the built image scored
0.3529 against the family's 0.10 ceiling, almost all of it on throw-ins, and that prompt gave
free kicks their rulebook meaning where SoccerNet's labels mean shot intent. The ledger
replaced it. The ledger's tolerance is 1 s, the tightest window SoccerNet's own tight
average-mAP uses, tightened after the ledger's first runs. `SPEC.md` and
`calibration/scores.md` say where each earlier version and its runs are archived.

## Layout

```
soccer-restart-outcome-chains/
  SPEC.md                         filled-in Spec Card, every claim with its measured number
  task.toml                       settings, resources, time limits
  environment/Dockerfile          bakes the digest-checked broadcast at build time
  steps/solve/
    instruction.md                the agent prompt, class definitions, output schema
    workdir/setup.sh              stages the baked video into /workspace/materials
    solution/solve.sh             the oracle, which writes the verified ledger
    tests/judge.py                deterministic per-class F1 scorer and the key
    tests/test.sh                 verifier entry point
  calibration/
    scores.md                     every arm, how it was run, and what its trajectory shows
    rollouts/                     each arm's trajectory, solution, reward, manifest and audit
    arm_protocol.py               the budget, resources, capacity check and lock arms share
    run_in_image.py               runs the Codex and Claude Code arms inside the task image
    run_antigravity.py            runs the Antigravity arm inside the task image under Harbor
    harbor_agents.py              the Antigravity arm's Harbor adapter, with the subagent hook
    antigravity_hooks.json        the hook that keeps the Antigravity arm to one agent
    probe_antigravity_hook.py     checks that hook in both directions
    antigravity_in_image.md       what that Harbor path needs beyond the stock adapter
    budget_watchdog.py            stops an arm at its budget from outside the runner
    run_oracle_empty.py           grades the oracle and an empty submission inside the image
    make_prompts.py               checks that the calibration prompt is the shipped prompt
    ship_arm.py, ship_rollout.py  sanitize a finished arm and file it under rollouts/
    audit_trajectory.py           counts tool calls and looks for shortcuts in a trajectory
    verify_scores.py              recomputes every number the documents assert
  provenance/                     how the ground truth is built, not part of the run
    data_setup/                   fetch the pinned labels and the video, digests checked
    align_halves.py               places each SoccerNet half on the clip's timeline
    alignment.json                the two offsets and the evidence for them
    build_gt.py                   Labels-v2.json to the key, mechanically
    dortmund_leverkusen.labels-derived.json   the 216-action key, mirrored by judge.py
    ablations/                    deterministic baselines and the measured degraded-input runs
    superseded-restart-contract/  the restart version's prompt, scorer and ablations
    superseded-2s-tolerance/      the ledger's 2 s prompt, scorer and ablations
    superseded-pooled-f1/         the scorer that pooled every entry into one F1
```

## Clears the bar (measured)

| check | result |
|---|---|
| oracle, inside the built image | 1.0 |
| empty submission, inside the built image | 0.0 |
| most common pair repeated 216 times over the halves, no media | 0.0041 |
| random pairs from the key's distribution, mean of 400 | 0.0039 |
| the same, best of 400 | 0.0511 |
| prompt only, GPT 5.6 Sol, no tools | 0.0000 |
| one still at t = 1786, GPT 5.6 Sol, no tools | 0.0000 |
| 128 frames on 8 contact sheets, GPT 5.6 Sol, no tools | 0.0000 |
| Codex, GPT 5.6 Sol | 0.0663 |
| Claude Code, Opus 4.8 | 0.0901 |
| Antigravity, Gemini 3.6 Flash | 0.0333 |

See `SPEC.md` and `calibration/scores.md`.

## Scoring rule

**F1 per action class, averaged over the classes in the key.** A predicted `(t, action, team)`
is a true positive when a key entry with the same `action` and `team` lies within 1 second of
it, each key entry matched at most once. Inside each (action, team) group a greedy pass in
time order finds a largest matching, which `provenance/build_gt.py` checks against brute
force. Each class gets an F1 from its own true positives, entries and key entries, and the
reward is the mean over the fourteen classes this match's key contains, the way SoccerNet
averages over classes. Kick-off, with one visible action, weighs as much as Ball out of play
with 62. Pure Python stdlib, no VLM or LLM judge. The key is hardcoded in `judge.py` and
mirrors the mechanical build in `provenance/build_gt.py`.

## Ground-truth provenance

Every entry is a deterministic transform of SoccerNet-v2's published, multi-annotator
`Labels-v2.json` for this match, which is public and needs no NDA.

- `action` is the annotation's own label, one of SoccerNet-v2's seventeen classes, and the
  prompt defines each class the way SoccerNet's annotation guidelines do.
- `team` is the annotation's team, the side that performs the action, written `none` for
  Ball out of play, the one class SoccerNet marks as belonging to no team.
- `t` is the annotation's `position` placed on the clip. SoccerNet times each event inside
  its half video, and the clip is a different recording of the same broadcast, so each half
  gets one offset: 350.006 s for the first and 3396.705 s for the second.
  `provenance/align_halves.py` measures both from SoccerNet's own shot-change log against
  ffmpeg's scene score, and `provenance/alignment.json` keeps the evidence.
- Only annotations with `visibility == "visible"` are kept, 216 of the match's 260.

`provenance/build_gt.py` asserts that the derived key equals `judge.py`'s and `solve.sh`'s
and that the oracle scores 1.0.

## Reproduce

```bash
python3 provenance/data_setup/fetch_labels.py --out labels
bash provenance/data_setup/fetch_video.sh media
python3 provenance/align_halves.py --video media/game.mp4 --cameras labels/Labels-cameras.json \
    --scores scene_scores.txt --out alignment.json
python3 provenance/build_gt.py --labels labels/Labels-v2.json --alignment alignment.json \
    --clip-duration-sec 6426.52 --out gt.json
python3 provenance/ablations/run_ablations.py --gt provenance/dortmund_leverkusen.labels-derived.json
python3 calibration/verify_scores.py
```
