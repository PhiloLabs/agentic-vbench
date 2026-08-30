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

One run per harness against the current prompt, the current key and the current judge.
Each is one agent in one session; none spawned a subagent, and that is checked from the
harness's own artifacts rather than asserted.

| harness | harness version | model | reasoning | score | tool calls | entries | trajectory | in the image | audit |
|---|---|---|---|---|---|---|---|---|---|
| Codex | codex-cli 0.144.1 | `gpt-5.6-sol` | xhigh | **0.0703** | **156** | 312 | `rollouts/codex.jsonl` | yes | clean |
| Antigravity | app 1.40609.0 | `gemini-3.6-flash-high` | high | **0.0362** | **342** | 238 | `rollouts/antigravity.jsonl` | no | one benign finding |
| Claude Code | 2.1.251, headless | `claude-opus-4-8` | default | **0.0152** | **145** | 213 | `rollouts/claude.jsonl` | yes | clean |

Tool-call counts are the shipped auditor's, recounted from each rollout rather than taken
from the manifest, and they count every tool call rather than only shell commands: 135 of
Codex's 156, 48 of Claude's 145 and 94 of Antigravity's 342 were shell.

The judge's own breakdown, which is where this task's difficulty shows up:

| arm | entries | true positives | label and order right, timing ignored | label and onset right, offset ignored |
|---|---|---|---|---|
| Codex | 312 | 22 | 246 | 73 |
| Antigravity | 238 | 10 | 122 | 39 |
| Claude | 213 | 4 | 158 | 22 |

All three read the recipes far better than they place them. Codex put 246 of 314 steps in
the right sequence position with the right label and scored 22 of them, which is the same
shape every arm has shown since the first calibration: knowing what happened is not the
binding constraint here, knowing when is, and now also knowing whether it was done right.

Trajectory audits: six positive controls passed on each, zero network tool calls, zero
hits on any of the three shortcut patterns, and no network command in any of the 135, 48
and 94 shell commands. Codex and Claude are **clean**. Antigravity is **REVIEW REQUIRED**
on one finding, which is that it read
`.gemini/antigravity/brain/<conversation>/.system_generated/tasks/task-77.log`, its own
harness's task log. That is the app's artifact directory, not anything belonging to this
task, and it is the same category of finding as the previous Antigravity arm's.

All three clear both gates. The strongest arm is 0.0703 against a ceiling of 0.10, a margin
of 0.030, and the weakest of the three claims is the Antigravity row, which ran on the host
because that harness cannot be made to execute anywhere else; the evidence for that is in
the PR discussion and in the disclosure below.

### What the error field is worth, per arm

An entry has to say how its step was performed. The best a submission that has not judged
the performances can do on that field is to answer the key's largest single class, `"none"`,
which is 36.6 percent of it. Replacing each arm's answers with exactly that constant
separates what the arm earned by locating steps from what it earned by diagnosing them:

| arm | as submitted | error field replaced by a constant guess | of its matches: on correct steps / on diagnosed errors |
|---|---|---|---|
| Codex | 0.0703 | 0.0319 | 9 / 13 |
| Antigravity | 0.0362 | 0.0362 | 9 / 1 |
| Claude | 0.0152 | 0.0152 | 4 / 0 |

Only Codex is diagnosing, and thirteen of its twenty-two scored entries are steps it
correctly said had gone wrong. The other two are indistinguishable from a constant guess on
that field, which is the honest reading of what this addition costs a model that does not
attempt it. It is a requirement, not a cap: an agent that reads the performances will beat
it, and one of the three partly did.

### Two harness failures worth recording

Both cost a run, both were protocol rather than model, and both are now enforced in code
because prose did not stop either.

**The first headless Claude attempt died in 36 seconds with an empty transcript.**
`--permission-mode bypassPermissions` maps to `--dangerously-skip-permissions`, which Claude
Code refuses to run as root, and a container runs as root. It now creates a non-root user,
copies the credentials inside the container, and requires that user to answer a probe before
the arm starts.

**The second spawned 29 subagents, one per recording, and produced no answer at all.** It
delegated "Transcribe video A", "Transcribe video B" and so on, then never assembled the
results: its five writes were all helper scripts, and `output/solution.json` still held the
empty placeholder it wrote in the first five minutes. This is the failure this file already
warned about in prose, since the sibling Ego-Exo4D task scored 0.1791 as one subagent per
video and 0.0029 as one agent. The prose did not prevent it. The launcher now passes
`--disallowedTools Agent Task Monitor SendMessage ToolSearch WebFetch WebSearch`, and the
retry used Bash, Read, Write and Edit only, which is the same shape as the retained
interactive run. The failed transcript is kept beside the arms rather than deleted.

## Superseded: the runs that answered an earlier contract

## What the re-run found

Not a calibration row: it answered a contract that no longer exists. It is here because it
is why the contract changed.

With the two contract bugs fixed, one Codex arm was re-run inside the frozen image and
scored **0.1621** against the family's 0.10 ceiling: 266 entries, 47 fully correct, 213
tool calls, one agent in one session. Six things that could have made that an artefact
were checked and none of them was: the judge was unchanged (all three retained solutions
regrade to their shipped values to the digit), the prompt had become harder rather than
easier, the container ran 1.2 to 1.6 times slower than the host, the agent's own trace
records the network as blocked, there was one thread and no subagent, and nothing
reachable inside the container held the key. The difference was effort. The 0.0173 on
record submitted 265 entries and got 5 right; this one submitted 266 and got 47, because
it did the boundary search the earlier run stopped short of after 72 turns of a six-hour
budget.

So the 0.0173 was the unrepresentative measurement, and the difficulty argument this task
rested on did not survive a serious attempt. SPEC.md section 8 is what replaced it.

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
| random, mean of 400 | 0.0 |
| random, best of 400 | 0.0032 |
| best spam of any shape | 0.0006 |
| oracle answers filed under the wrong video | 0.0 |

And the three degraded-input runs the family's ablation gate asks for, all real runs of
gpt-5.6-sol at xhigh rather than simulations, each in its own empty working directory and
each forced to answer, with transcripts under `provenance/ablations/measured/`:

| degraded input | entries | label+order | F1 |
|---|---|---|---|
| no media at all | 315 | 56 | **0.0** |
| one still per recording, no tools | 297 | 187 | **0.0033** |
| 16 uniform frames per recording, no tools | 277 | **192** | **0.0034** |

All three ran with **zero shell commands**, which the retained transcripts show. All three
are forced to answer, because a zero from a model that declined to guess would say nothing
about whether the degraded input was enough.

The last row is worth pausing on, and it is the measurement SPEC.md section 8 rests on.
With no video and no way to ask for another frame, the model placed 192 of 314 steps
correctly by label and sequence position, as many as any calibrated agent has managed with
the full video and tools, and scored 0.0034. Two thirds of the label-and-order channel is
free to a submission that cannot seek, so that channel carries no signal. Under the
current contract those 192 buy exactly one scored entry, because a match also needs both
boundaries and the error tag.

And two shapes of partial competence, which bracket where the 0.10 gate actually sits:

Reproduce with `python3 provenance/ablations/run_ablations.py --jitter`. These are Monte
Carlo estimates over 1000 draws and they are printed to the precision the estimate
actually has: the third decimal moves by up to 0.002 between disjoint blocks, so there is
no fourth digit to read. An earlier draft of this table printed four.

Two curves, because an entry now has to say how its step was performed as well as when it
happened. The left column is a hypothetical agent that gets that field right, which
isolates boundary noise. The right column is one that answers `"none"` every time, the
key's largest single class and the best a submission that has not judged the performances
can do. The right column is the one a shortcut has to be measured against.

| Gaussian boundary noise, perfect labels and order | error tag right | error tag guessed |
|---|---|---|
| sigma = 1 s | 0.947 | 0.344 |
| sigma = 2 s | 0.681 | 0.244 |
| sigma = 3 s | 0.418 | **0.149** |
| sigma = 5 s | 0.183 | 0.065 |
| sigma = 8 s | 0.077 | 0.027 |
| sigma = 10 s | 0.051 | 0.018 |
| sigma = 15 s | 0.023 | 0.008 |

Read the right column before the left, and read it as a limitation rather than a defence.
The error field moves the point where a non-diagnosing agent crosses 0.10 from about
sigma = 7 s to about sigma = 3.5 s, so it is a real tightening: an agent now has to place
both boundaries of a 27-second step to within roughly three and a half seconds to beat the
gate without judging a single performance. It does not make the task safe. **At sigma = 3 s
a submission that never looks at how anything was done still scores 0.149.** What the
field buys is that the remaining route to the gate is genuinely hard timing rather than
recognition, and that an agent which does diagnose the performances will beat it honestly.

The small drop in the left column against the version of this table that shipped before
the field existed, 0.947 where it read 0.952, is not noise; the block spread is 0.001. When
a jittered entry drifts far enough to align against a neighbouring instance it now fails on
that instance's tag as well as its times, so requiring the field costs a little even when
the field is answered perfectly.

Running the same routine against the sibling Ego-Exo4D key puts sigma = 5 s at 0.107 there
against 0.183 here, so this key is about 1.7x more forgiving on timing alone. That was the
single largest risk to this task passing its gate, it was not compensated for by moving the
tolerance rule, and the re-run above is what it looks like when the risk lands.
