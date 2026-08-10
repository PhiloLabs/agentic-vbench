# Independent observability audit

**Verdict: PASS.**

An independent reviewer sampled 19 clearances across all five legs, all status
classes, both overshoot buckets, and all three control dimensions. Enlarged
frames were inspected before issue, near execution, at completion or violation,
and after overshoot where applicable.

| Evidence class | Audited examples | Result |
|---|---|---|
| heading | complied, late, superseded, small and large overshoot | Compass-card movement, reversal, capture, and hold were visible. |
| altitude | complied, late, superseded, incomplete, large overshoot | Altimeter and vertical trend supported all labels. |
| airspeed | complied, late, incomplete, violated, small and large overshoot | The needle visibly swept across 57–166 knots and supported all speed labels. |
| leg boundaries | all four cuts at 720-second intervals | Hard resets were visually unmistakable within 0.2 seconds. |
| audio | 65 clearances | Isolated, unclipped speech with no overlap; command direction and target were recoverable. |
| leakage | full panel and metadata | No selected-heading, selected-altitude, selected-speed, subtitle, chapter, or command-text display. |

Representative checks included:

- leg 1: delayed heading, large altitude overshoot, small speed overshoot,
  heading supersession, incomplete altitude, and wrong-direction speed;
- leg 2: delayed speed, small altitude overshoot, and large heading overshoot;
- leg 3: delayed altitude, large speed overshoot, and small heading overshoot;
- leg 4: delayed heading, altitude supersession, and small speed overshoot;
- leg 5: large altitude overshoot, heading supersession, incomplete altitude,
  and wrong-direction speed.

Every scored field was judged recoverable from the audio, visible instruments,
chronology, and the public leg-boundary definitions.

## All-event reproducibility package

`audit_all_events.py` extracts the full six-pack at issue, maximum commanded
progress, execution, completion, and window-end moments for every clearance.
The committed `observability_all_events.json` records 65 events, 300 rendered
crops, every expected state snapshot, the exact frame timestamps, and SHA-256
for each crop. Peak progress independently recomputed from telemetry differs
from committed truth by at most 1.3 units at the available sample cadence.

The complete crop set and five aggregate contact sheets are persisted
under the managed research result:

```text
reports/observability-all-events/
```

This makes the 19-event independent visual audit reproducible and gives
reviewers deterministic access to rendered evidence for all 65 clearances
without committing the large derived image set.
