# Codex calibration under the efficiency-guidance rules (superseded)

Run of 2026-08-30 21:07-21:43Z, rules sha256 3171bb1d.

Result: reward 2e-05 (clears < 0.10) but **31 command turns**, which does not
clear the family requirement `tool_call_turns > 50`.

Kept because it is the measurement behind removing the "Working efficiently"
section from the shared rules. Against the 2026-08-29 run (53 turns, reward
0.001858) the turn count fell 42% and per-field scores fell with it
(rally_discovery f1 0.530 -> 0.210, stroke_timing f1 0.313 -> 0.029).

Not a causal isolation: the two runs differ in two ways at once -- this one adds
the efficiency section and drops the earlier "A complete best-effort answer beats
an empty one" line -- and each condition has n=1. What is established is the
outcome, not the mechanism.
