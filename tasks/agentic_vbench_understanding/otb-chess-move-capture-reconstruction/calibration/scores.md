# Calibration Scores

This task is in post-review revision. The source has been replaced, and the new
104-ply move sequence and Black-win result have been human-verified. A fresh
natural-prompt, full-media Codex rollout passes the numerical hardness and
long-horizon gates. The required `single_frame` and `no_media` shortcut checks
also pass. A fresh Claude attempt hit its subscription limit before submission.
A fresh isolated, checkpointed Antigravity run now passes the numerical
hardness and long-horizon gates without online, package-installation, host
Python-library, or outside-workspace access. A fresh isolated, checkpointed
Claude rerun now also produces a valid scored submission and passes both gates.
Under the checkpoint-allowed protocol, Codex, Claude, and Antigravity all have
qualifying replacement-source rollouts.

| run | status | reward | notes |
|---|---:|---:|---|
| oracle | passed | 1.0 | Human-verified move sequence and result; 287/287 checks passed across 104 plies and 26 captures. |
| empty baseline | passed | 0.0 | Empty `moves` and `capture_events` submission; 0/287 checks passed. |
| [Codex CLI](rollouts/codex-transcript.jsonl) (`codex-natural-chess-20260719T062119Z`) | passed | 0.0379 | Fresh GPT-5.6 Sol full-media rollout using the benchmark prompt with path-only rewriting; 13/343 checks, 45/104 plies, 17/26 captures, and 237 completed shell calls. The agent naturally exceeded 50 calls with no turn minimum or pacing hint. It wrote temporary analysis frames outside the workspace but did not access ground truth or public game data. |
| [Claude Code CLI](rollouts/claude-transcript.jsonl) (`claude-checkpoint-chess-20260723T040025Z`) | passed; checkpointed | 0.0 | Fresh Sonnet 5 high-effort run in a clean replacement-source workspace. The canonical initial prompt used path-only rewriting; a content-free persistence checkpoint was sent after 45 observed completed results. Claude wrote and parsed a valid empty submission, continued to 54 completed tool results, and scored 0/287 with verifier reason `ok`. A pre-tool gate blocked one package-manager probe; no web, package installation, third-party Python package, outside-workspace, ground-truth, or prior-rollout access succeeded. |
| [Antigravity CLI](rollouts/antigravity-transcript.jsonl) (`antigravity-qualifying-chess-20260719T170155Z`) | passed; checkpointed | 0.0 | Fresh Gemini 3.5 Flash (Medium) run in a clean sandbox on the replacement source. Its canonical initial prompt used path-only rewriting; one content-free persistence checkpoint was sent after call 46. The agent wrote a valid empty submission, continued naturally, and was stopped after scoring at call 53; the transcript has 54 invocations and 51 conservative `DONE` result records. No network, package installation, host Python package, outside-workspace, ground-truth, or prior-rollout access succeeded. All strict checks pass using the conservative 51-turn count. |
| Codex single-frame ablation (`codex-ablation-single-frame-20260719T012741Z`) | passed | 0.0058 | GPT-5.6 Sol (high reasoning) received one representative frame from 00:13:00. It produced a plausible but incorrect 50-ply history and 8 captures; only 2/343 checks passed. |
| Codex no-media ablation (`codex-ablation-no-media-20260719T012741Z`) | passed | 0.0 | GPT-5.6 Sol (high reasoning) received only the prompt and schema, returned `unknown` with empty move/capture lists, and passed 0/287 checks. |

## Remaining Work

- The move sequence and Black-win result are verified. A second independent
  timestamp pass remains recommended for the +/- 6s annotations.
- Claude and Antigravity now have clean qualifying evidence under the
  user-approved checkpoint protocol, though neither counts as natural-prompt
  evidence. Retired-source runs, padded diagnostics, and the quota-truncated
  Claude attempt are omitted from the committed evidence.

## Repository Evidence

The committed calibration evidence is limited to one sanitized, plain-text
transcript for each qualifying agent plus this score summary. Image payloads,
full reward dumps, compressed binaries, duplicate instructions, response logs,
historical and diagnostic runs, and personal paths are omitted. The shortcut
ablation results are retained only as the two aggregate rows above.
