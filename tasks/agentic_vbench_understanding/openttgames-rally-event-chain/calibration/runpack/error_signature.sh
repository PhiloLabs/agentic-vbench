#!/bin/bash
# Derive a canonical failure class for one attempt, from that attempt's own
# immutable artifacts.
#
# Why not the shared agy.log: the CLI truncates it each time --log-file is
# opened, so provider evidence survives on some attempts and vanishes on others.
# That made consecutive identical failures look like they alternated with
# "unknown", which defeated the same-error-twice guard and burned all four
# retries on one standing outage.
#
# The result record is always present and never rewritten, so it is the primary
# source; provider codes are reported as supporting detail but do not change the
# class, precisely because their visibility is unreliable.
#
# Usage: ./error_signature.sh <attempt-jsonl> [attempt-agy-log]
set -uo pipefail
J="${1:?usage: error_signature.sh <attempt.jsonl> [attempt.agy.log]}"
L="${2:-}"

python3 - "$J" "$L" <<'PY'
import sys, json, re, os
j, l = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "")
err = ""
for line in open(j, errors="replace"):
    line = line.strip()
    if not line.startswith("{"): continue
    try: d = json.loads(line)
    except Exception: continue
    if d.get("event") == "result":
        r = d.get("result") or {}
        err = str(r.get("error") or r.get("status") or "")

blob = err
if l and os.path.exists(l):
    try: blob += " " + open(l, errors="replace").read()
    except Exception: pass

provider = bool(re.search(r"Error 503|Error 429|UNAVAILABLE|high demand|RESOURCE_EXHAUSTED", blob))

e = err.lower()
if "agent execution terminated" in e:      cls = "EXECUTOR_TERMINATED"
elif "agent executor error" in e:          cls = "EXECUTOR_TERMINATED"
elif "error in generator" in e:            cls = "EXECUTOR_TERMINATED"
elif "timeout" in e:                       cls = "TIMEOUT"
elif err:                                  cls = "OTHER:" + re.sub(r"[^a-z ]", "", e)[:40].strip()
else:                                      cls = "UNKNOWN"

print("%s|provider_unavailable=%s" % (cls, "yes" if provider else "no"))
PY
