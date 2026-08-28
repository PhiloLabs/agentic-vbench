You are given ONE still image from each of twenty-two videos, twenty-two images in all, in the order A through V. Each still is taken from the midpoint of its recording. You have NO video, NO tools, and no way to ask for another frame. Answer from the stills alone.

| video | path | length | time range |
|---|---|---|---|
| `A` | `/workspace/materials/A.mp4` | 15.8 min | `t = 0` to `t = 946.5` |
| `B` | `/workspace/materials/B.mp4` | 11.6 min | `t = 0` to `t = 694.4` |
| `C` | `/workspace/materials/C.mp4` | 13.0 min | `t = 0` to `t = 779.9` |
| `D` | `/workspace/materials/D.mp4` | 13.1 min | `t = 0` to `t = 783.2` |
| `E` | `/workspace/materials/E.mp4` | 17.4 min | `t = 0` to `t = 1044.3` |
| `F` | `/workspace/materials/F.mp4` | 10.9 min | `t = 0` to `t = 652.1` |
| `G` | `/workspace/materials/G.mp4` | 13.5 min | `t = 0` to `t = 809.7` |
| `H` | `/workspace/materials/H.mp4` | 10.1 min | `t = 0` to `t = 608.4` |
| `I` | `/workspace/materials/I.mp4` | 19.2 min | `t = 0` to `t = 1149.6` |
| `J` | `/workspace/materials/J.mp4` | 14.0 min | `t = 0` to `t = 837.4` |
| `K` | `/workspace/materials/K.mp4` | 12.8 min | `t = 0` to `t = 770.4` |
| `L` | `/workspace/materials/L.mp4` | 11.3 min | `t = 0` to `t = 676.5` |
| `M` | `/workspace/materials/M.mp4` | 17.0 min | `t = 0` to `t = 1020.7` |
| `N` | `/workspace/materials/N.mp4` | 10.0 min | `t = 0` to `t = 603.0` |
| `O` | `/workspace/materials/O.mp4` | 11.5 min | `t = 0` to `t = 687.5` |
| `P` | `/workspace/materials/P.mp4` | 15.5 min | `t = 0` to `t = 928.9` |
| `Q` | `/workspace/materials/Q.mp4` | 12.5 min | `t = 0` to `t = 748.8` |
| `R` | `/workspace/materials/R.mp4` | 11.8 min | `t = 0` to `t = 709.2` |
| `S` | `/workspace/materials/S.mp4` | 10.8 min | `t = 0` to `t = 649.8` |
| `T` | `/workspace/materials/T.mp4` | 13.6 min | `t = 0` to `t = 816.2` |
| `U` | `/workspace/materials/U.mp4` | 15.2 min | `t = 0` to `t = 914.6` |
| `V` | `/workspace/materials/V.mp4` | 12.8 min | `t = 0` to `t = 766.0` |

For **each** of the twenty-two videos, reconstruct the **complete chronological transcript
of the recipe steps that person actually performed in that recording**, and when
each one started and ended.

Nobody here follows the recipe cleanly. Steps are performed out of order, some are
performed incorrectly, and some are skipped entirely. Report each recording as it
happened, not as the recipe says it should go. A step the person never performed is
not an entry, however clearly the recipe calls for it. A step performed twice is two
entries. A step performed out of the usual order belongs where it actually happened.

sample the videos.

## What to submit

Print the JSON object and nothing else as your final message.

```json
{
  "sequence": [
    {"video": "A", "id": 59, "t_start": 1.827, "t_end": 21.012},
    {"video": "A", "id": 1, "t_start": 58.468, "t_end": 89.529},
    {"video": "V", "id": 24, "t_start": 87.996, "t_end": 124.489}
  ]
}
```

One entry per step performed. Within each video, order the entries by the moment
the step begins; the videos themselves may come in any order. Fields:

- `video`: one of `"A"` through `"V"`, the clip this entry belongs to.
- `id`: the step's label, an integer from the closed vocabulary below.
- `t_start`: the second at which that step begins, in that clip.
- `t_end`: the second at which that same step ends, in that clip.

An entry counts only if it names the right video and **both** of its boundaries
land inside the tolerance of the true step. That tolerance is a quarter of the
step's duration, never tighter than 1 second and never looser than 3 seconds, and
the same tolerance applies to the start and to the end. Short steps are therefore
graded strictly at both ends, so watch each action begin and watch it stop.

## The closed vocabulary

One vocabulary covers all twenty-two videos, and it spans 6 different dishes, so most of
it belongs to dishes you will not see in any given clip. Use only these labels.
Several labels name similar actions on different ingredients, so pick the one that
names what the person actually handles.

- `1` Add-1 tablespoon of olive oil to the mug
- `2` Add-1 teaspoon of pepper powder to the bowl
- `3` Add-Add 1 tbsp salsa to the bowl
- `4` Add-Add 1 teaspoon of softened butter
- `5` Add-Add 1 teaspoon salt to the bowl
- `6` Add-Add 1/2 tbsp sweet and sour sauce to the bowl
- `7` Add-Add basil to the bowl
- `8` Add-Add chopped cilantro to the bowl
- `9` Add-Add in 3 tablespoons of milk to the mug
- `10` Add-Add the corn into a microwave-safe bowl
- `11` Add-Add the noodles to the bowl
- `12` Boil-Boil the water. (While the water is boiling, assemble the filter cone)
- `13` Chop-Chop 1 garlic clove on a cutting board
- `14` Clean-Clean the knife by wiping it with a paper towel
- `15` Clean-Clean the knife by wiping with a paper towel
- `16` Cover-Cover with a lid (or paper towel) to prevent splattering
- `17` Cross-Cross the floss's two ends over the tortilla roll's top
- `18` Discard-Discard ends of the tortilla
- `19` Discard-Discard the paper filter and coffee grounds
- `20` Extract-Extract lime juice from 1/3 lime
- `21` Grind-Grind the coffee beans until the coffee grounds are the consistency of coarse sand, about 20 seconds
- `22` Let-Let the noodles sit for about 1 minute after the microwave stops
- `23` Measure-Measure 12 ounces of cold water
- `24` Measure-Measure 2 cups of frozen corn
- `25` Microwave-Microwave for 1 minute 20 seconds, or until it rises and the toppings are bubbling
- `26` Microwave-Microwave for 3 minutes, stirring in between
- `27` Microwave-Microwave the corn for 2 minutes
- `28` Microwave-Microwave the corn for 3 more minutes
- `29` Microwave-Microwave the ramen for 4 minutes
- `30` Mix-Mix in the flavour packet to the bowl
- `31` Mix-Mix the contents of the bowl well
- `32` Mix-Mix the contents of the mug thoroughly. (There might be some lumps, but that is ok.)
- `33` Peel-Peel 1 garlic clove
- `34` Peel-Peel 1 medium onion
- `35` Place-Place 8 inch tortilla on a cutting board
- `36` Place-Place 8-inch flour tortilla on cutting board
- `37` Place-Place the dripper on top of a coffee mug
- `38` Place-Place the floss halfway between toothpicks
- `39` Place-Place the paper filter in the dripper
- `40` Place-Place the pinwheels on a plate
- `41` Pour-Pour a small amount of water into the filter to wet the grounds
- `42` Pour-Pour egg mixture on top of the tortilla
- `43` Prepare-Prepare the filter insert by folding the paper filter in half to create a semi-circle, and in half again to create a quarter-circle
- `44` Put-Put all the Vegetables in a microwave-safe bowl
- `45` Remove-Remove the noodles from the package(Break Noodles / Keep them as a block)
- `46` Roll-Roll the tortilla from one end to another into a log shape, about 1.5 inches thick. Roll it tight enough to prevent gaps but not so tight that the filling leaks
- `47` Roll-Roll the tortilla from one end to the other into a log shape, about 1.5 inches thick. Roll it tight enough to prevent gaps, but not so tight that the filling leaks
- `48` Secure-Secure the rolled tortilla by inserting 5 toothpicks about 1 inch apart
- `49` Slide-Slide floss under the tortilla, perpendicular to the length of the roll
- `50` Spread-Spread jelly over the nut butter
- `51` Spread-Spread nut butter onto the tortilla, leaving 1/2-inch uncovered at the edges
- `52` Sprinkle-Sprinkle 1 generous tablespoon of mozzarella cheese on top of the sauce
- `53` Sprinkle-Sprinkle 1 tbsp shredded cheddar cheese on top of the egg
- `54` Sprinkle-Sprinkle dried Italian herbs inside the mug
- `55` Sprinkle-Sprinkle oregano in the bowl
- `56` Stir-Stir noodles with a spoon or fork until the flavouring dissolves
- `57` Stir-Stir the contents in the mug well
- `58` Take-Take 1 tablespoon of marinara sauce
- `59` Take-Take a microwavable mug
- `60` Thaw-Thaw the frozen corn by putting it in a sieve and running it under cold water
- `61` Transfer-Transfer the grounds to the filter cone
- `62` Trim-Trim the ends of the tortilla roll with the butter knife, leaving 1/2 inch margin between the last toothpick and the end of the roll
- `63` Wait-Wait about 30 seconds for the coffee to bloom. (You will see small bubbles or foam on the coffee grounds during this step.)
- `64` Weigh-Weigh the coffee beans (0.8oz-0.12 oz)
- `65` Whisk-Whisk the egg
- `66` add-Extract and add contents of an egg to a microwave-safe bowl
- `67` add-Measure 1/16 teaspoon of baking soda and add it to the mug
- `68` add-Measure 1/8 teaspoon of baking powder and add it to the mug
- `69` add-Measure 1/8 teaspoon of salt and add it to the mug
- `70` add-Measure 4 tablespoons of flour and add it to the mug
- `71` add-add lime juice to the bowl
- `72` check-Once the water has boiled, check the temperature of the water. (The water should be between 195-205 degrees Fahrenheit or between 91-96 degrees Celsius. If the water is too hot, let it cool briefly.)
- `73` cover-cover the noodles with water
- `74` drain-Let the coffee drain completely into the mug before removing the dripper
- `75` pour-Slowly pour the rest of the water over the grounds in a circular motion. Do not overfill beyond the top of the paper filter
- `76` pull-pull the floss ends in opposite directions to slice
- `77` scoop-Use a butter knife to scoop nut butter from the jar
- `78` scoop-Use the knife to scoop jelly from the jar
- `79` slice-slice 1/4 medium onion into pieces
- `80` slicing-Continue slicing with floss to create 1 more pinwheel
- `81` spread-spread marinara sauce around the surface of the batter
- `82` spread-spread open filter in dripper to create a cone
- `83` stir-then stir the bowl
- `84` transfer-transfer water to a kettle

## Rules

Print the JSON object and nothing else as your final message.
  samples you take, not only at the end. Your run can end at any moment and only
  what is on disk counts, so an incomplete answer saved early beats a complete one
  you never got to write.
- Stay inside this working directory. Do not read, write, or search outside it.
- Do not look anything up online, and do not rely on any memory of these recordings
  or of the dataset they may come from. Every answer must come from watching these
  videos.
- Use only labels from the vocabulary above.
- Report every step you find, in every video, including a step performed more than
  once.
