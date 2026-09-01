#!/bin/bash
# Stage a fresh, key-free run container for one harness.
#
# Anti-cheat properties enforced here:
#   - the container is built from the frozen task image, so the agent sees the
#     shipped libraries and nothing else;
#   - only the task-visible video and instruction.md plus the documented harness
#     rules file (staged as AGENTS.md / GEMINI.md / CLAUDE.md) exist in it;
#   - the baked media is re-verified against the pinned SHA-256;
#   - a guard scan proves no reference, judge, or annotation file is reachable;
#   - the repo is never mounted, so the answer key cannot be read even by accident.
#
# Usage: ./stage_workspace.sh <harness>        e.g. codex | claude | antigravity
set -euo pipefail

H="${1:?usage: ./stage_workspace.sh <harness>}"
TASK="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE=${TASK_IMAGE:-agentic-vbench-openttgames}
GATE=${AVB_GATE:-avb-netgate}
CNAME="avb-run-$H"

# Take the pinned media digest specifically; the first 64-hex string in the
# Dockerfile is the base-image digest, which is a different thing.
MEDIA_SHA=$(sed -n 's/^ARG MATERIALS_SHA256=\([0-9a-f]\{64\}\)$/\1/p' \
             "$TASK/environment/Dockerfile" | head -1)
[ -n "$MEDIA_SHA" ] || { echo "FATAL: no pinned media sha in Dockerfile"; exit 1; }

docker inspect "$GATE" >/dev/null 2>&1 || { echo "FATAL: netgate not up (./netgate.sh up)"; exit 1; }

# Verify the baked media in a throwaway container, never inside the scored one.
# Hashing 11 GB streams the whole file through the page cache of whichever cgroup
# does the reading; doing it inside the 8192 MB scored container left ~7.2 GB of
# its budget occupied before the agent ran a single command, which is what
# OOM-killed two runs. Verifying here keeps the guarantee and leaves the scored
# cgroup cold, without resorting to a VM-global cache flush.
docker rm -f "${CNAME}-verify" >/dev/null 2>&1 || true
docker run --rm --name "${CNAME}-verify" "$IMAGE" sh -c "
  echo '$MEDIA_SHA  /baked/game.mp4' | sha256sum -c - >/dev/null \
    || { echo 'FATAL: media hash mismatch'; exit 1; }
" || { echo "FATAL: baked media failed verification"; exit 1; }
echo "  media sha256 verified out-of-band: $MEDIA_SHA"

docker rm -f "$CNAME" >/dev/null 2>&1 || true
# Enforce the task's declared budget rather than running unlimited. An earlier
# run had no limit at all, so the CLI plus its ffmpeg children exhausted the
# whole Docker VM and the kernel OOM-killed the agent three minutes in. The
# container must not get more than task.toml grants either: raising it would
# quietly relax the resource constraint the benchmark declares.
MEM_MB=$(sed -n 's/^memory_mb *= *\([0-9]*\).*/\1/p' "$TASK/task.toml" | head -1)
MEM_MB=${MEM_MB:-8192}
CPUS=$(sed -n 's/^cpus *= *\([0-9]*\).*/\1/p' "$TASK/task.toml" | head -1)
CPUS=${CPUS:-4}
echo "  enforcing task budget: ${MEM_MB}MB memory, ${CPUS} cpus (from task.toml)"

docker run -d --name "$CNAME" --network "container:$GATE" \
  --memory="${MEM_MB}m" --memory-swap="${MEM_MB}m" --cpus="$CPUS" \
  -w /workspace "$IMAGE" sh -c 'sleep infinity' >/dev/null

# Link the baked media rather than copying it. Copying 11 GB into the writable
# layer charged the whole file to this cgroup's page cache at once: measured
# memory.current 8191 MiB with file=8444 MiB and anon=0.5 MiB, i.e. the task's
# entire 8192 MB budget consumed by cache before the agent ran a single command.
# That is what OOM-killed two runs. The link keeps the bytes in the read-only
# image layer and lets pages be faulted in on demand.
docker exec "$CNAME" sh -c '
  set -e
  mkdir -p /workspace/materials /workspace/output /workspace/work
  ln -sf /baked/game.mp4 /workspace/materials/game.mp4
'
docker cp "$TASK/steps/solve/instruction.md" "$CNAME:/workspace/instruction.md"

# Harness-level rules, kept separate from the frozen instruction.md so the task
# contract is untouched. Follows the pattern used by the merged lacrosse task:
# each harness reads its own conventional filename.
RP="$(dirname "$0")"
for f in AGENTS.md GEMINI.md CLAUDE.md; do
  docker cp "$RP/AGENTS.md" "$CNAME:/workspace/$f" >/dev/null 2>&1
done
echo "  staged harness rules file (AGENTS.md / GEMINI.md / CLAUDE.md)"

# Harness credentials. Codex authenticates from CODEX_HOME; copying the host
# login in read-only avoids putting key material on a command line or in the
# container's environment. The gate allows only the model endpoint, so this
# credential cannot reach anything else.
if [ "$H" = codex ] && [ -f "$HOME/.codex/auth.json" ]; then
  docker exec "$CNAME" mkdir -p /opt/codex-home
  docker cp "$HOME/.codex/auth.json" "$CNAME:/opt/codex-home/auth.json"
  docker exec "$CNAME" chmod 600 /opt/codex-home/auth.json
  echo "  staged CODEX_HOME credential (read-only login, not an API key)"
fi

if [ "$H" = claude ]; then
  # Subscription OAuth is preferred over the metered API key. macOS keeps the
  # login in the Keychain, so it is piped straight into the container and never
  # touches the host filesystem or a command line. An ANTHROPIC_API_KEY present
  # anywhere would silently override OAuth and restore per-token billing, so the
  # key file is staged only when there is no subscription login to use.
  if security find-generic-password -s "Claude Code-credentials" -w >/dev/null 2>&1; then
    security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null \
      | docker exec -i "$CNAME" sh -c '
          mkdir -p /root/.claude && cat > /root/.claude/.credentials.json
          chmod 600 /root/.claude/.credentials.json
          printf "{\n  \"hasCompletedOnboarding\": true\n}\n" > /root/.claude.json'
    sub=$(docker exec "$CNAME" python3 -c \
      'import json;print(json.load(open("/root/.claude/.credentials.json"))["claudeAiOauth"]["subscriptionType"])' 2>/dev/null)
    echo "  staged Claude subscription OAuth login (plan: ${sub:-unknown}); no API key staged"
  elif [ -f "$HOME/.avb_anthropic_key" ]; then
    docker cp "$HOME/.avb_anthropic_key" "$CNAME:/opt/anthropic-key"
    docker exec "$CNAME" chmod 600 /opt/anthropic-key
    echo "  staged Anthropic API key file (metered; no subscription login found)"
  fi
fi

if [ "$H" = antigravity ]; then
  # Account (subscription) auth is preferred. Note what is deliberately NOT done
  # here: no `modelProvider: "gemini"` in settings.json. That key selects the CLI's
  # API-key mode, which would make it look for GEMINI_API_KEY and ignore the
  # account session entirely.
  #
  # The credential is the file the CLI itself writes after an in-container login.
  # macOS keeps the host login in the Keychain, which is not portable -- copying
  # the whole ~/.gemini into a container was tried and still reports "Please sign
  # in". A Linux container has no keyring daemon, so the CLI falls back to
  # antigravity-oauth-token, and that file does transfer.
  # Account auth is opt-in (AVB_ACCOUNT_AUTH=1), not the default, because it is
  # known-broken in a container: subsystems that need the desktop keyring log
  # "You are not logged into Antigravity" and retry hard -- 42 times in 90 s --
  # until the container hits its memory cap and is OOM-killed, while the main
  # inference path keeps working. Evidence: rollouts/aborted/oom-accountauth.*.
  # It also needs lh3.googleusercontent.com in the scored allowlist. API-key mode
  # has neither problem and is what the reported run used.
  if [ "${AVB_ACCOUNT_AUTH:-0}" = 1 ] && [ -f "$HOME/.avb_antigravity_oauth" ]; then
    docker exec "$CNAME" mkdir -p /root/.gemini/antigravity-cli
    docker cp "$HOME/.avb_antigravity_oauth" "$CNAME:/root/.gemini/antigravity-cli/antigravity-oauth-token"
    docker exec "$CNAME" chmod 600 /root/.gemini/antigravity-cli/antigravity-oauth-token
    am=$(docker exec "$CNAME" python3 -c \
      'import json;print(json.load(open("/root/.gemini/antigravity-cli/antigravity-oauth-token"))["auth_method"])' 2>/dev/null)
    echo "  staged Antigravity account session (auth_method: ${am:-unknown}); no API key staged"
  elif [ -f "$HOME/.avb_gemini_key" ]; then
    docker cp "$HOME/.avb_gemini_key" "$CNAME:/opt/gemini-key"
    docker exec "$CNAME" sh -c '
      chmod 600 /opt/gemini-key
      mkdir -p /root/.gemini/antigravity-cli
      printf "{\n  \"modelProvider\": \"gemini\"\n}\n" > /root/.gemini/antigravity-cli/settings.json'
    echo "  staged Gemini API key (metered/API-key mode; no account session found)"
  fi
fi



# Guard: nothing that could serve as an answer key may exist in the container.
docker exec "$CNAME" sh -c '
  hits=$(find / -xdev \( -name "reference.json" -o -name "judge.py" -o -name "game_2.json" \
         -o -name "*answer*" -o -name "*ground_truth*" \) 2>/dev/null | head)
  if [ -n "$hits" ]; then echo "FATAL: forbidden file present:"; echo "$hits"; exit 1; fi
  echo "  guard scan clean: no reference/judge/annotation file in container"
'

echo "staged: $CNAME (image $IMAGE, netns shared with $GATE)"
docker exec "$CNAME" ls -la /workspace
