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
Harbor's adapter is built for exactly that: a token is provisioned once out of band, and
every run afterwards is non-interactive. From its own docstring:

> Generate the token file with a one-time `agy` sign-in in a keyring-less container
> (which writes the plaintext `antigravity-oauth-token`) or by extracting it from a local
> keyring/Keychain login, then point `AGY_AUTH_JSON_PATH` at it.

The adapter uploads that file with `upload_file` so it never reaches Harbor's command
logs, moves it to `$HOME/.gemini/antigravity-cli/antigravity-oauth-token`, `chmod 600`,
and scrubs it from the container after the run.

The sign-in is a human step and is performed by the task author, not by any agent
preparing this submission. No token value appears in this repository, in the raw archive,
or in any transcript.

## What the final campaign will do

`harbor run --agent antigravity-cli --model gemini-3.5-flash --effort high` against the
frozen task image, with `AGY_AUTH_JSON_PATH` pointing at the provisioned token. The
resulting native transcript is retained as the raw trajectory, per the family rule that a
summary cannot be audited.

This replaces the host run. The host Antigravity row and its evidence stay in the archive
as the record of what was tried first, and are not reported as a calibration arm.
