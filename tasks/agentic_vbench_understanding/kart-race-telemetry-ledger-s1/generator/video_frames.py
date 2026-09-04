#!/usr/bin/env python3
"""Small ffmpeg helpers for reading raw frames out of a rendered race video."""
import subprocess

import numpy as np

FFPROBE = "/pkg/ffmpeg/4.2.2/bin/ffprobe"


def ffmpeg_exe():
    """Return the ffmpeg the generator encodes with (imageio-ffmpeg), else PATH ffmpeg."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def duration(video):
    """Return the video's duration in seconds."""
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", video], stdout=subprocess.PIPE, check=True).stdout
    return float(out.split()[0])


def burst(video, t, x, y, w, h, nframes):
    """Decode nframes consecutive grayscale frames at time t, cropped to (x, y, w, h).

    Returns a (frames, h, w) float32 array, or None if the decode came up short.
    """
    cmd = [ffmpeg_exe(), "-v", "error", "-ss", "%.3f" % t, "-i", video,
           "-frames:v", str(nframes),
           "-vf", "crop=%d:%d:%d:%d,format=gray" % (w, h, x, y),
           "-f", "rawvideo", "-"]
    out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout
    frame = w * h
    got = len(out) // frame
    if got < 1 or got < min(nframes, 5) and nframes > 1:
        return None
    return np.frombuffer(out[:got * frame], np.uint8).reshape(got, h, w).astype(np.float32)
