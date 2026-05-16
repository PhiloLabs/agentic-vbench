# Restore A Clipped Recording

I have a short mono speech recording at `/workspace/materials/noisy.wav`.
For a stretch in the middle, the audio sounds harsh and crunchy — like
the peaks of the waveform have been chopped off so the loud parts
distort. Outside that stretch the recording sounds fine.

Please rebuild the distorted peaks so the voice sounds natural again
through that stretch. Leave the already-clean parts unchanged.

## What to deliver

- `/workspace/output/enhanced.wav` — 16-bit PCM mono at 16 kHz, same
  total length (sample count) as the input.

## Environment

- CPU only, ~30 min timeout. Internet available for `pip install`.
