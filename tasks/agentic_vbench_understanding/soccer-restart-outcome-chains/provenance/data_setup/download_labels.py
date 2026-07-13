#!/usr/bin/env python3
"""Download SoccerNet-v2 action-spotting LABELS (Labels-v2.json). NO NDA needed.
    pip install SoccerNet
    python download_labels.py --dir ./soccernet --split test
"""
import argparse
from SoccerNet.Downloader import SoccerNetDownloader
ap = argparse.ArgumentParser()
ap.add_argument("--dir", required=True)
ap.add_argument("--split", nargs="+", default=["test"])
a = ap.parse_args()
d = SoccerNetDownloader(LocalDirectory=a.dir)
d.downloadGames(files=["Labels-v2.json"], split=a.split)
print("labels ->", a.dir)
