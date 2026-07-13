#!/usr/bin/env python3
"""Download SoccerNet 224p broadcast videos. REQUIRES the NDA password (email).
    SOCCERNET_PASSWORD=<pw> python download_videos.py --dir ./soccernet \
        --games "england_epl/2014-2015/2015-02-21 - 18-00 Chelsea 1 - 1 Burnley"
"""
import argparse, os
from SoccerNet.Downloader import SoccerNetDownloader
ap = argparse.ArgumentParser()
ap.add_argument("--dir", required=True)
ap.add_argument("--password", default=os.environ.get("SOCCERNET_PASSWORD"))
ap.add_argument("--split", nargs="+", default=["test"])
a = ap.parse_args()
assert a.password, "set --password or SOCCERNET_PASSWORD from the NDA email"
d = SoccerNetDownloader(LocalDirectory=a.dir)
d.password = a.password
d.downloadGames(files=["1_224p.mkv", "2_224p.mkv"], split=a.split)
print("224p videos ->", a.dir)
