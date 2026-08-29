# Calibration

The family asks two things of a task before it is worth merging: a strong agent scores
**below 0.10**, and a real attempt runs past **50 tool-call turns**. Both are measured
here, on the shipped key, with the shipped judge.

## How the arms are run

`calibration/run_arm.py` pins the protocol so that the three arms are comparable and so
that no arm is accidentally helped or starved:

- **one agent, one session, all 22 recordings.** Not one agent per recording. An earlier
  version of the sibling Ego-Exo4D task was calibrated with one subagent per video, each
  getting the full budget, and it scored 0.1791; the same task under one agent scored
  0.0029. The protocol, not the corpus, produced that difference, so it is fixed in code
  rather than in prose.
- **the budget comes from `task.toml`**, `steps.agent.timeout_sec`, read at run time. It
  is not chosen in the calibration script.
- **arms do not run concurrently.** An exclusive lock plus a process-table scan, and the
  scan carries a positive control: if it cannot see any agent process at all it errors
  rather than reporting all-clear.
- **every run writes `manifest.json`**: model, reasoning effort, harness version, budget,
  argv, prompt sha256, wall clock, exit code.
- **the prompt is the shipped prompt.** `calibration/make_prompts.py` asserts that
  substituting the run directory back to `/workspace` reproduces
  `steps/solve/instruction.md` byte for byte.

Turn counts are not self-reported. `calibration/audit_trajectory.py` reads the raw
rollout, counts real tool calls, lists every filesystem path the agent touched, and looks
for the three ways this task could be shortcut: reading the key or the grader, reaching
the network, and recalling the source dataset. Every check carries a positive control, so
a clean verdict on a file the script could not read is impossible: if a control fails the
script exits non-zero and reports nothing else.

## Results

> **These three runs are stale as of the review of PR #115 and are kept for reference,
> not as the calibration.** Two task-contract bugs found in that review have been fixed:
> the prompt's schema examples were real key rows, and the judge made the key's arbitrary
> order among steps with the same onset a hidden requirement. Fixing the first changed the
> prompt, so every arm below answered a slightly different question than the one now
> shipped, and `calibration/verify_scores.py` refuses to bless them: it reports all three
> as STALE and exits non-zero. The judge change is a no-op on these three submissions,
> which regrade to the same 0.0173, 0.0073 and 0.0762, so what has to be redone is the
> runs, not the scoring. They will be re-measured once the contract is frozen.


| harness | harness version | model | reasoning | score | tool-call turns | trajectory | wall clock | audit |
|---|---|---|---|---|---|---|---|---|
| Codex | codex-cli 0.144.1 | gpt-5.6-sol | xhigh | **0.0173** | **72** | `rollouts/codex.jsonl` | 72.8 min | clean |
| Claude Code | 2.1.246 | claude-opus-4-8 | xhigh | **0.0073** | **175** | `rollouts/claude.jsonl` | 107 min active | clean |
| Antigravity | app, run in the UI | gemini-3.6-flash | high | **0.0762** | **426** | `rollouts/antigravity.jsonl` | 120.5 min | one benign finding |

All three arms clear both gates. On the score gate they are not equally comfortable, and
the honest summary is the weakest of them: **the strongest arm scores 0.0762 against a
ceiling of 0.10, a margin of 0.024.** That is the risk the difficulty section below
predicted in advance, it is being reported rather than managed, and nothing in the key or
the tolerance rule was touched after seeing it.

The spread between the arms is itself worth reading. A factor of ten separates 0.0073
from 0.0762 while the label-and-order counts sit within 30 of each other (164, 183, 195
out of 314). All three read the recipes comparably well. What separates them is entirely
how precisely they place the boundaries.

### Codex, gpt-5.6-sol at xhigh, codex-cli 0.144.1

Run under `run_arm.py --arm codex`: one agent, one session, all 22 recordings, budget
21600 s read from `task.toml`. Exit 0 after 72.8 minutes, so it stopped because it
decided it was finished rather than because the budget bound it. Submitted 265 entries
against a key of 314.

The judge's own breakdown is where this task's difficulty shows up, and it is worth
reading before the score:

| | count | of 314 |
|---|---|---|
| right label, right place in the sequence, timing ignored | **183** | 58% |
| right label and the onset inside tolerance | 21 | 7% |
| right label and BOTH boundaries inside tolerance (scored) | **5** | 1.6% |

The agent read the recipes well. It identified and ordered 58 percent of the steps
correctly. What it could not do is say when each one started and stopped: of the 183 it
placed correctly, 162 missed the onset and a further 16 got the onset but missed the
offset. This is the task working as designed. The difficulty is temporal localisation
over a 10-to-19-minute recording, not recognition, and it is not an artefact of a
confusing label set.

Trajectory audit: **VERDICT clean**. 72 tool calls (59 Bash, 13 Write), five positive
controls passed, zero network tool calls, zero absolute paths touched outside the run
directory, zero hits on any of the three shortcut patterns, and no network command among
the 59 shell commands it ran.

Two things to disclose rather than leave to be found:

1. **The transport dropped four times.** The trajectory carries four reconnect events
   ("stream disconnected before completion", broken pipe), after which Codex exhausted
   its five WebSocket retries and fell back to HTTPS on its own. The run then completed
   normally: `turn.completed` reports 14.3M input tokens and 68.4K output tokens, the
   process exited 0, and the solution covers all 22 recordings. This was a transport
   problem on our side, not a truncated attempt, but it happened and the raw trajectory
   shows it.
2. **It used 20 percent of its budget.** 72.8 minutes of a six-hour allowance, and 72
   turns against a floor of 50. The gate is a floor rather than a target, and the agent
   ended the session itself, but a reviewer reading "72 turns" should know it is not a
   run that was cut short by time.

### Claude Code, Opus 4.8 at xhigh, interactive session

Run in a Claude Code session rather than through `run_arm.py`, for the same reason as the
Antigravity arm: it was driven by hand. The same things are pinned by artifact.

- **The model is read from the harness.** 448 messages in the raw session transcript
  carry `message.model = "claude-opus-4-8"`.
- **One agent, one session, all 22 recordings.** Three tool names appear in the whole
  trajectory: Read, Bash, Edit. There is no `Task` call, so no subagent was spawned.
- **The prompt is the shipped prompt**, sha256 `55bf8c1c...9b14b6e6`, and the only other
  thing the user said in the entire session is quoted in full below.
- **The budget was not enforced**, because an interactive session has no budget knob.

Submitted 236 entries against a key of 314:

| | count | of 314 |
|---|---|---|
| right label, right place in the sequence, timing ignored | **164** | 52% |
| right label and the onset inside tolerance | 23 | 7.3% |
| right label and BOTH boundaries inside tolerance (scored) | **2** | 0.6% |

Trajectory audit: **VERDICT clean**. 175 tool calls (112 Read, 42 Bash, 21 Edit), six
positive controls passed, zero network tool calls, zero absolute paths outside the run
directory, zero hits on any of the three shortcut patterns, and no network command among
the 42 shell commands it ran.

Two things to disclose rather than leave to be found:

1. **The account hit its usage limit mid-run and the session sat idle for 3 h 56 min**,
   from 04:35:12Z to 08:31:37Z. It was restarted by the only other message the user sent
   in the whole session, quoted here in full: "I hit my usage limit while you were
   working, but it has reset now. Please continue from where you left off." That carries
   no information about the task, the corpus or the answer. The wall-clock column above
   reports 107 minutes of active time rather than the 343-minute span, because the span
   is mostly the stall.
2. **The trajectory is a whole interactive session, not a subagent's output.** It was
   checked for the operator's own context before shipping, under positive controls that
   had to find the prompt's title and first line before any absence was reported: zero
   hits for the workspace CLAUDE.md, the operator's memory index, the task package,
   the answer key or the grader, and the operator's identity.

### Antigravity, Gemini 3.6 Flash at high, run by hand in the app

Run in the Antigravity app rather than through `run_arm.py`, because the app has no
headless entry point. Everything the script would have pinned is pinned here by artifact
instead, and the artifacts are named so a reviewer can check them rather than take the
row on trust.

- **The model is read from the harness, not from the agent.** The conversation store
  records the session model as `gemini-3.6-flash-high` in `executor_metadata`, and it
  keeps one `gen_metadata` row per planner turn: 431 rows, exactly matching the 431
  `PLANNER_RESPONSE` rows in the shipped trajectory, every one of them carrying
  `used_claude=false` and `used_non_gemini_model=false`.
- **One agent, one session, all 22 recordings.** Six tool names appear in the whole
  trajectory and none of them spawns an agent. `manage_task` is 80 status polls and one
  kill against background *shell* commands, and all 51 completions the harness reported
  read "The command exited with code N". This is worth checking rather than asserting:
  the sibling Ego-Exo4D task scored 0.1791 when it was run as 17 subagents and 0.0029
  under one agent, so the protocol moved that score by more than the corpus did.
- **The prompt is the shipped prompt.** `make_prompts.base_prompt` applied to the run
  directory reproduces the folder's `instruction.md` byte for byte,
  sha256 `e7cd27d0...647ab651`.
- **The budget was not enforced**, because the app has no budget knob. The 21600 s figure
  in the manifest is there for comparability only. The run ended on its own after 7228 s,
  a third of that, so the arm was not budget-bound either way.

Submitted 290 entries against a key of 314. The breakdown says the same thing as the
Codex arm, one notch further along:

| | count | of 314 |
|---|---|---|
| right label, right place in the sequence, timing ignored | **195** | 62% |
| right label and the onset inside tolerance | 45 | 14% |
| right label and BOTH boundaries inside tolerance (scored) | **23** | 7.3% |

It read the recipes slightly better than Codex did and localised them about four times as
often, and that is the whole of the difference between 0.0173 and 0.0762. Of the 195
steps it placed in the right sequence position, 150 still missed the onset outright. The
binding constraint is unchanged: knowing what happened is not hard here, knowing when is.

Trajectory audit: 426 tool calls (210 view_file, 90 run_command, 81 manage_task, 30
list_dir, 9 write_to_file, 6 grep_search), six positive controls passed, zero network tool
calls, zero hits on any of the three shortcut patterns, and no network command among the
90 shell commands it ran. **VERDICT: REVIEW REQUIRED**, on one finding, and the review is
below.

Six things to disclose rather than leave to be found:

1. **The one path outside the run directory is its own planning artifact.** The agent
   wrote `implementation_plan.md` into the app's own conversation directory, because that
   is where this harness parks user-facing plan artifacts. It is not a read of anything
   belonging to this task, and the container has no equivalent directory. That single
   path is the entire reason the verdict is not "clean".
2. **The materials are reached through a symlink, so the agent had to read outside its
   stated working directory to see the clips at all.** The shipped prompt says to stay
   inside the working directory; in local calibration `materials/` is a symlink out to a
   scratch directory holding the transcoded 1080p clips. In the task image there is no
   symlink and the clips sit at `/workspace/materials`, so this is a property of running
   calibration on a laptop, not of the task. It is listed here because the agent was
   asked to approve that read and a reviewer reading the trajectory will see it.
3. **The stream was interrupted twice.** The harness logged "the stream was interrupted"
   at steps 510 and 512, which cost two empty planner turns; the agent resumed with a
   `view_file` at step 515. No work was lost and no context was reset. The two rows are a
   row type the audit reader did not originally understand, which would have dropped them
   silently, so the reader now fails a control on any row type no reader claims.
4. **It noticed the tablet, on its very first frame, and never used it.** After
   extracting one frame at t=10 s it wrote "I see a tablet on the counter displaying
   text, potentially recipe instructions". That is the cue SPEC.md open item 6 is about,
   and this is the only place in 426 tool calls where any agent refers to it: Codex and
   Claude never mention it. It did not crop it, did not upscale it, did not read it, and
   its answers do not follow the canonical script. The cue is real and available, and it
   is not being taken.
5. **Its context was truncated mid-run.** The transcript carries the harness's own note
   that "the earlier parts of this conversation have been truncated due to its long
   length", followed by a summary it wrote to continue from. It is one session and one
   agent throughout, and the truncation is the harness managing its own context, not a
   restart, but a reviewer counting 426 turns should know the agent was not holding all
   of them at once.
6. **It did not recognise the source dataset, and it did not reach the network.** Both
   are worth stating because the same harness did both on the sibling Ego-Exo4D task: it
   named Ego4D in its private thinking from a frame grid, and it ran three `pip install`
   commands under a task that declares `allow_internet = false`. Here a sweep of twelve
   dataset-identifying patterns over every `content` and `thinking` block returns five
   hits. Four are the prompt's own line 179 read back to itself, the one telling it not
   to rely on memory of "the dataset they may come from"; the fifth is its own turn using
   the word generically for the 22 clips. No corpus, institution or host is ever named,
   and there are zero `pip`, `curl`, `wget` or `git clone` commands.

The turn count and every conclusion above were recomputed on the shipped, sanitized
rollout and are identical to the raw file: 426 turns either way.

## What is already known about the difficulty, without an agent

Measured on this key, in `provenance/ablations/run_ablations.py` and reproducible:

| submission | F1 |
|---|---|
| oracle | 1.0 |
| empty | 0.0 |
| canonical recipe prior, full dish order | 0.0032 |
| canonical recipe prior, labels that occur only | 0.0065 |
| random, mean of 400 | 0.0001 |
| random, best of 400 | 0.0032 |
| best spam of any shape | 0.0013 |
| oracle answers filed under the wrong video | 0.0 |

And the three degraded-input runs the family's ablation gate asks for, all real runs of
gpt-5.6-sol at xhigh rather than simulations, each in its own empty working directory and
each forced to answer, with transcripts under `provenance/ablations/measured/`:

| degraded input | entries | label+order | F1 |
|---|---|---|---|
| no media at all | 352 | 32 | **0.0** |
| one still per recording, no tools | 326 | 161 | **0.0031** |
| 16 uniform frames per recording, no tools | 312 | **211** | **0.0032** |

All three ran with **zero shell commands**, which the retained transcripts show. All three
are forced to answer, because a zero from a model that declined to guess would say nothing
about whether the degraded input was enough.

The last row is worth pausing on. With no video and no way to ask for another frame, the
model placed 211 of 314 steps correctly by label and sequence position, more than any
calibrated agent managed with the full video and tools, and scored 0.0032. Whatever this
task is measuring, it is not recognition of the procedure, and the tools are not
decoration.

And two shapes of partial competence, which bracket where the 0.10 gate actually sits:

Reproduce with `python3 provenance/ablations/run_ablations.py --jitter`. These are Monte
Carlo estimates over 1000 draws and they are printed to the precision the estimate
actually has: the third decimal moves by up to 0.002 between disjoint blocks, so there is
no fourth digit to read. An earlier draft of this table printed four.

| a hypothetical agent, Gaussian boundary noise | F1 |
|---|---|
| perfect labels and order, sigma = 1 s | 0.952 |
| perfect labels and order, sigma = 2 s | 0.683 |
| perfect labels and order, sigma = 3 s | 0.419 |
| perfect labels and order, sigma = 5 s | 0.183 |
| perfect labels and order, sigma = 8 s | 0.077 |
| perfect labels and order, sigma = 10 s | 0.051 |
| perfect labels and order, sigma = 15 s | 0.023 |

Both arms land where that table predicts, and they bracket its bottom rows. Codex matched
183 of 314 labels in the right sequence position and scored 0.0173, below the 8 s row;
Antigravity matched 195 and scored 0.0762, which sits right at the 8 s row. Neither is
literally an agent with perfect labels and 8 s of jitter, since both also lose labels, but
the ordering is the point: knowing what happened is not the binding constraint here,
knowing when is.

So the gate is roughly "an agent that can place both boundaries of a 27-second step to
within about 6 seconds". Running the same routine against the sibling Ego-Exo4D key puts
sigma = 5 s at 0.107 there against 0.183 here, so this key is about 1.7x more forgiving
on timing alone. That is the
single largest risk to this task passing its gate, it was not compensated for by moving
the tolerance rule, and it is why the arms above are the deciding evidence.
