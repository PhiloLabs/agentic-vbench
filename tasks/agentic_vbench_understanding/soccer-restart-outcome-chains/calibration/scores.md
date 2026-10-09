# Calibration

The family asks two things of a task before it is worth merging. A strong agent scores
**below 0.10**, and a real attempt runs past **50 tool-call turns**. Both are measured here
inside the image `environment/Dockerfile` builds, on the shipped key, with the shipped judge.
`calibration/verify_scores.py` recomputes every number in this file, `SPEC.md` and `README.md`
from the artifacts in `calibration/rollouts/` and `provenance/`, and fails if a document says
anything they do not back.

This task changed during calibration. It first asked for restarts only, where a Codex run
scored 0.3529, and the ledger that replaced it was tightened to a 1 s tolerance after its
first runs. Both earlier versions are archived with the scorer each ran under, and the
Results below are ledger runs at 1 s.

## How the arms are run

Codex and Claude Code run through `calibration/run_in_image.py`. Antigravity runs under
Harbor, which owns that arm's container, and `calibration/antigravity_in_image.md` records
what that path needs. The protocol all three share lives in `calibration/arm_protocol.py`.

- **One agent, one session.** Claude Code runs with `--disallowedTools Agent Task Monitor
  SendMessage ToolSearch WebFetch WebSearch`, so it can neither spawn a subagent nor reach
  the web. Codex runs one `codex exec` thread, and `ship_arm.py` requires its session record
  to hold exactly one session in `/workspace`. Antigravity's `agy` offers subagent tools, so a
  hook denies them before they run, a probe shows the hook holding in both directions, and
  `run_antigravity.py` marks the run one session only when agy recorded exactly one.
- **The budget comes from `task.toml`.** It is `steps.agent.timeout_sec`, 10800 s, read at
  run time. It was 3600 s when calibration began, for the reason under "The first budget".
- **The resources come from `task.toml`.** Every arm's container gets 4 CPUs and 8192 MiB
  on a Docker engine with 8 CPUs and 31 GiB. Arms overlap only when every running
  container's CPU limit plus the new arm's fits on the engine, and each manifest records
  what was already running when its arm started.

  | arm | started, UTC | already running |
  |---|---|---|
  | Codex | 20:14:01 | nothing, reconstructed as its manifest explains |
  | Claude Code | 21:09:53 | Codex, reconstructed as its manifest explains |
  | Antigravity | 00:57:21 | nothing |

- **The prompt is the shipped prompt**, checked byte for byte before each run, and its
  digest is in every manifest.
- **Egress is cut before the agent starts.** In the two in-image arms DNS resolves nothing
  and `/etc/hosts` pins the model API and the CLI's token endpoint: `chatgpt.com` and
  `auth.openai.com` for Codex, `api.anthropic.com` and `platform.claude.com` for Claude
  Code. The allowed hosts must answer and `example.com` must not, and the CLI must answer a
  trivial question once with the network open and once after the cut. Antigravity's hosts
  are Harbor's phase overrides, listed in its manifest.
- **Every run writes a manifest** with the model, reasoning effort, the CLI version read
  inside the container, budget, resources, argv, prompt digest, wall clock, exit code and
  both egress checks.

Turn counts are not self-reported. `calibration/audit_trajectory.py` reads each shipped
rollout, counts the tool calls the model issued, lists every path it touched, and looks for
the ways this task could be shortcut: reading the key or the grader, reaching the network,
and naming SoccerNet. Every check carries a positive control, and a failed control exits
with no verdict.

For Codex the rollout is the session record the CLI keeps itself, which `run_in_image.py`
copies out of the container. The `--json` event stream ships beside it and on its own
undercounts the run. In code mode each tool call is an `exec` script, and most of the shell
commands and image views inside it never reach that stream. On the first Codex attempt, the
stream held 41 shell commands and the session record held 156 tool calls that viewed 460
frames between them. The auditor counts a script once however much it did inside.

## Results

| arm | model, effort | entries | true positives | reward | tool calls | audit |
|---|---|---|---|---|---|---|
| Codex | GPT 5.6 Sol, xhigh | 165 | 14 | **0.0663** | 185 | clean |
| Claude Code | Opus 4.8, xhigh | 129 | 18 | **0.0901** | 405 | one failed `pip install` |
| Antigravity | Gemini 3.6 Flash, high | 218 | 11 | **0.0333** | 351 | two `pip install` attempts |

The reward is each class's F1 averaged over the fourteen classes in the key. All three runs
ended on their own with an answer written and inside the 180-minute budget, Codex after 71
minutes of agent time, Claude Code after 166 and Antigravity after 139.

**The runner stopped before the agents did.** At 21:25:51 UTC the Claude Code session that
had launched `run_in_image.py` for both arms was restarted, which killed the runner and its
`docker exec` clients. The agents inside the containers were not signalled and worked on to
their own ends, Codex at 21:56 UTC and Claude Code at 00:37 UTC, so nothing enforced the
budget after 21:25 and neither run reached it. Their answers and session records were then
copied out by hand, matched against the containers by SHA256, and the containers removed.
Each manifest records this under `runner_interrupted`, and the exit code, which only the
runner could have seen, is marked not observed. The streams the two CLIs printed stop at
21:25, so each shipped rollout is the CLI's own session record, with the stream beside it as
`<arm>-events.jsonl`. On the 2 s Claude Code run, whose runner survived, the stream and the
record give the same 242 tool calls.

**The host slept during both runs.** The lid was closed from 20:37:32 to 21:14:36 UTC in the
Codex run and from 23:01:42 to 23:36:58 UTC in the Claude Code run. Docker's VM pauses with
the host, so the agent times above come from each container's own clock, which stops while
the host sleeps, as the runner's budget timer does. Claude Code's record shows four API
errors inside the second window and the run carrying on after it.

**Two audits flag `pip install`.** In its first minute Claude Code ran
`pip install numpy opencv-python-headless pillow`, which failed because DNS resolves nothing
inside the container. Antigravity ran `pip install opencv-python-headless pillow numpy` in its
first minute too, which exited with code 1 when Harbor's egress control dropped the
connection to the package index, and tried `pip install pillow` once more near the end under
the same control. No other command in either run reaches for the network.

**An Antigravity attempt before the reported one ended without an answer.** It started at
20:14:06 UTC, the lid was closed 23 minutes in, and agy exited on a dropped model connection
during a brief wake of the sleeping host. It ran as one session with no subagent call and is
kept in `rollouts/not-reported/antigravity-1s-attempt/`. Its audit flags one `pip install` in
its first minute, which exited with code 1 when Harbor's egress control dropped the connection
to the package index.

## What is known without an agent

Measured on the ledger key by `provenance/ablations/run_ablations.py`, with the oracle and
the empty submission graded again inside the image by `calibration/run_oracle_empty.py`.
Every blind submission is as long as the key and is handed the true spans of the two halves,
which the prompt does not give, so each is stronger than a real blind guess.

| submission | F1 |
|---|---|
| oracle, inside the image | 1.0 |
| empty, inside the image | 0.0 |
| Ball out of play, repeated 216 times evenly over the halves | 0.0041 |
| every (action, team) pair at its key count, each spread evenly | 0.0012 |
| pairs drawn from the key's distribution at random times, mean of 400 | 0.0039 |
| the same, best of 400 | 0.0511 |

And the three degraded-input runs the family's ablation gate asks for. Each is a real run of
GPT 5.6 Sol at xhigh through `codex exec` with a read-only sandbox in an empty working
directory. Each prompt is the shipped prompt with the media paragraph replaced and the answer
printed instead of written to a file, which `make_ablation_prompt.py` asserts, and each run is
told that an empty sequence is not an acceptable answer. The stills and contact sheets were
cut inside the task image and are not committed; their SHA256 digests are in each run's
`details.json`.

| degraded input | entries | F1 |
|---|---|---|
| the prompt alone | 2 | **0.0000** |
| one still at t = 1786 | 1 | **0.0000** |
| 128 frames on 8 contact sheets, one every 50 s | 8 | **0.0000** |

All three ran with zero shell calls, which their transcripts show. Told that an empty answer
was not acceptable, they still returned two entries, one and eight, so they show a model
declining to guess more than a guess failing. The blind submissions above bound what guessing
earns.

## How the contract got here

### The restart contract, and why it was replaced

The first contract on this match asked for every visible restart as
`(t, restart_type, team, outcome)`, scored by an order-preserving F1 with a 3 s tolerance
against a key of 72 restarts. Its prompt, scorer and runs are kept, in
`provenance/superseded-restart-contract/` and `rollouts/superseded-restart-contract/`. The
archived prompt's SHA256 equals the digest every superseded manifest records, and the
archived scorer regrades every superseded solution to its shipped reward.

A three-hour Codex run on that contract finished on its own after 46 minutes and scored
**0.3529**: 30 entries, 18 of them correct, 256 tool calls, clean audit. Seventeen of the 18
were throw-ins with no shot or goal after them, the most common tuple in a key where 48 of
72 restarts were throw-ins and 63 had no outcome. Its matched entries sat within 1.2 s of the
key, so no tighter tolerance would have changed the verdict: at 1 s it still scored 0.3333.

The same run exposed a definition the prompt had wrong. SoccerNet-v2's guidelines call a
free kick indirect when it is taken "with no intention to score" and direct when it is a
shot or faces a wall, which is why the key held 14 indirect free kicks and one direct. The
prompt gave only the two names, so an agent reading them by the laws of the game labels a
free kick for a foul as direct. Five of Codex's direct free kicks sat within 2 s of an
indirect one in the key, with the same team and outcome. Scored with the two classes merged,
the run reaches 0.4510, so fixing the definition could only make that contract easier.

The action ledger replaced it, and every choice below was fixed before any agent ran
against the ledger:

- **every visible SoccerNet-v2 annotation**, all seventeen classes, 216 entries, each defined
  in the prompt as SoccerNet's guidelines define it. The team rule was checked against this
  match's own labels.
- **a tolerance set from the blind baselines**, so that a spread of Ball out of play entries
  cannot rival a real attempt.
- **no half boundaries in the prompt.** The only visible kick-off sits at 3399.5 s, and the
  restart prompt told the agent the second half began at about 3400.

The degraded-input runs on the restart contract scored 0.0265 with the prompt alone, 0.0000
from one still and 0.0260 from 128 frames. They are archived with that prompt.

### The ledger's first runs, at a 2 s tolerance

The ledger first ran with a 2 s tolerance. Those runs, that prompt and that scorer are
archived under `provenance/superseded-2s-tolerance/` and `rollouts/superseded-2s-tolerance/`,
and `verify_scores.py` regrades each of them with the scorer it ran under. The tolerance here
is 1 s, the tightest window SoccerNet's own tight average-mAP uses, and the blind baselines
at 1 s are in the table above. One of those runs, the Antigravity arm, was 4.6 minutes in
when the tolerance changed and was stopped, with one session and no answer.

The 1 s runs in Results were made while the reward was one F1 pooled over every entry. It
became the mean of each class's F1 after they had finished. `provenance/superseded-pooled-f1/`
keeps the pooled scorer, and `verify_scores.py` regrades every 1 s run with it.

### The first budget

The calibration began at the budget #51 shipped with, 3600 s, on the restart contract. Three
runs used it and none wrote an answer. The shipped verifier scores a missing solution 0.0,
so each would have cleared the 0.10 gate by writing nothing, and a gate cleared that way
measures the budget instead of the task. The budget became 10800 s. The Codex run above then
finished inside the old hour anyway, so the budget alone was never what kept the restart
scores low.

| run | tool calls | how it ended | kept in |
|---|---|---|---|
| Claude Code, first run | 226 | reached 3600 s. Its last messages say the goals were pinned and the final fine passes resolved, with the answer still to be compiled. | `rollouts/superseded-restart-contract/first-budget/claude-1/` |
| Codex, second run | 245 | reached 3600 s. It had finished its full-match sweep by 50 minutes and was cross-checking every goal chain against the score graphic before saving. | `rollouts/superseded-restart-contract/first-budget/codex-2/` |
| Claude Code, second run | 144 | stopped at 50 minutes when the budget was raised. At 40 minutes it had reached t = 2600 of the 6427 s clip. | `rollouts/superseded-restart-contract/first-budget/claude-2/` |

A Claude Code run at the new budget was stopped at 68.7 minutes, after 263 tool calls and
with no answer written, when the ledger replaced the restart contract. It is in
`rollouts/superseded-restart-contract/claude-3h-stopped/`. All four audits are clean.

### Attempts that failed on the harness

Both are kept in `rollouts/superseded-restart-contract/not-reported/`, and each harness
failure is now fixed in code.

**Codex, first attempt, ended without an answer.** It ran 53.5 minutes of agent time. Its
access token expired at 15:49:30 UTC, and Codex refreshes tokens at `auth.openai.com`,
which the egress cut had not allowed, so it retried for four minutes and ended the turn with
`error sending request for url (https://auth.openai.com/oauth/token)`. `run_in_image.py` now
pins each CLI's token endpoint beside its model API. Up to then the attempt had made 156
tool calls and its audit was clean. Three more things about it:

1. **The host slept through part of it.** The laptop's lid closed about 20 minutes in, and
   the power log records sleep from 14:52:34 to 15:21:28 UTC with brief maintenance wakes.
   Docker's VM paused with the host, and so did the runner's budget timer, which is
   `time.monotonic()` and does not count sleep on macOS, so the pause was not charged to the
   agent. Codex's own record agrees, with 3,211.7 s of turn time against 4,883 s of wall
   clock. The four `Connection refused` WebSocket errors in its stderr fall at 14:54 and
   15:18 UTC, beside maintenance wakes at 14:53:50 and 15:18:13, and Codex reconnected after
   each and kept working.
2. **The budget stop could not have worked.** `run_in_image.py` stopped an arm with `pkill`,
   and the image has no procps. The first Claude Code run had already started under that
   version, so `calibration/budget_watchdog.py` held its budget from outside the runner and
   sent SIGKILL to the agent user's processes when the agent command had been alive 3600.1 s
   by the container's own clock. It was tested first on a throwaway container with a 12 s
   budget. `run_in_image.py` now sends that SIGKILL itself.
3. **The runner wrote its credential back after the failure.** The file it wrote back held
   the same token set, refresh token included, and the next run's open preflight refreshed
   it at 16:19:51 UTC, before egress was cut, as designed.

**Antigravity, first attempt, split the match across four subagents.** Eight minutes in, at
16:02:06 UTC, the main session called `invoke_subagent` once with four subagents, one per
quarter of the clip, and then polled them with `manage_subagents`. That is the protocol
failure this family has already measured once: the sibling Ego-Exo4D task scored 0.1791 when
run as one subagent per video and 0.0029 under one agent. The attempt was stopped at
16:18:16 UTC, after all five session transcripts had been copied out of the container, by
sending SIGTERM to `agy`. By then the main session had made 107 tool calls of its own, and
one of them was `pip install opencv-python-headless pillow numpy tqdm`, which failed because
egress was closed. The subagents also used up that Google account's Antigravity quota, so
the probe and the reported run use a second account on a paid plan, signed in the same way.
