# Anti-shortcut ablations and retained trajectories

Five degraded-input rollouts, each the same prompt and model family as the
required Codex row with one input channel removed. All five score 0.0000 under
the shipped judge.

| ablation | reward | clearances submitted | matched | full-credit | ledger |
|---|---:|---:|---:|---:|---|
| no media | 0.0000 | 0 | 0 | 0 | `ledgers/no-media.json` |
| one frame | 0.0000 | 0 | 0 | 0 | `ledgers/single-frame.json` |
| video only | 0.0000 | 56 | 37 | 0 | `ledgers/video-only.json` |
| audio only | 0.0000 | 65 | 63 | 0 | `ledgers/audio-only.json` |
| frame dump + transcript, no media tools | 0.0000 | 65 | 63 | 0 | `ledgers/frame-dump-no-tools.json` |

`matched` counts clearances that matched an expected one on command type and
issue time; `full-credit` counts those that earned every available unit. A row
can match all 65 and still score 0.0000 — matching is what makes a clearance
gradable, not what earns credit.

Reproduce the whole table, including the required-agent rows:

```bash
python3 calibration/rescore_ledgers.py
```

Audio-only is the row that mattered. Under the first revision of the scorer it
returned 0.0031 and beat every run that included video — the inversion the
maintainer flagged. It is now 0.0000, because the judge discounts each
clearance by what a transcript alone could have said about it and lets a
below-ceiling clearance subtract rather than clip. Its 63 matched clearances are
still there, and it still earns 252 of 260 target units from the spoken numbers
alone — but only 86 of 260 instrument-snapshot units, which is the part a
transcript cannot supply. It no longer clears the bar a transcript sets for
itself.

## Ledger provenance

`ledgers/*.json` are what these agents actually submitted. The calibration
policy at the time kept trajectories rather than duplicate solution sidecars, so
all five had to be recovered from the retained trajectory. Four are verbatim
payloads; one is a replay, and is labelled as such:

- **no-media**, **single-frame** — the agent wrote `{"clearances": []}` through
  its patch tool; the payload is in the trajectory verbatim.
- **audio-only** — the agent wrote `output/generate_solution.py` through its
  patch tool and ran it. That script is in the trajectory verbatim and is
  deterministic, so re-running it untouched reproduces the submitted file.
- **frame-dump-no-tools** — the agent wrote `output/solution.json` directly
  through its patch tool; the payload is in the trajectory verbatim.
- **video-only** — the only one not directly recoverable, and therefore the one
  weakest claim in this directory. This agent built its ledger from a numpy
  array it had computed in the container's `/tmp`, so the trajectory holds the
  recipe but not the result. Its 38 retained shell commands are deterministic
  and read nothing but the video, so they were replayed in order against a
  video-only cut of the same media. The replay produced 56 clearances, matching
  the 1404-line file the agent is seen viewing in its own trajectory. This is a
  reconstruction, not the agent's own bytes: the area policy asks for a real
  measured run, and a replay only satisfies that to the extent the recipe is
  deterministic. It scores 0.0000, as does every other degraded row, so nothing
  in the anti-shortcut conclusion rests on it alone.

Storing the sidecars is the fix going forward; see `../rollouts/README.md`.

## Retained trajectories

Full raw harness trajectories for the five ablations and for both replaced
rounds are published as hash-pinned release assets rather than committed —
13,085,971 bytes as shipped (gzipped), 31,160,204 bytes uncompressed:

<https://github.com/JordanPeng/agentic-vbench/releases/tag/flightgear-calibration-20260827>

The same release also carries the native Claude row's unmodified trajectory,
which is condensed in the repository; that asset and its hashes are documented
in `../rollouts/README.md` rather than here.

```text
88e1b9b5d6559251b95511dd792d2ab3508835cdeeaf602db1b7a0ced401468e  ablation-audio-only_gpt-5.6-sol.jsonl.gz
9e1e058f03ae9b080adb58e66aac28ce023408f96ff51b85c11172ebd6b163c6  ablation-frame-dump-no-tools_gpt-5.6-sol.jsonl.gz
41e8fcb97e4b71d2cd5918384ab2e3583f519c49c4c23cdcce1523fb46085e0f  ablation-no-media_gpt-5.6-sol.jsonl.gz
205dbf6ad4818a26943ebc4b94c4d393271abe2acef1439740a163b8e5526a67  ablation-single-frame_gpt-5.6-sol.jsonl.gz
45220858a26eafebc0249dfb033a8e074a4aa63d0d42207e0b19daa0cf596293  ablation-video-only_gpt-5.6-sol.jsonl.gz
19d1f3b2290816ec32548647f54508bb0d84357c915949f9912d4750ac5dffda  replaced-round_antigravity-gemini-3.6_20260812T203542Z-resource-exhausted.jsonl.gz
ca0d640092efdde2942d4e7108e7f14eedaaadf3ed0e70e1fdf395e90dd2a551  replaced-round_claude-opus-4.8-agent-host-parity.jsonl.gz
```

Required-harness trajectories stay in the repository, under
`../rollouts/`.

The release is hosted on the contributor fork (`JordanPeng/agentic-vbench`)
because that is where the PR branch lives. That makes a merged task depend on a
single contributor's account for its evidence. All seven assets are public and
their hashes verify against the list above, so the content is pinned rather than
trusted — but if the maintainers would rather the assets live upstream or in
LFS, say so and they will be re-hosted; the hashes will not change.

## Replaced rounds

Two rounds were replaced. Both are in the release above, so each claim below is
checkable rather than asserted.

**`antigravity-gemini-3.6`, replaced for failure.** Started 2026-08-12T20:35:42Z
and stopped on a provider resource-exhausted error partway through media
extraction, before producing any ledger. Re-run to completion on 2026-08-13, and
that completed run is the reported Antigravity row. Nothing about the task, the
prompt, or the media changed between the two.

**`claude-opus-4.8`, replaced for harness parity.** The original round ran Opus
4.8 through a VS Code Copilot agent-host whose wrapper prompt added solving
guidance the other harnesses never saw — the `copilotUsage`/AHP metadata and the
wrapper text are both in the released trajectory. It was re-run natively as
`claude -p` on the shipped `instruction.md` and nothing else; that native run is
the reported Claude row. The task, prompt, and media are unchanged apart from the
scorer revision in this PR, which was applied to every row alike. See
`../scores.md` for both scores side by side.

