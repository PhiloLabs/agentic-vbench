# Remove Reverb From A Recording

I have a short mono speech recording at `/workspace/materials/noisy.wav`.
For a stretch in it, the voice sounds reverby / echoey, as if
the speaker stepped into a large empty room. The rest of the recording
is clean and dry.

Please reduce the reverb in the affected stretch so the voice sounds as
dry as the rest of the recording. Leave the already-clean parts alone.

## What to deliver

- `/workspace/output/enhanced.wav` — 16-bit PCM mono at 16 kHz, same
  total length (sample count) as the input.

## Environment

- CPU only, ~30 min timeout. Internet available for `pip install`.
