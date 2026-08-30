#!/usr/bin/env python3
"""Build the native raw transcript archive: everything the harness wrote, minus secrets.

    python3 calibration/make_raw_archive.py --home /Users/someone --out DIR \
        codex=/abs/codex.jsonl claude=/abs/session.jsonl antigravity=/abs/anti.jsonl

This is the counterpart to ship_rollout.py and exists because that script is lossy in two
ways a reviewer may not accept. It elides base64 image blobs, so the frames the agent
actually looked at are gone. And it rewrites the run directory and the materials
directory to their in-image paths, which makes a run that happened on the host read as
though it happened in the container. Both are the right trade for a file committed to a
benchmark repository and the wrong one for an audit.

So this script redacts TWO things and nothing else:

  1. the home directory prefix, which is personal, becomes <HOME>
  2. credentials, which are secret, become <REDACTED:kind>

Left alone on purpose: every command, every tool result, every frame, the turn structure,
and the real host paths, because the host/container boundary is one of the things under
audit.

Redaction that cannot be checked is a claim, so each rule ships with a positive control:
a canary line carrying one instance of every pattern is passed through the same code, and
the run fails unless every canary is caught. A redactor that silently matches nothing
would otherwise report a clean archive. The frames get a control of their own in the
opposite direction: the number of long base64 strings in the output must EQUAL the number
in the input, so a future edit that starts eliding them again cannot pass quietly.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

# Credential shapes. Each is (kind, compiled pattern, canary that must be caught).
SECRETS = [
    ("anthropic-key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
     "sk-ant-api03-" + "A" * 40),
    ("openai-key", re.compile(r"\bsk-(?!ant-)[A-Za-z0-9_\-]{20,}"),
     "sk-" + "B" * 40),
    ("github-token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}"),
     "ghp_" + "C" * 36),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
     "github_pat_" + "D" * 60),
    ("hf-token", re.compile(r"\bhf_[A-Za-z0-9]{20,}"),
     "hf_" + "E" * 34),
    ("aws-key-id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
     "AKIA" + "F" * 16),
    ("bearer", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}"),
     "Bearer " + "G" * 40),
]

# A base64 string long enough to be an image. Same threshold ship_rollout.py elides at,
# used here only to COUNT them, so the two files can be compared on exactly that axis.
BLOB = re.compile(r'"[A-Za-z0-9+/]{2000,}={0,2}"')


def redact(line: str, home: str, hits: collections.Counter) -> str:
    for kind, pat, _ in SECRETS:
        line, n = pat.subn(f"<REDACTED:{kind}>", line)
        if n:
            hits[kind] += n
    if home:
        line, n = line.replace(home, "<HOME>"), line.count(home)
        if n:
            hits["home-prefix"] += n
    return line


# A harness startup row that lists the operator's own installed skills. Those names and
# descriptions are private tooling, they say nothing about this task, and they would be
# published along with everything else. The row, its type and the skill COUNT stay,
# because what the harness injected at startup IS part of the environment under audit;
# only the names and the prose go.
PRIVATE_ATTACHMENTS = {"skill_listing"}


def redact_attachment(line: str, hits: collections.Counter) -> str:
    if '"skill_listing"' not in line:
        return line
    try:
        d = json.loads(line)
    except Exception:
        return line
    a = d.get("attachment")
    if not isinstance(a, dict) or a.get("type") not in PRIVATE_ATTACHMENTS:
        return line
    for k in ("content", "names"):
        if k in a:
            n = len(json.dumps(a[k], ensure_ascii=False))
            a[k] = f"<REDACTED: operator's private skill {k}, {n} chars>"
    hits["skill-listing"] += 1
    return json.dumps(d, ensure_ascii=False)


def attachment_control() -> None:
    """Must redact a skill listing, and must leave every other attachment alone."""
    hits: collections.Counter = collections.Counter()
    private = json.dumps({"type": "attachment", "attachment": {
        "type": "skill_listing", "skillCount": 2, "isInitial": True,
        "names": ["secret-skill-one", "secret-skill-two"],
        "content": "- secret-skill-one: does a private thing"}}, ensure_ascii=False)
    out = redact_attachment(private, hits)
    if "secret-skill" in out or not hits.get("skill-listing"):
        sys.exit("attachment control FAILED: a skill listing survived redaction")
    if '"skillCount": 2' not in out:
        sys.exit("attachment control FAILED: the skill count should survive, it is harness metadata")
    keep = json.dumps({"type": "attachment", "attachment": {
        "type": "agent_listing_delta", "addedTypes": ["calib-opus48"]}}, ensure_ascii=False)
    if redact_attachment(keep, hits) != keep:
        sys.exit("attachment control FAILED: a non-skill attachment was modified")
    print("  attachment control: skill listing redacted, count kept, other attachments untouched")


def control(home: str) -> None:
    """Every rule must fire on a line built to trigger it, or the archive is not trusted."""
    canary = " ".join(c for _, _, c in SECRETS) + (f" {home}/somewhere" if home else "")
    hits: collections.Counter = collections.Counter()
    out = redact(canary, home, hits)
    missed = [kind for kind, _, c in SECRETS if c in out or not hits.get(kind)]
    if home and (home in out or not hits.get("home-prefix")):
        missed.append("home-prefix")
    if missed:
        sys.exit(f"positive control FAILED, these rules matched nothing: {missed}")
    print(f"  positive control: all {len(SECRETS) + (1 if home else 0)} rules fired on the "
          f"canary line and nothing survived")


# A second, independent pass over the FINISHED archive, looking for credential shapes the
# pattern list above does not know: any <word suggesting a credential><separator><long
# opaque value>. Deliberately noisy, because the failure that matters is being blind, not
# being wrong. It carries its own canaries for the same reason, and two of them were added
# after they caught real blind spots: `_` is a word character, so a naive \btoken never
# matched HF_TOKEN, and "Authorization: Bearer <v>" has no punctuation between the keyword
# and the value.
BLOB_RUN = re.compile(r"[A-Za-z0-9+/]{200,}={0,2}")
KV = re.compile(r"(?i)[A-Za-z0-9_]{0,32}(token|secret|password|passwd|api[_-]?key"
                r"|access[_-]?key|auth[a-z]{0,20}|credential[a-z]{0,3}|bearer)[A-Za-z0-9_]{0,32}"
                r"[\"']?[ \t]{0,4}[:=\s][ \t]{0,4}[\"']?([A-Za-z0-9_\-.]{16,120})")
KV_CANARIES = [
    '{"env":{"HF_TOKEN":"abcdefghijklmnopqrstuvwx"}}',
    "export API_KEY=ZZZZZZZZZZZZZZZZZZZZZZZZ",
    '  "password": "hunter2hunter2hunter2hunter2"',
    "Authorization: Bearer QQQQQQQQQQQQQQQQQQQQQQQQ",
    "ANTHROPIC_AUTH_TOKEN=sk-ant-aaaaaaaaaaaaaaaaaaaaaaaa",
    '"credentials":{"secret_access_key":"wJalrXUtnFEMIK7MDENGbPxRfiCY"}',
]
BENIGN = re.compile(r"(?i)^(null|none|true|false|undefined|<redacted|xxx+|\.\.\.)")


def sweep(out: Path) -> None:
    blind = [c for c in KV_CANARIES if not KV.findall(c)]
    if blind:
        sys.exit(f"the independent sweep is blind to {len(blind)} of {len(KV_CANARIES)} "
                 f"canaries, so a clean result from it would mean nothing")
    found = collections.Counter()
    for f in sorted(out.glob("*.native.jsonl")):
        for line in f.open(errors="replace"):
            # Long base64 runs are stripped first: they cannot hold a real credential
            # pair, and leaving them in makes this pattern backtrack for minutes.
            for kind, value in KV.findall(BLOB_RUN.sub("<b64>", line)):
                if not BENIGN.match(value):
                    found[(f.name, kind.lower())] += 1
    if found:
        print("  independent sweep flagged pairs to inspect BEFORE publishing:")
        for (fname, kind), n in found.most_common(12):
            print(f"    {fname} {kind} x{n}")
        sys.exit("archive not certified")
    print(f"  independent sweep: {len(KV_CANARIES)}/{len(KV_CANARIES)} canaries caught, "
          f"zero credential-shaped pairs in the archive")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sources", nargs="+", help="name=/abs/path, in the order to archive")
    ap.add_argument("--home", default=str(Path.home()))
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    home = args.home.rstrip("/")

    control(home)
    attachment_control()
    args.out.mkdir(parents=True, exist_ok=True)
    index = {}

    for spec in args.sources:
        name, _, path = spec.partition("=")
        src = Path(path)
        if not src.exists():
            sys.exit(f"no such file: {src}")
        hits: collections.Counter = collections.Counter()
        blobs_in = blobs_out = lines = 0
        dst = args.out / f"{name}.native.jsonl"
        h = hashlib.sha256()
        with src.open(errors="replace") as fin, dst.open("w") as fout:
            for line in fin:
                if not line.strip():
                    continue
                lines += 1
                blobs_in += len(BLOB.findall(line))
                line = redact_attachment(line.rstrip("\n"), hits)
                line = redact(line, home, hits) + "\n"
                blobs_out += len(BLOB.findall(line))
                fout.write(line)
                h.update(line.encode())
        # The frames must survive. This is the control in the other direction: a change
        # that starts eliding them again fails here instead of shipping quietly.
        if blobs_in != blobs_out:
            sys.exit(f"{name}: {blobs_in - blobs_out} image blob(s) lost in redaction")
        index[name] = {
            "source_basename": src.name,
            "lines": lines,
            "bytes": dst.stat().st_size,
            "sha256": h.hexdigest(),
            "image_blobs_retained": blobs_out,
            "redactions": dict(sorted(hits.items())),
        }
        red = ", ".join(f"{k}={v}" for k, v in sorted(hits.items())) or "none"
        print(f"  {name:<12} {lines:6d} lines  {dst.stat().st_size/1e6:7.2f} MB  "
              f"frames kept {blobs_out:4d}  redacted: {red}")

    sweep(args.out)
    (args.out / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    print(f"  index written to {args.out / 'index.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
