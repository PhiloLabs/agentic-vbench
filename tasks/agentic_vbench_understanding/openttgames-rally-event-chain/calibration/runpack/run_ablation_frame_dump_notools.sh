#!/bin/bash
# frame_dump_no_tools -- the literal condition, not the earlier substitute.
#
# What the family asks for is the complete selected frame set placed in front of
# the model with no agentic inspection in between. The earlier attempt could not
# do that: Codex CLI's only tool is the shell, so the frames had to sit on disk
# and the agent spent 44 shell/Python calls looking at them. That is a
# frames-plus-tools condition, which is not what was requested.
#
# This runner removes the agent loop entirely. The complete 1 fps set -- all 1435
# frames, the sampling the review accepted -- is pre-arranged into 30 seven-by-seven
# contact sheets before anything runs, and those sheets are handed to the model as
# image inputs on a single request with every tool disallowed. The model answers
# from the pixels in one pass; the harness, not the model, writes the file. Expect
# `tool_use` count 0 in the trajectory: that is the condition being tested.
#
# Sheet geometry is 1568x882, chosen by measurement rather than taste. Image cost
# tracks pixel area, not tile count, so 7x7 and 5x5 cost the same per sheet and 7x7
# simply needs fewer of them: 30 sheets at ~4679 tokens each is ~140k, which leaves
# real output room inside the context window. The larger 1918x1078 variant measured
# ~5606 per sheet (~168k) and left too little. A probe confirmed the model still
# resolves the ball at this tile size, so the zero this produces is a result rather
# than an artefact of an unreadable presentation.
#
# Usage: ./run_ablation_frame_dump_notools.sh [model]
set -euo pipefail

MODEL="${1:-claude-opus-4-8}"
BUILDER=avb-abl-fdnotools          # holds the extracted frames and built sheets
RUNNER=avb-run-claude              # holds the subscription credential
TASK="$(cd "$(dirname "$0")/../.." && pwd)"
A="$(cd "$(dirname "$0")/.." && pwd)/ablations"
MODE=frame-dump-notools
mkdir -p "$A"

for c in "$BUILDER" "$RUNNER"; do
  docker inspect "$c" >/dev/null 2>&1 || { echo "FATAL: $c is not up"; exit 1; }
done
N=$(docker exec "$BUILDER" sh -c 'ls /workspace/sheets/*.jpg 2>/dev/null | wc -l' | tr -d ' ')
[ "$N" -gt 0 ] || { echo "FATAL: no contact sheets in $BUILDER:/workspace/sheets"; exit 1; }

# Pin exactly which sheets the scored request saw.
docker exec "$BUILDER" sh -c 'cd /workspace/sheets && sha256sum *.jpg' > "$A/ablation_${MODE}_sheets.sha256"
echo "  sheet manifest: $(wc -l < "$A/ablation_${MODE}_sheets.sha256" | tr -d ' ') entries"

"$(dirname "$0")/net_guard.sh" "ablation-$MODE-pre" "$A/$MODE.netguard.log"

{
  echo "ablation:        $MODE (literal no-tools condition)"
  echo "harness:         Claude Code CLI, stream-json image input, all tools disallowed"
  echo "harness version: $(docker exec "$RUNNER" claude --version 2>/dev/null)"
  echo "model:           $MODEL"
  echo "presentation:    $N contact sheets, 7x7 grid, 1568x882 each, 224x126 per tile,"
  echo "                 covering all 1435 frames of a 1 fps sample with no frame omitted"
  echo "sheet manifest:  ablation_${MODE}_sheets.sha256"
  echo "tools:           none -- Bash/Read/Write/Edit/Glob/Grep/Task/WebFetch/WebSearch all disallowed"
  echo "task commit:     $(git -C "$TASK" rev-parse HEAD)"
  echo "image:           $(docker image inspect agentic-vbench-openttgames --format '{{.Id}}' 2>/dev/null)"
  echo "rules file:      not loaded -- the request runs from /tmp, which has no"
  echo "                 CLAUDE.md, so the shared rules file is not in this run's"
  echo "                 context at all. The model sees the 30 images, instruction.md"
  echo "                 and the ablation note, and nothing else. The repository rules"
  echo "                 file (sha256 $(shasum -a 256 "$(dirname "$0")/AGENTS.md" | awk '{print $1}'))"
  echo "                 is unmodified and unused here."
  echo "override:        in the ablation prompt text only; no rules file was edited"
  echo "started:         $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} | tee "$A/ablation_${MODE}_metadata.txt"

docker exec "$BUILDER" sh -c 'tar -cf - -C /workspace/sheets .' \
  | docker exec -i "$RUNNER" sh -c 'rm -rf /tmp/sheets && mkdir -p /tmp/sheets && tar -xf - -C /tmp/sheets'
docker cp "$TASK/steps/solve/instruction.md" "$RUNNER:/tmp/instruction.md" >/dev/null

docker exec -i "$RUNNER" python3 - <<'PY'
import base64, glob, json
sheets = sorted(glob.glob('/tmp/sheets/*.jpg'))
blocks = []
for p in sheets:
    blocks.append({"type": "image", "source": {
        "type": "base64", "media_type": "image/jpeg",
        "data": base64.b64encode(open(p, 'rb').read()).decode()}})
instruction = open('/tmp/instruction.md').read()
note = """

## Ablation condition (this run only)

You have no video file, no shell, and no tools of any kind. The images above are
the entire input: %d contact sheets covering every frame of a 1 fps sample of the
match, 1435 frames in all.

Each sheet is a 7x7 grid read left to right, top to bottom. Sheets are in
chronological order. Sheet 1 tile 1 is second 0, sheet 1 tile 2 is second 1, and so
on without gaps, so the tile at index t (0-based) of sheet s (1-based) is second
49*(s-1) + t. The trailing tiles of the final sheet are blank padding.

This section supersedes the no-guessing rules above for this run only. Rule 4 of the
workspace rules ("work from the video") and the instruction rule against reporting
unobserved events do not apply here: there is no video, the contact sheets are the
input, and this is a deliberate diagnostic that measures what the frames alone yield
without any tooling. Abstaining makes it measure nothing. A best-effort reconstruction
built from these tiles is not a claim about the real match, does not void the run, and
is what is being asked for. Do not return an empty rally list.

Answer from these images alone. Reply with the JSON object required by the schema
above and nothing else: no prose, no code fence, no commentary. Your entire reply is
written to output/solution.json verbatim, so anything else in it invalidates the
submission.""" % len(sheets)
blocks.append({"type": "text", "text": instruction + note})
json.dump({"type": "user", "message": {"role": "user", "content": blocks}},
          open('/tmp/fd_in.jsonl', 'w'))
open('/tmp/fd_in.jsonl', 'a').write('\n')
print(f"  prepared {len(sheets)} sheets")
PY

docker exec "$RUNNER" sh -c "
    cd /tmp
    cat /tmp/fd_in.jsonl | claude -p --model $MODEL \
      --input-format stream-json --output-format stream-json --verbose \
      --disallowedTools Bash,Read,Write,Edit,NotebookEdit,Glob,Grep,Task,WebFetch,WebSearch,ListAgents,Skill,ToolSearch
  " > "$A/ablation_${MODE}.jsonl" 2> "$A/ablation_${MODE}.err" || true

"$(dirname "$0")/net_guard.sh" "ablation-$MODE-post" "$A/$MODE.netguard.log"

# The model has no Write tool by design, so the harness extracts its reply and
# writes it verbatim. It never synthesises a submission on the model's behalf --
# in particular it never substitutes {"rallies": []} for an unparseable reply,
# because a harness-constructed empty answer is exactly the abstention-shaped zero
# this rerun exists to avoid. An invalid reply is written as-is and the hardened
# verifier scores it 0 on its own, which the malformed-input regression covers.
python3 - "$A/ablation_${MODE}.jsonl" "$A/ablation_${MODE}_solution.json" <<'PY'
import json, re, sys
text = []
tools = []
for line in open(sys.argv[1], errors='replace'):
    line = line.strip()
    if not line.startswith('{'):
        continue
    try:
        d = json.loads(line)
    except Exception:
        continue
    for b in (d.get('message', {}) or {}).get('content', []) or []:
        if isinstance(b, dict):
            if b.get('type') == 'text':
                text.append(b.get('text', ''))
            if b.get('type') == 'tool_use':
                tools.append(b.get('name'))
raw = '\n'.join(text).strip()
raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw).strip()
open(sys.argv[2], 'w').write(raw)
try:
    parsed = json.loads(raw)
    print(f"  rallies submitted: {len(parsed.get('rallies', []))}")
except Exception:
    print("  model reply is not valid JSON; written verbatim for the verifier to judge")
    print(f"  reply length: {len(raw)} chars")
print(f"  tool_use calls in trajectory: {len(tools)}  (the condition requires 0)")
PY

python3 "$TASK/steps/solve/tests/judge.py" \
  --solution "$A/ablation_${MODE}_solution.json" \
  --reference "$TASK/steps/solve/tests/reference.json" \
  --output "$A/ablation_${MODE}_reward.json" >/dev/null

python3 -c "
import json; d = json.load(open('$A/ablation_${MODE}_reward.json'))
print('  reward %s   (gate: <= 0.15)' % d['reward'])
print('  rallies %d/%d matched   strokes %d/%d matched' % (
    d['matched_rallies'], d['reference_rallies'],
    d['stroke_timing']['matched'], d['stroke_timing']['reference']))"
