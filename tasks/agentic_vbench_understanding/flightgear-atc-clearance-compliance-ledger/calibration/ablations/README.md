# Anti-shortcut trajectories

These are measured GitHub Copilot CLI / GPT-5.6 Sol runs against degraded
inputs:

- `no-media_*`: prompt only;
- `single-frame_*`: one representative cockpit frame;
- `video-only_*`: the full recording with audio removed;
- `audio-only_*`: the audio track without video;
- `frame-dump-no-tools_*`: ten fixed frame sheets plus the offline ASR
  transcript, with media-analysis tools unavailable.

Each JSONL file is the raw trajectory with local absolute paths redacted. The
measured rewards and verifier diagnostics are recorded once in `../scores.md`;
duplicate solution and reward sidecars are intentionally omitted.
