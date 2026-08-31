#!/usr/bin/env python3
"""Fetch one public YouTube adaptive format using the Android player API."""

from __future__ import annotations

import argparse
import json
import shutil
import time
import urllib.request
from pathlib import Path


CLIENT_VERSION = "20.10.38"
USER_AGENT = (
    f"com.google.android.youtube/{CLIENT_VERSION} "
    "(Linux; U; Android 14) gzip"
)


def player_response(video_id: str) -> dict[str, object]:
    payload = {
        "videoId": video_id,
        "context": {
            "client": {
                "clientName": "ANDROID",
                "clientVersion": CLIENT_VERSION,
                "hl": "en",
                "gl": "US",
            }
        },
    }
    request = urllib.request.Request(
        "https://www.youtube.com/youtubei/v1/player?prettyPrint=false",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def resolve_format(video_id: str, itag: int) -> tuple[str, int | None]:
    data = player_response(video_id)
    status = data.get("playabilityStatus", {})
    if status.get("status") != "OK":
        raise RuntimeError(f"YouTube player rejected video: {status}")
    formats = data.get("streamingData", {}).get("adaptiveFormats", [])
    match = next((item for item in formats if item.get("itag") == itag), None)
    if match is None or "url" not in match:
        available = [item.get("itag") for item in formats]
        raise RuntimeError(f"itag {itag} unavailable; available itags: {available}")
    length = int(match["contentLength"]) if "contentLength" in match else None
    return match["url"], length


def download(video_id: str, itag: int, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + ".part")
    last_error: Exception | None = None
    for attempt in range(1, 13):
        try:
            url, expected_length = resolve_format(video_id, itag)
            offset = partial.stat().st_size if partial.exists() else 0
            if expected_length is not None and offset == expected_length:
                partial.replace(output)
                return
            headers = {"User-Agent": USER_AGENT}
            if offset:
                headers["Range"] = f"bytes={offset}-"
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=120) as response:
                resumed = offset > 0 and response.status == 206
                mode = "ab" if resumed else "wb"
                with partial.open(mode) as stream:
                    shutil.copyfileobj(response, stream, length=1024 * 1024)
            if expected_length is not None and partial.stat().st_size != expected_length:
                raise RuntimeError(
                    f"downloaded {partial.stat().st_size} bytes; expected {expected_length}"
                )
            partial.replace(output)
            return
        except Exception as exc:
            last_error = exc
            if attempt == 12:
                break
            time.sleep(attempt * 2)
    raise RuntimeError(f"failed to download {video_id} itag {itag}") from last_error


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--itag", type=int, required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    download(args.video_id, args.itag, args.output)


if __name__ == "__main__":
    main()
