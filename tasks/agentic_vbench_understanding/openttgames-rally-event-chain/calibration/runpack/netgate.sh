#!/bin/bash
# Bring up (or tear down) the egress gate that every calibration run shares.
#
# The gate is default-DROP with an allowlist, never a denylist. A denylist keyed
# on resolved IPs cannot be complete -- GitHub and the dataset host answer with
# different addresses on different lookups, so a blocked host silently becomes
# reachable later. Default-DROP inverts the failure mode: if an allowed endpoint
# rotates its address the run breaks, which is visible, instead of the ground
# truth becoming reachable, which is not.
#
# Why a sidecar rather than image changes or a proxy: the frozen task image must
# not be modified for calibration and has no iptables, and agent CLIs differ in
# whether they honour HTTP(S)_PROXY, so a proxy would silently degrade to no
# isolation for some harnesses. The gate holds the network namespace; run
# containers join it with `--network container:$AVB_GATE` (default `avb-netgate`).
# Bringing up more than one named gate keeps concurrent runs independent: `install`
# on one gate cannot widen another gate's allowlist while that run is being scored.
#
# Two phases, because installing a CLI needs package hosts that a scored run
# must not keep:
#   ./netgate.sh up      allowlist = package hosts + model endpoints (install)
#   ./netgate.sh lock    allowlist = model endpoints only (scored run)
#   ./netgate.sh show | down
set -euo pipefail

GATE=${AVB_GATE:-avb-netgate}
ALPINE=${ALPINE_IMAGE:-alpine}

MODEL_HOSTS=(
  api.openai.com
  chatgpt.com
  api.anthropic.com
  generativelanguage.googleapis.com
  antigravity.google
  oauth2.googleapis.com
)
# Antigravity's account (non-API-key) auth runs an eligibility check on every
# invocation that fetches the signed-in user's profile picture. There is no flag
# or env var to skip it: with this host blocked the CLI exits before any work,
# with "Eligibility check failed: failed to get profile picture". It is therefore
# required for the whole scored phase, not just install -- removing it after
# startup was tried and fails, because the check re-resolves and the CDN rotates
# addresses. This widens the scored allowlist by one Google user-content CDN;
# scores.md discloses it, and net_guard still proves the ground-truth hosts stay
# blocked.
# Opt-in only: set AVB_ACCOUNT_AUTH=1. Left off by default so that a harness
# which does not need it -- Codex, Claude Code, or Antigravity in API-key mode --
# keeps the narrower allowlist, and so that running one harness can never widen
# another's gate.
if [ "${AVB_ACCOUNT_AUTH:-0}" = 1 ]; then
  ACCOUNT_AUTH_HOSTS=( lh3.googleusercontent.com )
else
  ACCOUNT_AUTH_HOSTS=()
fi
INSTALL_HOSTS=(
  deb.debian.org
  security.debian.org
  registry.npmjs.org
  nodejs.org
  antigravity.google
  storage.googleapis.com
  dl.google.com
  # release host the official agy installer resolves, read out of install.sh
  antigravity-cli-auto-updater-974169037036.us-central1.run.app
)

apply() {
  local hosts=("$@")
  docker exec "$GATE" sh -c '
    iptables -F OUTPUT
    iptables -P OUTPUT DROP
    iptables -A OUTPUT -o lo -j ACCEPT
    iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
    iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
    iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT
  '
  for h in "${hosts[@]}"; do
    docker exec "$GATE" sh -c "
      for ip in \$(getent ahostsv4 $h 2>/dev/null | awk '{print \$1}' | sort -u); do
        iptables -A OUTPUT -d \$ip -j ACCEPT
      done" || true
  done
  docker exec "$GATE" sh -c 'iptables -L OUTPUT -n | grep -c ACCEPT' \
    | xargs echo "  ACCEPT rules:"
}

case "${1:?usage: ./netgate.sh up|lock|show|down}" in
up)
  docker rm -f "$GATE" >/dev/null 2>&1 || true
  docker run -d --name "$GATE" --cap-add=NET_ADMIN "$ALPINE" sh -c 'sleep infinity' >/dev/null
  docker exec "$GATE" apk add --no-cache iptables >/dev/null 2>&1
  apply "${INSTALL_HOSTS[@]}" "${MODEL_HOSTS[@]}" ${ACCOUNT_AUTH_HOSTS[@]+"${ACCOUNT_AUTH_HOSTS[@]}"}
  echo "netgate up (install phase: package hosts + model endpoints allowed)"
  ;;
install)
  # Re-resolve the install hosts and re-apply. Package mirrors are CDN-backed and
  # rotate addresses, so the set pinned at `up` time goes stale within minutes;
  # this refreshes it in place rather than recreating the gate, which would tear
  # down the network namespace the run container is sharing.
  docker inspect "$GATE" >/dev/null 2>&1 || { echo "netgate not up"; exit 1; }
  apply "${INSTALL_HOSTS[@]}" "${MODEL_HOSTS[@]}" ${ACCOUNT_AUTH_HOSTS[@]+"${ACCOUNT_AUTH_HOSTS[@]}"}
  echo "netgate refreshed (install phase)"
  ;;
lock)
  docker inspect "$GATE" >/dev/null 2>&1 || { echo "netgate not up"; exit 1; }
  apply "${MODEL_HOSTS[@]}" ${ACCOUNT_AUTH_HOSTS[@]+"${ACCOUNT_AUTH_HOSTS[@]}"}
  echo "netgate locked (scored phase: model endpoints only)"
  ;;
show) docker exec "$GATE" iptables -L OUTPUT -n ;;
down) docker rm -f "$GATE" >/dev/null 2>&1 || true; echo "netgate down" ;;
*) echo "usage: ./netgate.sh up|lock|show|down" >&2; exit 1 ;;
esac
