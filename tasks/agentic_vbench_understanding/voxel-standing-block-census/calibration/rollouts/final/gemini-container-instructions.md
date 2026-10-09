# Read this first

You are being asked to solve one video-understanding task and nothing else. Everything you
need is described here and in `brief.md`, which sits next to this file.

Work through the task on your own, from start to finish, without asking questions. When you
are finished, write your answer to the file named at the bottom of this page.

---

## 1. The task

`brief.md` is the complete task statement. Read it now, before anything else, and follow it
exactly.

## 2. Where the video is

The recording is not in this folder. It lives in the task environment, a container with no
network. You reach that environment with the script `task.sh`, which sits next to this file:

    ./task.sh '<your command>'

It runs the command in there, waits, and prints the exit code and the output. The working
directory inside is `/workspace`, and it holds:

    /workspace/materials/session.mp4   the recording the brief refers to
    /workspace/work/                   scratch space, writable

`ffmpeg` 7.1.5, `ffprobe`, `python3` 3.12, numpy, scipy, opencv, scikit-image and pillow are
all installed in there, with 4 CPUs. Nothing needs installing.

**Do not use `docker` yourself, and do not try to reach any container directly.** `task.sh`
is the only way in, and it is enough.

## 3. How to actually look at the video

You cannot watch the recording. You extract still frames from it and look at those.

`/workspace/work/` inside the task environment is the *same directory* as the folder this
file is in. So a frame written inside to `/workspace/work/frames/x.jpg` appears immediately
at `frames/x.jpg` next to this file, and you can open it with your normal file reading tool
to actually see the picture.

A worked example. To look at the moment 5 minutes into the recording:

    ./task.sh 'mkdir -p /workspace/work/frames && ffmpeg -y -loglevel error -ss 300 -i /workspace/materials/session.mp4 -frames:v 1 -q:v 2 /workspace/work/frames/t300.jpg'

then open `frames/t300.jpg`.

Two things that make this much faster:

- Put `-ss <seconds>` **before** `-i`. That seeks instead of decoding from the start.
- Extract many frames in one `task.sh` call with a shell loop or `xargs -P4`, rather than one
  call per frame.

You can also write a python script into `/workspace/work/` through `task.sh` and run it in
there, which is usually the sane way to do anything repetitive.

## 4. Rules you must follow

These are hard rules. A run that breaks any of them is thrown away.

1. **Work only from the recording.** That is your entire evidence base.
2. **No web.** Do not search the web, do not fetch any URL, do not use any browser or search
   tool, and do not consult any external record or summary.
3. **Do not go looking for an answer key.** Stay inside this folder and inside the task
   environment. Do not read, list or search other parts of the file system for files that
   might contain the answer.
4. **Do not stop early and do not decline.** You must produce an integer for every one of the
   six block types at every one of the thirty checkpoints. Where you are unsure, give your
   best estimate rather than leaving anything out.

## 5. Where to write the answer

`output/solution.json`, next to this file, in the format `brief.md` gives. You can write it
from inside the task environment with `./task.sh` to `/workspace/work/output/solution.json`,
or directly with your own file tools. Rewrite the whole file every few checkpoints rather
than only at the end.
