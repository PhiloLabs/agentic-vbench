# Rollout records

The old Codex, Claude, and metadata-less schema-invalid Gemini files have been
removed. They predated the final scorer and pinned isolated environment and cannot
be cited as qualification results.

For the clean pass, retain the unmodified harness trajectory first, run
`tools/scrub_trajectory.py` only if a release asset requires local-path or opaque
payload redaction, and publish the raw or deterministically scrubbed whole file as a
fork release asset. Record its URL and SHA256 in `../scores.md`; do not replace the
raw trajectory with a summary.

Example deterministic scrub:

```bash
python3 tools/scrub_trajectory.py \
  --input /path/to/raw.jsonl \
  --output /path/to/release.jsonl \
  --replace-path "/Users/name=/home/agent"
```

The script sorts JSON object keys and emits one compact JSON object per line, so the
same input and replacement arguments reproduce the recorded digest.
