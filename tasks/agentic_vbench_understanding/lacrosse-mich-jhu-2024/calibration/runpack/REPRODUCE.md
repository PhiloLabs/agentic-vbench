# Reproduce the task video from its public source (fallback only)

Prefer the direct download: set VIDEO_URL.txt and run `./fetch_video.sh`.
Use this only if you cannot obtain the hosted file.

Source: full-game broadcast upload, YouTube id `jr-le7CCyEs` (download at 720p).

    yt-dlp -f "bv*[height<=720]" -o raw.mp4 "https://www.youtube.com/watch?v=jr-le7CCyEs"
    ffmpeg -i raw.mp4 \
      -vf "scale=1280:720,drawbox=x=0:y=505:w=1280:h=215:color=black:t=fill" \
      -an -c:v libx264 -crf 23 -preset veryfast -map_metadata -1 -map_chapters -1 \
      -movflags +faststart materials/game.mp4

Note: a fresh re-download + re-encode is very unlikely to be BYTE-identical to
the official file, so its SHA-256 will differ from materials/game.mp4.sha256.
The result is task-EQUIVALENT (same frames, same lower-third mask, same timing)
and fine for calibration, but stage_workspace.sh's exact-hash gate will refuse
it. To proceed with a reproduced file, re-pin it and note it in scores.md:

    shasum -a 256 materials/game.mp4 > materials/game.mp4.sha256
