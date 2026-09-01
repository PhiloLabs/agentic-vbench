# Can an agent see how the step was performed?

Review round 2 asked for a compact per-tag audit of the newly scored `error` field: what in
the supplied video lets an agent tell the annotated error from the intended action, and the
opposite question, whether anything readable hands it the tag without judging the
performance.

This directory holds the answer. The half that needs eyes is below, with the frames it
rests on. The half a machine can check is `../audit_error_observability.py`, which
recomputes every count quoted here and fails if it stops being true.

Short version: every tag that can decide a row has agent-visible evidence, exhibited below
for each. The two categories with no visual definition, `Other` and `Missing Step`, are
never a row's only tag, so no row is ever scored on recognising them. Nothing we ship, and
nothing readable in shot, names the tag. **No row is masked or excluded.**

## Method

Twenty-eight rows were drawn from the 22 shipped recordings: up to three per tag, all of
them for the rare tags, plus six rows the release annotates as performed correctly. Slots
were shuffled and the tags were held back, so the first pass was a blind read of nine
frames spread across each step, decoded from the same 1080p derivatives the image ships.
The blind pass was scored afterwards against `key.json`.

The blind pass is not the evidence. It is the reason to distrust a cheap look: reading
nine downscaled frames, the annotated tag was recovered on roughly three rows in ten. What
the blind pass established is where the information actually lives.

## The finding that decided the rest

**The evidence is in the pixels, but not in a downscaled whole frame.** Instrument
readouts are legible in the shipped derivative when cropped at native resolution and
unreadable when the frame is scaled to fit a vision model. The agent has `ffmpeg` and can
crop; what the task demands is knowing where and when to look. That is the work, and it is
why a competent agent still scores under the gate rather than at zero.

## Per-tag evidence

`rows` is how many instances the tag is the only tag on, which is the only case where the
agent has to recognise that tag rather than name a co-tag.

| tag | rows | what makes it visible | exhibit |
|---|---:|---|---|
| Order Error | 43 | The tablet in shot renders the recipe's canonical step list; the performed order comes from the agent's own transcript. The two differ, and the difference is the tag. | `order_P_tablet_canonical_list.jpg` |
| Technique Error | 36 | Gross substitution of method. `R` at 162 s squeezes jelly from a squeeze bottle where the step reads "use the knife to scoop jelly from the jar". | `technique_R_jelly_squeeze_bottle.jpg` |
| Preparation Error | 27 | Gross substitution of ingredient or vessel. `A` at 215 s handles an Arm & Hammer baking soda box during "Measure 1/8 teaspoon of baking powder". | `preparation_A_baking_soda_box.jpg` |
| Measurement Error | 20 | Quantity and implement, not graduations. `A` at 611 s takes repeated scoops with an ordinary spoon straight from the jar for "Take 1 tablespoon of marinara sauce", with the measuring spoons hanging unused in the same frame. | `measurement_A_marinara_spoonfuls.jpg` |
| Timing Error | 13 | The appliance display. `H` keys the microwave to `3:00` for "Microwave the ramen for 4 minutes"; the countdown at 265 s confirms it started there. | `timing_H_microwave_set_to_3min.jpg` |
| Temperature Error | 1 | The instrument. `J` at 605 s reads `79.4` with the probe in a jar of solids, for "Once the water has boiled, check the temperature of the water". This is the only row in the key where Temperature Error stands alone. | `temperature_J_thermometer_79F.jpg` |
| Other | 0 | Never a row's only tag. | |
| Missing Step | 0 | Never a row's only tag. | |

Two structural results carry as much weight as the exhibits, and both are recomputed by the
script rather than asserted here:

- **`Other` and `Missing Step` are never alone.** Every row carrying either also carries a
  tag with a visual definition, and any annotated tag scores, so a catch-all with no visual
  signature is never what a row turns on.
- **No row is scored against a twin it cannot be told apart from.** Two row pairs in the
  key sit inside each other's tolerance on both boundaries, which makes them the same
  frames as far as the agent is concerned. Neither pair disagrees on the tag.

One more shortcut was closed by measurement rather than by intent: the label ids are
alphabetical, not recipe order. Consecutive steps increase in id 46.6% of the time, which
is chance. An agent that wants the canonical order has to read it off the tablet.

## The opposite direction: does anything give the tag away?

- **What we ship.** Two agent-visible files. Only `instruction.md` names the tags, listing
  all eight as the vocabulary, tied to no row. The media manifest is not shipped, and the
  filenames are single letters.
- **The tablet in shot.** It renders the recipe step list and highlights a step. Read at
  native resolution in two different kitchens (`F` at 421 s, `P` at 800 s), it carries the
  step texts and nothing else. No error wording, no marking that separates an error step
  from a correct one. See `shortcut_F_tablet_no_error_text.jpg`.
- **The release's own wording.** None of the 352 distinct step descriptions the release
  ships is phrased as an error instruction. The induced error is not written into the step
  text, so it cannot reach the tablet through it.
- **The highlight is not a reliable pointer.** In `P` at 800 s the performed step is the
  cheddar sprinkle while the highlight sits on the next step, and a step performed earlier
  appears last on screen. The tablet helps, and it does not hand over the answer.

## Limitations, stated

- Measuring-implement graduations were not legible in a bounded search. The Measurement
  evidence rests on quantity and implement choice, which is a gross signal; it will not
  carry every one of the 20 rows, only the ones where the deviation is gross.
- Technique Error and Preparation Error overlap. On a row where one of them stands alone,
  an agent that sees the deviation can still name the other and score nothing.
- Two rows put label and picture in tension. `G`'s Missing Step row carries a 6.2 s span in
  which a lid visibly goes on, and `U`'s lemon-for-lime reads as a measurement or
  preparation problem but is tagged Other. Both rows are multi-tag, so neither is
  load-bearing, but both are worth knowing about.
- During this audit a blurred tablet line was misread as an induced-error instruction
  ("...instead of oregano"). Checking it against the release showed the line is "Sprinkle
  oregano in the bowl" and that no released description contains such wording at all. The
  claims above are backed by the corpus check, not by reading blur.

## Treatment

None applied. The maintainer's instruction was to mask, exclude, or otherwise treat any
retained row whose tag cannot be supported from agent-visible evidence, rather than force
a hidden label. On this audit every load-bearing category has exhibited evidence and the
two undefined categories are never load-bearing, so there is no row that meets that
condition. If the maintainer reads the limitations above as reaching the sole Measurement
rows, the cheapest treatment that does not move `N` is to accept any tag on those 20 rows,
and the count is stated here so that decision needs no new measurement.

## Reproducing the sample

`sample.json` is the 28 rows with their tags. `make_contact_sheets.py` rebuilds the nine
frame contact sheets from the shipped derivatives:

```
python3 provenance/observability/make_contact_sheets.py provenance/observability <media-dir>
```

The sheets are about 10 MB and are not committed. The exhibits above are, and each is a
crop or strip of the same frames at the resolution named in the table.
