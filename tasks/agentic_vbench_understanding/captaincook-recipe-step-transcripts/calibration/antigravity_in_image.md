# Antigravity in the task image

The first review round asked for Antigravity in the image and got a host run plus an
exception request. That request answered the wrong question, and this file withdraws it.

**What we tested before.** The Antigravity desktop application, version 2.11.0 on this
Mac. Four pieces of evidence were assembled about why that application cannot be driven
inside a container.

**What was asked.** The Antigravity **CLI**, driven by Harbor, the path the merged Dota 2
and IndustReal tasks use. That is a different artifact from the desktop application, and
nothing measured about the application bears on it.

## The in-image path exists and installs

Harbor 0.20.0 carries `antigravity-cli` as a first-class agent
(`harbor/agents/installed/antigravity_cli.py`). Its `install()` runs, inside the container:

```
apt-get update && apt-get install -y curl          # as root
curl -fsSL https://antigravity.google/cli/install.sh | bash   # as the agent user
```

which places `agy` at `$HOME/.local/bin/agy`.

Measured on this machine, 2026-08-31, `linux/arm64`:

| probe | result |
|---|---|
| installer in the task's base image, `python:3.12-slim` | installs, `agy` 1.1.22, 198,070,504 bytes |
| installer in the real task image `cc4d:frozen`, as the non-root `agent` user | installs, `agy` 1.1.22, owned by `agent` |
| `agy --help` with no credential | prints the full flag set, including `-p/--print`, `--model`, `--effort`, `--output-format stream-json`, `--log-file` |
| `agy -p "say OK" --model gemini-3.5-flash` with no credential | prints a Google OAuth URL, waits 60 s for a browser callback or a pasted authorization code, then `Error: authentication failed or timed out` |

So the adapter is not the limitation and the image is not the limitation. The one
remaining requirement is a credential.

## The credential

`agy` has no API-key or service-account path; it does interactive browser OAuth only.
Harbor 0.21.0's adapter is built for exactly that: a token is provisioned once out of
band, and every run afterwards is non-interactive. From its own docstring:

> Generate the token file with a one-time `agy` sign-in in a keyring-less container
> (which writes the plaintext `antigravity-oauth-token`) or by extracting it from a local
> keyring/Keychain login, then point `AGY_AUTH_JSON_PATH` at it.

The adapter uploads that file with `upload_file` so it never reaches Harbor's command
logs, moves it to `$HOME/.gemini/antigravity-cli/antigravity-oauth-token`, `chmod 600`,
and scrubs it from the container after the run. The sign-in is a human step, performed by
the task author. No token value appears in this repository, in the raw archive, or in any
transcript.

## No released Harbor does both halves

Getting the arm to start took two flags Harbor does not pass, and the reason is a version
split that is worth stating plainly, because it decides which Harbor this arm has to use.

| Harbor | seeds the OAuth token | passes `--effort` |
|---|---|---|
| 0.20.0 through 0.21.1.dev202608192356 | yes | no |
| 0.21.1.dev202608202357 through 0.22.0 | no | yes |

Every release in that range was checked. The changeover happens in one release: the same
version that added `--effort` replaced OAuth-token seeding with an API key or Application
Default Credentials, and `agy` accepts neither.

Without `--effort`, `agy` 1.1.22 refuses to start:

    Error: invalid model selection (--model "gemini-3.6-flash" --effort ""):
    --model gemini-3.6-flash requires --effort (available: low, medium, high)

The 0.21.0 adapter does read `reasoning_effort`. It writes a `harbor-<model>-<effort>`
alias into `~/.agy/antigravity-cli/settings.json` with the right `thinkingLevel`, then
passes the raw model name on the command line instead of the alias, so the setting is
never reached.

The second flag came out of a probe run rather than out of reading. `agy --print-timeout`
defaults to five minutes and is the agent's own cap on a single `--print` run; it knows
nothing about the budget Harbor grants. A probe ended at exactly that mark with
`Error: timeout waiting for response`. The value passed is `task.toml`'s own
`steps.agent.timeout_sec`, six hours, not a number chosen here.

Rather than patch the library, both flags are added by a four-line subclass through the
`module:ClassName` agent path Harbor documents on `--agent`. It is
`calibration/harbor_agents.py`, and it changes two strings and nothing else.

## Egress

`task.toml` keeps `allow_internet = false` and is not modified. Harbor's own phase
overrides carry the difference, declared on the command line so both lists are in the
record:

- **installing the agent** (`--allow-environment-host`): `antigravity.google`, the
  release manifest host `antigravity-cli-auto-updater-…-us-central1.run.app`, and
  `storage.googleapis.com`, which are the three hosts the vendor's installer reads. They
  were taken from a traced run of the installer, not guessed.
- **while the agent runs** (`--allow-agent-host`): the Google endpoints `agy` needs to
  authenticate and call its model. Every one of them was added only after a run named it
  in an error, starting from an empty list.

The prompt's own no-lookup rule is unchanged, and `calibration/audit_trajectory.py` still
reads the trajectory for shell-level network use.

## Memory

The first full attempt died at 32 minutes with exit 137, the OOM kill. `task.toml` asks
for 8192 MiB and the Docker daemon had 8.2 GB in total, which does not leave an 8 GB
container room to reach its own limit. The daemon was raised to 16 GiB so the container
gets what the task declares. The partial answer that attempt produced is not reported
anywhere: a starved agent scores lower, and lower is the direction that would make this
task look like it passes.

## What this replaces

The host Antigravity row. Its evidence stays in the archive as the record of what was
tried first, and is not reported as a calibration arm.
