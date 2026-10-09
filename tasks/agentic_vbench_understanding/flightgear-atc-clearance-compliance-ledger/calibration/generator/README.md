# Fixed-release media and ground-truth generator

This directory contains the exact source used to generate and validate the
fixed hosted recording.

Pipeline:

```text
build_full_dataset.py
  -> five isolated FlightGear C172P legs
  -> run_pilot.py + pilot_lib.py + telemetry_protocol.xml
  -> derive_ground_truth.py
  -> validate_run.py
  -> build_release.py
  -> audit_release.py
```

The scripts require FlightGear 2020.3.18, the packaged C172P, Xvfb, FFmpeg,
eSpeak NG, and Python 3.12. Large outputs default to managed `/scratch`
storage. `generation_manifest.json` records the exact generator-file,
configuration, alignment, segment-video, and release-video hashes used for the
committed verifier truth.

Controller targets and behavior are scenario-controlled, but capture and
integration use wall-clock scheduling. A fresh run may therefore differ by
sub-second timestamps and encoded bytes. The committed truth is reproducibly
derived from the fixed recorded command logs and telemetry whose hashes are in
`generation_manifest.json`; the generator does not claim byte-identical reruns.

`test_pilot.py` covers controller direction, scenario diversity, stable
completion, violations, supersession, overshoot derivation, and scorer failure
cases.
