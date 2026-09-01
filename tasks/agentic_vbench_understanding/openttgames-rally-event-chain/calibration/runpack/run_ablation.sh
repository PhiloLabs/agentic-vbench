#!/bin/bash
# Degraded-input ablations. Each must score at or below 0.15; a pass here is what
# proves the task has no shortcut, so every number must come from a real run --
# never a constructed submission.
#
#   single-frame      one representative frame instead of the video
#   no-media          prompt and schema only, no media at all
#   no-media-forced   same, but the run is required to answer instead of abstaining;
#                     this is the variant that bounds recall, and it needs an
#                     ablation-only override in the container copy of the rules
#                     because rule 4 otherwise makes the agent decline
#
# A legacy `frame-dump` branch is still present, but only to reproduce the superseded
# frames-plus-tools run. It is not retained evidence and is not part of the current
# required ablation set. The literal frame_dump_no_tools condition lives in
# run_ablation_frame_dump_notools.sh, because Codex cannot express it: the shell is
# Codex's only tool, so leaving the frames on disk leaves the agent inspecting them,
# and `--sandbox read-only` would leave it unable to write output/solution.json at
# all. The superseded run's artifacts are under ablations/superseded/.
#
# video-only / audio-only are not run: this task declares audio as not required,
# so that pair does not apply.
#
# Usage (retained):            ./run_ablation.sh single-frame|no-media|no-media-forced [codex-version]
# Legacy reproduction only:    ./run_ablation.sh frame-dump [codex-version]
set -euo pipefail

MODE="${1:?usage: ./run_ablation.sh single-frame|no-media|no-media-forced|frame-dump}"
VER="${2:-0.147.0}"
TASK="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE=${TASK_IMAGE:-agentic-vbench-openttgames}
GATE=${AVB_GATE:-avb-netgate}
CNAME="avb-abl-$MODE"
A="$(cd "$(dirname "$0")/.." && pwd)/ablations"
mkdir -p "$A"

docker inspect "$GATE" >/dev/null 2>&1 || { echo "FATAL: netgate not up"; exit 1; }
docker rm -f "$CNAME" >/dev/null 2>&1 || true
MEM_MB=$(awk -F'[= ]+' '/^memory_mb/{print $2}' "$TASK/task.toml" | head -1)
CPUS=$(awk -F'[= ]+' '/^cpus/{print $2}' "$TASK/task.toml" | head -1)
docker run -d --name "$CNAME" --network "container:$GATE" -w /workspace \
  --memory="${MEM_MB:-8192}m" --memory-swap="${MEM_MB:-8192}m" --cpus="${CPUS:-4}" \
  "$IMAGE" sh -c 'sleep infinity' >/dev/null
echo "  budget: ${MEM_MB:-8192}MB / ${CPUS:-4} cpus   gate: $GATE"
docker cp "$TASK/steps/solve/instruction.md" "$CNAME:/workspace/instruction.md"
# Same harness rules as the canonical run. Without this the ablation would differ
# from canonical in two ways at once and would not isolate the input degradation.
for f in AGENTS.md GEMINI.md CLAUDE.md; do
  docker cp "$(dirname "$0")/AGENTS.md" "$CNAME:/workspace/$f" >/dev/null 2>&1
done
docker exec "$CNAME" mkdir -p /workspace/materials /workspace/output /opt/codex-home
if [ -f "$HOME/.codex/auth.json" ]; then
  docker cp "$HOME/.codex/auth.json" "$CNAME:/opt/codex-home/auth.json"
  docker exec "$CNAME" chmod 600 /opt/codex-home/auth.json
elif [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "FATAL: no ~/.codex/auth.json and no OPENAI_API_KEY" >&2; exit 1
fi

case "$MODE" in
  single-frame)
    docker exec "$CNAME" sh -c '
      ffmpeg -nostdin -v error -ss 700 -i /baked/game.mp4 -frames:v 1 \
        /workspace/materials/frame.png'
    ;;
  no-media|no-media-forced)
    : # materials stays empty on purpose
    ;;
  frame-dump)
    # one frame per second, then the extraction tooling is removed: the point is
    # to show agency matters, so the agent gets the pixels but cannot drive
    # ffmpeg itself.
    #
    # The tools are removed from the container rather than by running the agent
    # under `--sandbox read-only`. read-only makes /workspace unwritable, so the
    # agent cannot write output/solution.json at all -- that scores 0.0 by
    # construction, which proves nothing about whether frames alone suffice.
    # Verified directly: `codex sandbox -c sandbox_mode="read-only"` fails a
    # write to /workspace/output with "Read-only file system".
    docker exec "$CNAME" sh -c '
      ffmpeg -nostdin -v error -i /baked/game.mp4 -vf fps=1 \
        /workspace/materials/f_%05d.png
      FF=$(command -v ffmpeg || true); FP=$(command -v ffprobe || true); FL=$(command -v ffplay || true)
      rm -f "$FF" "$FP" "$FL" 2>/dev/null
      for b in "$FF" "$FP" "$FL"; do
        [ -n "$b" ] && [ -e "$b" ] && { echo "FATAL: $b still present" >&2; exit 1; }
      done
      echo "  extracted $(ls /workspace/materials | wc -l) frames; ffmpeg/ffprobe removed"'
    ;;
  *) echo "unknown mode $MODE" >&2; exit 1 ;;
esac

if [ "$MODE" = no-media-forced ]; then
  # The binding rules file outranks instruction.md, and rule 4 ("work from the
  # video") is why earlier attempts at this diagnostic abstained even when the
  # appended ablation section told them to guess: the agent was right to treat the
  # hard rules as inviolable. For this diagnostic only, the container copy of the
  # rules carries the same override. The repository copy is untouched and every
  # scored run still uses it at sha256 779eec27...; the metadata below records the
  # different digest the agent actually saw here.
  for f in AGENTS.md GEMINI.md CLAUDE.md; do
    docker exec "$CNAME" sh -c "cat >> /workspace/$f <<'"'"'RULEEOF'"'"'

## Ablation override (this diagnostic run only)

Rule 4 does not apply on this run: there is no video to work from. This is a
deliberate no-media diagnostic that measures what guessing alone scores, so
abstaining defeats it. Producing a best-effort invented reconstruction here does
not void the run and is not a claim about the real match. See the ablation
condition at the end of instruction.md.
RULEEOF"
  done
  docker exec "$CNAME" sh -c 'cat >> /workspace/instruction.md <<'"'"'EOF'"'"'

## Ablation condition (this run only)

No media is provided. This is a deliberate diagnostic, not a mistake, and abstaining
defeats its purpose: an empty rally list measures nothing.

**This section supersedes the no-guessing rules above for this run only.** The
"do not guess, omit rather than infer" rule stated above, and the workspace rules
against reporting unobserved events do not apply here: this is a deliberate
diagnostic whose entire purpose is to measure what pure guessing scores, so
declining to guess makes it measure nothing. Nothing you write here is a claim
about the real match, and nothing here changes how the normal task is run.

You must still write `output/solution.json`, conforming to the schema above, and it
must be a best-effort reconstruction of the **whole match**, not a token single entry.
The video is 1435 seconds of a real table-tennis match; produce the full sequence of
rallies you would expect across that duration, with plausible serve times, stroke
chains, players, hands, stroke types and endings throughout.

Guess. Infer whatever you can from how matches of this length are normally
structured. Being wrong is the expected outcome and costs you nothing here; what
defeats the purpose of this diagnostic is a single placeholder rally, an empty
list, a refusal, or a request for the media.
EOF'
fi

"$(dirname "$0")/net_guard.sh" "ablation-$MODE-pre" "$A/$MODE.netguard.log"

# Package mirrors are CDN-backed and rotate; re-pin them right before apt runs.
"$(dirname "$0")/netgate.sh" install
docker exec "$CNAME" sh -c "
  apt-get update -qq && apt-get install -y -qq --no-install-recommends nodejs npm >/dev/null
  npm install -g @openai/codex@$VER >/dev/null 2>&1
" || true
docker exec "$CNAME" codex --version >/dev/null 2>&1 || {
  echo "FATAL: codex did not install - not starting a scored phase" >&2; exit 1; }

# Package hosts must not stay reachable during the scored phase.
"$(dirname "$0")/netgate.sh" lock

{
  echo "ablation:        $MODE"
  echo "harness:         Codex CLI"
  echo "harness version: $(docker exec "$CNAME" codex --version 2>/dev/null)"
  echo "model:           gpt-5.6-sol"
  echo "reasoning:       high"
  echo "web_search:      false"
  echo "gate:            $GATE"
  echo "task commit:     $(git -C "$TASK" rev-parse HEAD)"
  echo "rules sha256:    $(shasum -a 256 "$(dirname "$0")/AGENTS.md" | awk '{print $1}') (repository copy)"
  echo "rules in container: $(docker exec "$CNAME" sha256sum /workspace/AGENTS.md 2>/dev/null | awk '{print $1}')"
  echo "started:         $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} | tee "$A/ablation_${MODE}_metadata.txt"

SANDBOX="--sandbox workspace-write"

docker exec -e CODEX_HOME=/opt/codex-home \
  ${OPENAI_API_KEY:+-e OPENAI_API_KEY="$OPENAI_API_KEY"} \
  "$CNAME" sh -c "
    cd /workspace
    codex exec --json --skip-git-repo-check $SANDBOX \
      --config model_reasoning_effort=high \
      --config model=gpt-5.6-sol \
      --config tools.web_search=false \
      \"\$(cat instruction.md)\" < /dev/null
  " > "$A/ablation_$MODE.jsonl" 2> "$A/ablation_$MODE.err" || true

"$(dirname "$0")/net_guard.sh" "ablation-$MODE-post" "$A/$MODE.netguard.log"

docker cp "$CNAME:/workspace/output/solution.json" "$A/ablation_${MODE}_solution.json" 2>/dev/null \
  || echo '{"rallies": []}' > "$A/ablation_${MODE}_solution.json"

python3 "$TASK/steps/solve/tests/judge.py" \
  --solution "$A/ablation_${MODE}_solution.json" \
  --reference "$TASK/steps/solve/tests/reference.json" \
  --output "$A/ablation_${MODE}_reward.json" | tail -1

echo "ablation $MODE reward:"
python3 -c "import json;print('  ', json.load(open('$A/ablation_${MODE}_reward.json'))['reward'])"
echo "  (gate: must be <= 0.15)"
