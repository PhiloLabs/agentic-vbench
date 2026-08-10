# C172P airspeed-needle property audit

The FlightGear 2020.3.18 C172P analog airspeed needle does **not** read the
generic `/instrumentation/airspeed-indicator/indicated-speed-kt` node under the
null FDM used for generation. Its model animation reads:

```text
/fdm/jsbsim/velocities/vias-kts
```

Source: C172P `Models/Interior/Panel/Instruments/asi/asi.xml`, `Needle` rotate
animation:
https://github.com/c172p-team/c172p/blob/master/Models/Interior/Panel/Instruments/asi/asi.xml

The committed generic protocol writes the controller airspeed to both
`/velocities/airspeed-kt` and the exact `fdm/jsbsim/velocities/vias-kts`
rendering property, logs both, and validation requires zero/near-zero
divergence. Ground truth uses `fdm_vias_kt` because it is the property that
drives the visible needle.

Reproducible final-media crops are retained in the managed all-event evidence
package. For clearance 3:

- `c03_issue_120.000.png`, SHA-256
  `e03139aa5920d33e16f45f2981fcbfe461340df7a892dbe7b0847f2055dca665`;
- `c03_completion_139.167.png`, SHA-256
  `eeaa05e06c0a1de798ed0866ab0b55d3e0ed1e1c98e14b49e45efdcb7ffc3714`;
- `c03_maximum_progress_145.142.png`, SHA-256
  `9ff467b76839b6e86db196eae6550b4f39b5c5531b624ec822668cacfa4276b8`.

Both images were extracted from the pinned hosted MP4 with:

```bash
ffmpeg -ss <time> -i flight.mp4 -frames:v 1 \
  -vf 'crop=170:170:430:300,scale=680:680' output.png
```

The release audit additionally checks the rendering property against the
controller airspeed for every telemetry sample; maximum error is 0.0 knots.
