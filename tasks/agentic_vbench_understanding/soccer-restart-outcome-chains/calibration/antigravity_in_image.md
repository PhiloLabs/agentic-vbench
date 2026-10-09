# Antigravity in the task image

The Antigravity arm runs the Antigravity CLI, `agy`, inside the image this task's
Dockerfile builds. Harbor's `antigravity-cli` agent drives it, the path the CaptainCook4D
task took, and `calibration/run_antigravity.py` is the launcher. This file records what
that path needs beyond the stock adapter.

## Harbor and the two flags

Harbor is pinned to 0.21.0 through `uvx --from harbor==0.21.0`. When the CaptainCook4D task
checked the releases up to 0.22.0, no single release both seeded `agy`'s OAuth token and
passed `--effort`. 0.21.0 seeds the token, and `agy` accepts no API key or Application
Default Credentials, so that half cannot be given up.

`calibration/harbor_agents.py`, copied unchanged from that task, subclasses the adapter
through the `module:ClassName` path Harbor documents on `--agent` and adds what 0.21.0 does
not pass:

- `--effort`, because `agy` refuses `gemini-3.6-flash` without one;
- `--print-timeout`, because `agy` otherwise ends every `--print` run at five minutes. The
  value is `task.toml`'s own `steps.agent.timeout_sec`, 10800 s.

It also copies `agy`'s session record from
`$HOME/.gemini/antigravity-cli/brain/*/.system_generated/logs/transcript_full.jsonl`, the
file the shipped rollout comes from. A probe of `agy` 1.2.2 inside this image, a one-tool-call
run, confirmed the file is still written at that path.

## The credential

`agy` signs in through a browser only. The token file was produced once by the task author's
own sign-in and reaches Harbor through the `AGY_AUTH_JSON_PATH` environment variable, never
the command line, so it is in neither Harbor's logs nor the manifest. The adapter uploads it
into the container, sets it to mode 600 and removes it after the run. No token value appears
in this repository or in any transcript.

The reported run uses a second account. The first attempt's subagents used up the first
account's quota, as `calibration/scores.md` records, so the author signed in a second
account with Harbor's own helper, `python -m harbor.agents.installed.antigravity_login`,
which runs the same browser sign-in inside a throwaway container and copies the token out.

## Egress

`task.toml` keeps `allow_internet = false`. Harbor's phase overrides carry the difference,
declared on the command line and recorded in the manifest:

- **while the agent is installed** (`--allow-environment-host`): `antigravity.google`, the
  release manifest host `antigravity-cli-auto-updater-974169037036.us-central1.run.app`, and
  `storage.googleapis.com`, the hosts the vendor's installer reads;
- **while the agent runs** (`--allow-agent-host`): the Google endpoints `agy` needs to
  authenticate and reach its model, listed in `run_antigravity.py`.

Both lists are the CaptainCook4D task's, where each host was added only after a run named
it in an error. The prompt's no-lookup rule is unchanged, and `calibration/audit_trajectory.py`
reads the trajectory for shell-level network use.

## One agent

`agy` 1.2.2 offers the model two tools the one-agent protocol rules out, `invoke_subagent`
and `manage_subagents`. This arm's first attempt used them eight minutes in. One call
started four subagents, each with its own quarter of the clip, and the main session then
polled them. That attempt was stopped and is not reported; `calibration/scores.md` says why.

`agy` has no flag that removes a tool, and its hooks can refuse one. So
`calibration/harbor_agents.py` writes `calibration/antigravity_hooks.json` to
`~/.gemini/config/hooks.json`, agy's global customization directory, before the run. The
file holds one PreToolUse hook that answers `deny` for any tool whose name contains
"subagent". `calibration/probe_antigravity_hook.py` checks the hook in both directions with
a prompt that asks for one subagent. Without the hook agy has to record a second session,
and with it agy has to record exactly one while the model still tries the tool. On the
account the reported run uses, with `gemini-3.6-flash` at high, both held. Without the hook
agy recorded two sessions and the model reported that the subagent replied PING. With it agy
recorded one session, the model still called `invoke_subagent`, and it reported that
subagent execution is disabled in this environment. The record is
`calibration/rollouts/antigravity-hook-probe.json`.

Every session agy records is copied out with the run, and `calibration/run_antigravity.py`
marks the run `one_session` only when there is exactly one. The earlier copy took whichever
transcript was written last, which in a run with subagents can be a subagent's. The
trajectory is now the session whose first request carries the instruction's title.

## Resources

Harbor applies the 4 CPUs and 8192 MiB `task.toml` declares. The Docker engine has 8 CPUs
and 31 GiB, so the container can reach its own memory limit. Harbor also starts an
egress-control sidecar with no CPU limit of its own; `calibration/arm_protocol.py` counts it
as taking no CPU when it checks whether another arm fits beside this one, and says why.
