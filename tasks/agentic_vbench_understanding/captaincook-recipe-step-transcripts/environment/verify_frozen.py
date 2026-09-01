#!/usr/bin/env python3
"""Check a built task image against the frozen record.

    python3 environment/verify_frozen.py <image>

`frozen.json` records what the calibration ran against: the base image by digest, the
task image's own id and layers, and the SHA256 of each of the 22 files the agent can see
in /baked. The image id is not reproducible across builds, since layer metadata carries
timestamps, so it is recorded rather than required. What IS required is the content: the
22 baked files must hash to what the record says.

That requirement is not a formality. Two builds of this Dockerfile, run separately on the
same machine, produced byte-identical /baked files, so a mismatch here means the media
changed, not that the build was noisy.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    image = sys.argv[1]
    rec = json.loads((HERE / "frozen.json").read_text())
    want = rec["baked_sha256"]
    assert want, "the record lists no baked files, so this check cannot fail"

    r = subprocess.run(
        ["docker", "run", "--rm", image, "bash", "-lc",
         "cd /baked && sha256sum *.mp4 | sort"],
        capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        print(f"could not read /baked from {image}:\n{r.stderr.strip()}", file=sys.stderr)
        return 2
    got = {}
    for line in r.stdout.splitlines():
        h, n = line.split()
        got[n] = h
    assert got, f"read no files out of {image}:/baked"

    missing = sorted(set(want) - set(got))
    extra = sorted(set(got) - set(want))
    bad = sorted(n for n in set(want) & set(got) if want[n] != got[n])
    if missing or extra or bad:
        for n in missing:
            print(f"  MISSING  {n}")
        for n in extra:
            print(f"  EXTRA    {n}")
        for n in bad:
            print(f"  CHANGED  {n}\n    recorded {want[n]}\n    found    {got[n]}")
        print(f"{image} does not carry the frozen media", file=sys.stderr)
        return 1

    here = subprocess.run(["docker", "image", "inspect", image, "--format", "{{.Id}}"],
                          capture_output=True, text=True).stdout.strip()
    print(f"{image}: all {len(want)} baked files match the frozen record")
    print(f"  base pinned in the Dockerfile: {rec['base_image']}")
    print(f"  image the calibration ran on:  {rec['task_image_id']}")
    # Say which of the two cases this is, rather than printing two hex strings and
    # leaving the reader to compare them.
    if here == rec["task_image_id"]:
        print(f"  this image:                    the same one")
    else:
        print(f"  this image:                    {here}")
        print(f"  a different build, carrying the same media. Image ids are not "
              f"reproducible across builds; the media is.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
