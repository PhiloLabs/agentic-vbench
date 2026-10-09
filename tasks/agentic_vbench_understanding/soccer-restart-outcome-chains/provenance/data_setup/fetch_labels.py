#!/usr/bin/env python3
"""Fetch this match's public SoccerNet-v2 labels at a pinned revision and verify them.

No account, token or NDA is needed: SoccerNet/SN-Labels is a public Hugging Face dataset.
Two files are used. Labels-v2.json is the action-spotting log the answer key is derived
from (provenance/build_gt.py). Labels-cameras.json is the shot-change log that places
each half on the clip's timeline (provenance/align_halves.py).

    python3 fetch_labels.py --out ./labels
"""
import argparse
import hashlib
import pathlib
import urllib.parse
import urllib.request

REVISION = "8e01649fe968da9f541c91019b65b3028b2425fc"
GAME = "germany_bundesliga/2016-2017/2017-03-04 - 17-30 Dortmund 6 - 2 Bayer Leverkusen"
FILES = {
    "Labels-v2.json": "2dce207c4172ab0a4dae1952d51bfcf1dbc978795c7809f6bc5e10f7e000f444",
    "Labels-cameras.json": "7a418df51f9e144c8e6b39f863ede467883510f58b856871423bfebc80ae9e57",
}

ap = argparse.ArgumentParser(description="Fetch and verify the pinned SoccerNet labels.")
ap.add_argument("--out", required=True, type=pathlib.Path)
a = ap.parse_args()
a.out.mkdir(parents=True, exist_ok=True)
for name, digest in FILES.items():
    url = (f"https://huggingface.co/datasets/SoccerNet/SN-Labels/resolve/{REVISION}/"
           + urllib.parse.quote(f"{GAME}/{name}"))
    data = urllib.request.urlopen(url, timeout=120).read()
    got = hashlib.sha256(data).hexdigest()
    assert got == digest, f"{name}: sha256 {got} does not match the pinned {digest}"
    (a.out / name).write_bytes(data)
    print(f"{name}: {len(data)} bytes, sha256 verified -> {a.out / name}")
