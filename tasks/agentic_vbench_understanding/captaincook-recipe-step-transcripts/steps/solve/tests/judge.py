#!/usr/bin/env python3
"""Grade 22 egocentric recipe-step transcripts. Pure Python stdlib, deterministic.

The agent watches 22 continuous head-mounted GoPro recordings, 293 minutes of
video in total, and must return the transcript of each one: every recipe step as it
was actually performed in that recording, in order, with the span of each step.
314 steps across the 22, drawn from 6 different recipes.

A predicted step is a true positive only when it names the right video, its label
matches, and BOTH of its boundaries fall inside that step's own tolerance, under an
order-preserving one-to-one alignment within that video. Misses and false positives
both hurt, and the reward is the F1 over the totals.

Requiring the whole span is what makes this a transcript rather than a list of
timestamps.

The tolerance travels with the ground-truth step: a quarter of that step's annotated
duration, floored at 1.0 s and capped at 3.0 s, and the same tolerance applies to
both boundaries. Short steps are graded strictly and long ones leniently, and no step
is graded outside [1, 3] seconds. The prompt states the same rule to the agent.

Why the metric is safe against guessing. The canonical order of a recipe is common
knowledge, and these 22 recordings cover only 6 recipes, so an agent that recognised
the dish could try to recite it. It does not work, because these are not clean
executions: 199 of the 314 steps are annotated by the dataset as performed with an
error, and the recordings depart from the order induced by the other recordings of the
same recipe 77 times. Every step also needs a span, not just a name. Reciting the
canonical order of each recipe, derived from the other recordings of that recipe,
scores TBD on the real key; 400 random submissions average TBD
and the best of them reaches TBD. Only watching what these particular people
did, in which order, and where, converts into score. All of it is reproduced by
../../../provenance/ablations/run_ablations.py.

Ground truth is a deterministic transform of the released CaptainCook4D step
annotations, produced by ../../../provenance/build_gt.py. The agent never sees this
file.
"""
import argparse
import json
from pathlib import Path

# Bound the alignment cost against a spam submission. Anything past this many
# entries is ignored; a submission that long is already far below the bar.
MAX_ENTRIES = 20000


VOCABULARY = {
    1: "Add-1 tablespoon of olive oil to the mug",
    2: "Add-1 teaspoon of pepper powder to the bowl",
    3: "Add-Add 1 tbsp salsa to the bowl",
    4: "Add-Add 1 teaspoon of softened butter",
    5: "Add-Add 1 teaspoon salt to the bowl",
    6: "Add-Add 1/2 tbsp sweet and sour sauce to the bowl",
    7: "Add-Add basil to the bowl",
    8: "Add-Add chopped cilantro to the bowl",
    9: "Add-Add in 3 tablespoons of milk to the mug",
    10: "Add-Add the corn into a microwave-safe bowl",
    11: "Add-Add the noodles to the bowl",
    12: "Boil-Boil the water. (While the water is boiling, assemble the filter cone)",
    13: "Chop-Chop 1 garlic clove on a cutting board",
    14: "Clean-Clean the knife by wiping it with a paper towel",
    15: "Clean-Clean the knife by wiping with a paper towel",
    16: "Cover-Cover with a lid (or paper towel) to prevent splattering",
    17: "Cross-Cross the floss's two ends over the tortilla roll's top",
    18: "Discard-Discard ends of the tortilla",
    19: "Discard-Discard the paper filter and coffee grounds",
    20: "Extract-Extract lime juice from 1/3 lime",
    21: "Grind-Grind the coffee beans until the coffee grounds are the consistency of coarse sand, about 20 seconds",
    22: "Let-Let the noodles sit for about 1 minute after the microwave stops",
    23: "Measure-Measure 12 ounces of cold water",
    24: "Measure-Measure 2 cups of frozen corn",
    25: "Microwave-Microwave for 1 minute 20 seconds, or until it rises and the toppings are bubbling",
    26: "Microwave-Microwave for 3 minutes, stirring in between",
    27: "Microwave-Microwave the corn for 2 minutes",
    28: "Microwave-Microwave the corn for 3 more minutes",
    29: "Microwave-Microwave the ramen for 4 minutes",
    30: "Mix-Mix in the flavour packet to the bowl",
    31: "Mix-Mix the contents of the bowl well",
    32: "Mix-Mix the contents of the mug thoroughly. (There might be some lumps, but that is ok.)",
    33: "Peel-Peel 1 garlic clove",
    34: "Peel-Peel 1 medium onion",
    35: "Place-Place 8 inch tortilla on a cutting board",
    36: "Place-Place 8-inch flour tortilla on cutting board",
    37: "Place-Place the dripper on top of a coffee mug",
    38: "Place-Place the floss halfway between toothpicks",
    39: "Place-Place the paper filter in the dripper",
    40: "Place-Place the pinwheels on a plate",
    41: "Pour-Pour a small amount of water into the filter to wet the grounds",
    42: "Pour-Pour egg mixture on top of the tortilla",
    43: "Prepare-Prepare the filter insert by folding the paper filter in half to create a semi-circle, and in half again to create a quarter-circle",
    44: "Put-Put all the Vegetables in a microwave-safe bowl",
    45: "Remove-Remove the noodles from the package(Break Noodles / Keep them as a block)",
    46: "Roll-Roll the tortilla from one end to another into a log shape, about 1.5 inches thick. Roll it tight enough to prevent gaps but not so tight that the filling leaks",
    47: "Roll-Roll the tortilla from one end to the other into a log shape, about 1.5 inches thick. Roll it tight enough to prevent gaps, but not so tight that the filling leaks",
    48: "Secure-Secure the rolled tortilla by inserting 5 toothpicks about 1 inch apart",
    49: "Slide-Slide floss under the tortilla, perpendicular to the length of the roll",
    50: "Spread-Spread jelly over the nut butter",
    51: "Spread-Spread nut butter onto the tortilla, leaving 1/2-inch uncovered at the edges",
    52: "Sprinkle-Sprinkle 1 generous tablespoon of mozzarella cheese on top of the sauce",
    53: "Sprinkle-Sprinkle 1 tbsp shredded cheddar cheese on top of the egg",
    54: "Sprinkle-Sprinkle dried Italian herbs inside the mug",
    55: "Sprinkle-Sprinkle oregano in the bowl",
    56: "Stir-Stir noodles with a spoon or fork until the flavouring dissolves",
    57: "Stir-Stir the contents in the mug well",
    58: "Take-Take 1 tablespoon of marinara sauce",
    59: "Take-Take a microwavable mug",
    60: "Thaw-Thaw the frozen corn by putting it in a sieve and running it under cold water",
    61: "Transfer-Transfer the grounds to the filter cone",
    62: "Trim-Trim the ends of the tortilla roll with the butter knife, leaving 1/2 inch margin between the last toothpick and the end of the roll",
    63: "Wait-Wait about 30 seconds for the coffee to bloom. (You will see small bubbles or foam on the coffee grounds during this step.)",
    64: "Weigh-Weigh the coffee beans (0.8oz-0.12 oz)",
    65: "Whisk-Whisk the egg",
    66: "add-Extract and add contents of an egg to a microwave-safe bowl",
    67: "add-Measure 1/16 teaspoon of baking soda and add it to the mug",
    68: "add-Measure 1/8 teaspoon of baking powder and add it to the mug",
    69: "add-Measure 1/8 teaspoon of salt and add it to the mug",
    70: "add-Measure 4 tablespoons of flour and add it to the mug",
    71: "add-add lime juice to the bowl",
    72: "check-Once the water has boiled, check the temperature of the water. (The water should be between 195-205 degrees Fahrenheit or between 91-96 degrees Celsius. If the water is too hot, let it cool briefly.)",
    73: "cover-cover the noodles with water",
    74: "drain-Let the coffee drain completely into the mug before removing the dripper",
    75: "pour-Slowly pour the rest of the water over the grounds in a circular motion. Do not overfill beyond the top of the paper filter",
    76: "pull-pull the floss ends in opposite directions to slice",
    77: "scoop-Use a butter knife to scoop nut butter from the jar",
    78: "scoop-Use the knife to scoop jelly from the jar",
    79: "slice-slice 1/4 medium onion into pieces",
    80: "slicing-Continue slicing with floss to create 1 more pinwheel",
    81: "spread-spread marinara sauce around the surface of the batter",
    82: "spread-spread open filter in dripper to create a cone",
    83: "stir-then stir the bowl",
    84: "transfer-transfer water to a kettle",
}

# The release's own error taxonomy, carried through from the annotations
# rather than written here, so the judge and the prompt cannot drift apart.
ERROR_TAGS = (
    "Measurement Error",
    "Missing Step",
    "Order Error",
    "Other",
    "Preparation Error",
    "Technique Error",
    "Temperature Error",
    "Timing Error",
)

# letter -> chronological ground truth, each with the tolerance for both bounds
GROUND_TRUTH = {
    "A": [
        {"id": 59, "t_start": 1.827, "t_end": 21.012, "tau": 3.0, "error": ["none"]},
        {"id": 1, "t_start": 58.468, "t_end": 89.529, "tau": 3.0, "error": ["Order Error", "Preparation Error"]},
        {"id": 70, "t_start": 107.8, "t_end": 174.489, "tau": 3.0, "error": ["Measurement Error", "Order Error"]},
        {"id": 68, "t_start": 180.884, "t_end": 248.488, "tau": 3.0, "error": ["Order Error", "Preparation Error"]},
        {"id": 57, "t_start": 254.883, "t_end": 295.993, "tau": 3.0, "error": ["Order Error", "Technique Error"]},
        {"id": 9, "t_start": 300.56, "t_end": 380.04, "tau": 3.0, "error": ["Measurement Error", "Order Error"]},
        {"id": 69, "t_start": 383.694, "t_end": 433.94, "tau": 3.0, "error": ["Order Error"]},
        {"id": 32, "t_start": 436.68, "t_end": 524.382, "tau": 3.0, "error": ["Order Error"]},
        {"id": 67, "t_start": 528.95, "t_end": 560.924, "tau": 3.0, "error": ["Order Error"]},
        {"id": 58, "t_start": 576.0, "t_end": 607.0, "tau": 3.0, "error": ["Measurement Error"]},
        {"id": 81, "t_start": 608.0, "t_end": 611.0, "tau": 1.0, "error": ["none"]},
        {"id": 58, "t_start": 611.0, "t_end": 613.0, "tau": 1.0, "error": ["Measurement Error"]},
        {"id": 81, "t_start": 612.0, "t_end": 638.577, "tau": 3.0, "error": ["none"]},
        {"id": 52, "t_start": 651.366, "t_end": 687.909, "tau": 3.0, "error": ["none"]},
        {"id": 54, "t_start": 690.649, "t_end": 715.315, "tau": 3.0, "error": ["none"]},
        {"id": 25, "t_start": 716.229, "t_end": 944.618, "tau": 3.0, "error": ["Timing Error"]},
    ],
    "B": [
        {"id": 59, "t_start": 10.053, "t_end": 19.437, "tau": 2.346, "error": ["Preparation Error"]},
        {"id": 67, "t_start": 22.118, "t_end": 74.396, "tau": 3.0, "error": ["Measurement Error"]},
        {"id": 68, "t_start": 77.077, "t_end": 136.057, "tau": 3.0, "error": ["none"]},
        {"id": 70, "t_start": 144.1, "t_end": 174.26, "tau": 3.0, "error": ["Measurement Error", "Technique Error"]},
        {"id": 69, "t_start": 183.644, "t_end": 208.442, "tau": 3.0, "error": ["Measurement Error"]},
        {"id": 57, "t_start": 208.442, "t_end": 229.89, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 1, "t_start": 231.23, "t_end": 254.018, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 9, "t_start": 263.401, "t_end": 302.275, "tau": 3.0, "error": ["none"]},
        {"id": 54, "t_start": 322.382, "t_end": 350.531, "tau": 3.0, "error": ["Order Error"]},
        {"id": 58, "t_start": 401.469, "t_end": 437.661, "tau": 3.0, "error": ["none"]},
        {"id": 81, "t_start": 436.321, "t_end": 448.385, "tau": 3.0, "error": ["Order Error", "Technique Error"]},
        {"id": 52, "t_start": 478.546, "t_end": 508.036, "tau": 3.0, "error": ["none"]},
        {"id": 32, "t_start": 519.43, "t_end": 538.196, "tau": 3.0, "error": ["Order Error"]},
        {"id": 25, "t_start": 536.856, "t_end": 680.285, "tau": 3.0, "error": ["Timing Error"]},
    ],
    "C": [
        {"id": 59, "t_start": 6.022, "t_end": 24.843, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 68, "t_start": 27.101, "t_end": 45.169, "tau": 3.0, "error": ["Measurement Error"]},
        {"id": 70, "t_start": 61.731, "t_end": 117.439, "tau": 3.0, "error": ["Measurement Error"]},
        {"id": 67, "t_start": 118.944, "t_end": 141.529, "tau": 3.0, "error": ["none"]},
        {"id": 69, "t_start": 150.562, "t_end": 162.607, "tau": 3.0, "error": ["Measurement Error"]},
        {"id": 57, "t_start": 173.899, "t_end": 209.282, "tau": 3.0, "error": ["none"]},
        {"id": 1, "t_start": 215.304, "t_end": 246.922, "tau": 3.0, "error": ["none"]},
        {"id": 9, "t_start": 308.653, "t_end": 351.563, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 54, "t_start": 356.08, "t_end": 383.181, "tau": 3.0, "error": ["Order Error"]},
        {"id": 58, "t_start": 424.586, "t_end": 459.215, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 81, "t_start": 457.709, "t_end": 469.754, "tau": 3.0, "error": ["Order Error", "Technique Error"]},
        {"id": 52, "t_start": 508.9, "t_end": 541.271, "tau": 3.0, "error": ["Order Error"]},
        {"id": 32, "t_start": 547.294, "t_end": 593.968, "tau": 3.0, "error": ["Order Error"]},
        {"id": 25, "t_start": 616.552, "t_end": 765.609, "tau": 3.0, "error": ["Timing Error"]},
    ],
    "D": [
        {"id": 33, "t_start": 61.556, "t_end": 112.443, "tau": 3.0, "error": ["Measurement Error", "Technique Error"]},
        {"id": 13, "t_start": 123.112, "t_end": 164.264, "tau": 3.0, "error": ["none"]},
        {"id": 45, "t_start": 182.774, "t_end": 196.979, "tau": 3.0, "error": ["none"]},
        {"id": 34, "t_start": 241.489, "t_end": 258.952, "tau": 3.0, "error": ["none"]},
        {"id": 79, "t_start": 264.218, "t_end": 320.727, "tau": 3.0, "error": ["Measurement Error"]},
        {"id": 44, "t_start": 333.35, "t_end": 354.972, "tau": 3.0, "error": ["none"]},
        {"id": 11, "t_start": 360.813, "t_end": 365.124, "tau": 1.078, "error": ["none"]},
        {"id": 73, "t_start": 384.489, "t_end": 402.693, "tau": 3.0, "error": ["none"]},
        {"id": 29, "t_start": 420.0, "t_end": 444.0, "tau": 3.0, "error": ["Timing Error"]},
        {"id": 16, "t_start": 444.151, "t_end": 451.09, "tau": 1.735, "error": ["none"]},
        {"id": 29, "t_start": 454.568, "t_end": 580.938, "tau": 3.0, "error": ["Timing Error"]},
        {"id": 8, "t_start": 624.084, "t_end": 637.076, "tau": 3.0, "error": ["none"]},
        {"id": 22, "t_start": 641.13, "t_end": 709.58, "tau": 3.0, "error": ["none"]},
        {"id": 30, "t_start": 731.097, "t_end": 738.301, "tau": 1.801, "error": ["none"]},
        {"id": 56, "t_start": 741.514, "t_end": 780.136, "tau": 3.0, "error": ["Technique Error"]},
    ],
    "E": [
        {"id": 34, "t_start": 25.256, "t_end": 140.0, "tau": 3.0, "error": ["none"]},
        {"id": 33, "t_start": 170.479, "t_end": 245.312, "tau": 3.0, "error": ["Measurement Error"]},
        {"id": 13, "t_start": 272.504, "t_end": 311.394, "tau": 3.0, "error": ["none"]},
        {"id": 79, "t_start": 344.747, "t_end": 417.054, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 45, "t_start": 467.239, "t_end": 485.546, "tau": 3.0, "error": ["none"]},
        {"id": 44, "t_start": 506.387, "t_end": 525.117, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 11, "t_start": 568.264, "t_end": 580.629, "tau": 3.0, "error": ["none"]},
        {"id": 73, "t_start": 584.681, "t_end": 594.834, "tau": 2.538, "error": ["none"]},
        {"id": 16, "t_start": 608.674, "t_end": 614.039, "tau": 1.341, "error": ["Technique Error"]},
        {"id": 29, "t_start": 641.507, "t_end": 801.788, "tau": 3.0, "error": ["Timing Error"]},
        {"id": 7, "t_start": 803.147, "t_end": 814.512, "tau": 2.841, "error": ["none"]},
        {"id": 22, "t_start": 853.659, "t_end": 887.755, "tau": 3.0, "error": ["Timing Error"]},
        {"id": 8, "t_start": 940.543, "t_end": 946.062, "tau": 1.38, "error": ["none"]},
        {"id": 30, "t_start": 986.254, "t_end": 1003.196, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 56, "t_start": 1011.0, "t_end": 1044.0, "tau": 3.0, "error": ["none"]},
    ],
    "F": [
        {"id": 33, "t_start": 53.618, "t_end": 152.137, "tau": 3.0, "error": ["Measurement Error"]},
        {"id": 34, "t_start": 175.834, "t_end": 190.027, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 13, "t_start": 202.643, "t_end": 259.047, "tau": 3.0, "error": ["none"]},
        {"id": 45, "t_start": 273.608, "t_end": 289.685, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 79, "t_start": 313.416, "t_end": 335.629, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 8, "t_start": 413.171, "t_end": 420.421, "tau": 1.812, "error": ["Order Error"]},
        {"id": 11, "t_start": 421.421, "t_end": 427.172, "tau": 1.438, "error": ["Order Error"]},
        {"id": 44, "t_start": 433.672, "t_end": 443.922, "tau": 2.562, "error": ["Order Error"]},
        {"id": 16, "t_start": 456.538, "t_end": 466.385, "tau": 2.462, "error": ["Order Error"]},
        {"id": 29, "t_start": 472.308, "t_end": 543.289, "tau": 3.0, "error": ["Order Error", "Timing Error"]},
        {"id": 22, "t_start": 565.888, "t_end": 595.062, "tau": 3.0, "error": ["Order Error", "Timing Error"]},
        {"id": 7, "t_start": 600.044, "t_end": 615.294, "tau": 3.0, "error": ["Order Error"]},
        {"id": 73, "t_start": 622.91, "t_end": 633.161, "tau": 2.563, "error": ["Order Error", "Preparation Error"]},
        {"id": 56, "t_start": 638.68, "t_end": 649.142, "tau": 2.616, "error": ["none"]},
    ],
    "G": [
        {"id": 33, "t_start": 21.541, "t_end": 30.227, "tau": 2.171, "error": ["none"]},
        {"id": 45, "t_start": 44.061, "t_end": 65.038, "tau": 3.0, "error": ["none"]},
        {"id": 34, "t_start": 74.414, "t_end": 116.537, "tau": 3.0, "error": ["none"]},
        {"id": 13, "t_start": 122.392, "t_end": 136.057, "tau": 3.0, "error": ["none"]},
        {"id": 44, "t_start": 143.932, "t_end": 150.744, "tau": 1.703, "error": ["Order Error"]},
        {"id": 79, "t_start": 173.577, "t_end": 187.118, "tau": 3.0, "error": ["none"]},
        {"id": 7, "t_start": 202.68, "t_end": 214.43, "tau": 2.938, "error": ["Order Error"]},
        {"id": 73, "t_start": 277.094, "t_end": 331.781, "tau": 3.0, "error": ["Order Error", "Preparation Error"]},
        {"id": 16, "t_start": 335.842, "t_end": 342.049, "tau": 1.552, "error": ["Missing Step", "Order Error"]},
        {"id": 29, "t_start": 360.0, "t_end": 372.0, "tau": 3.0, "error": ["Order Error", "Preparation Error"]},
        {"id": 11, "t_start": 390.096, "t_end": 393.887, "tau": 1.0, "error": ["Order Error"]},
        {"id": 29, "t_start": 403.402, "t_end": 651.687, "tau": 3.0, "error": ["Order Error"]},
        {"id": 22, "t_start": 670.706, "t_end": 733.37, "tau": 3.0, "error": ["none"]},
        {"id": 8, "t_start": 681.476, "t_end": 690.246, "tau": 2.192, "error": ["none"]},
        {"id": 30, "t_start": 757.848, "t_end": 772.535, "tau": 3.0, "error": ["none"]},
        {"id": 56, "t_start": 776.452, "t_end": 807.992, "tau": 3.0, "error": ["Technique Error"]},
    ],
    "H": [
        {"id": 34, "t_start": 20.599, "t_end": 30.0, "tau": 2.35, "error": ["Technique Error"]},
        {"id": 33, "t_start": 30.01, "t_end": 34.255, "tau": 1.061, "error": ["none"]},
        {"id": 79, "t_start": 55.912, "t_end": 71.096, "tau": 3.0, "error": ["none"]},
        {"id": 45, "t_start": 94.167, "t_end": 101.501, "tau": 1.834, "error": ["none"]},
        {"id": 11, "t_start": 108.145, "t_end": 131.708, "tau": 3.0, "error": ["Order Error"]},
        {"id": 33, "t_start": 140.0, "t_end": 158.0, "tau": 3.0, "error": ["none"]},
        {"id": 13, "t_start": 157.25, "t_end": 169.435, "tau": 3.0, "error": ["none"]},
        {"id": 44, "t_start": 180.242, "t_end": 195.691, "tau": 3.0, "error": ["Order Error"]},
        {"id": 73, "t_start": 222.911, "t_end": 226.682, "tau": 1.0, "error": ["Technique Error"]},
        {"id": 16, "t_start": 242.775, "t_end": 248.281, "tau": 1.377, "error": ["none"]},
        {"id": 29, "t_start": 252.338, "t_end": 443.201, "tau": 3.0, "error": ["Timing Error"]},
        {"id": 7, "t_start": 456.122, "t_end": 460.157, "tau": 1.009, "error": ["none"]},
        {"id": 22, "t_start": 509.091, "t_end": 541.461, "tau": 3.0, "error": ["Order Error", "Timing Error"]},
        {"id": 8, "t_start": 564.267, "t_end": 573.359, "tau": 2.273, "error": ["Order Error"]},
        {"id": 30, "t_start": 585.601, "t_end": 590.429, "tau": 1.207, "error": ["none"]},
        {"id": 56, "t_start": 597.373, "t_end": 604.2, "tau": 1.707, "error": ["Technique Error"]},
    ],
    "I": [
        {"id": 23, "t_start": 4.264, "t_end": 98.067, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 84, "t_start": 107.596, "t_end": 121.42, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 43, "t_start": 146.197, "t_end": 185.303, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 37, "t_start": 197.16, "t_end": 222.64, "tau": 3.0, "error": ["none"]},
        {"id": 12, "t_start": 239.117, "t_end": 400.193, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 39, "t_start": 413.174, "t_end": 426.843, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 82, "t_start": 440.742, "t_end": 455.037, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 64, "t_start": 476.088, "t_end": 571.919, "tau": 3.0, "error": ["Measurement Error"]},
        {"id": 21, "t_start": 583.323, "t_end": 805.777, "tau": 3.0, "error": ["Preparation Error", "Timing Error"]},
        {"id": 61, "t_start": 823.112, "t_end": 844.376, "tau": 3.0, "error": ["none"]},
        {"id": 41, "t_start": 853.055, "t_end": 874.771, "tau": 3.0, "error": ["Preparation Error", "Technique Error"]},
        {"id": 63, "t_start": 874.99, "t_end": 974.528, "tau": 3.0, "error": ["Timing Error"]},
        {"id": 75, "t_start": 975.065, "t_end": 1017.218, "tau": 3.0, "error": ["Preparation Error", "Technique Error"]},
        {"id": 74, "t_start": 1017.945, "t_end": 1095.205, "tau": 3.0, "error": ["none"]},
        {"id": 19, "t_start": 1112.929, "t_end": 1140.0, "tau": 3.0, "error": ["none"]},
    ],
    "J": [
        {"id": 43, "t_start": 13.126, "t_end": 56.744, "tau": 3.0, "error": ["none"]},
        {"id": 64, "t_start": 64.114, "t_end": 162.239, "tau": 3.0, "error": ["Measurement Error"]},
        {"id": 23, "t_start": 275.0, "t_end": 293.0, "tau": 3.0, "error": ["none"]},
        {"id": 84, "t_start": 293.0, "t_end": 305.0, "tau": 3.0, "error": ["none"]},
        {"id": 39, "t_start": 326.116, "t_end": 346.0, "tau": 3.0, "error": ["Order Error"]},
        {"id": 82, "t_start": 346.0, "t_end": 360.0, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 21, "t_start": 370.035, "t_end": 416.314, "tau": 3.0, "error": ["Timing Error"]},
        {"id": 12, "t_start": 427.341, "t_end": 595.843, "tau": 3.0, "error": ["none"]},
        {"id": 72, "t_start": 595.0, "t_end": 622.845, "tau": 3.0, "error": ["Temperature Error"]},
        {"id": 61, "t_start": 609.795, "t_end": 679.181, "tau": 3.0, "error": ["none"]},
        {"id": 37, "t_start": 663.113, "t_end": 669.452, "tau": 1.585, "error": ["Order Error"]},
        {"id": 41, "t_start": 684.643, "t_end": 700.783, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 63, "t_start": 700.713, "t_end": 730.476, "tau": 3.0, "error": ["none"]},
        {"id": 74, "t_start": 730.522, "t_end": 791.269, "tau": 3.0, "error": ["none"]},
        {"id": 19, "t_start": 797.109, "t_end": 832.471, "tau": 3.0, "error": ["none"]},
    ],
    "K": [
        {"id": 37, "t_start": 9.091, "t_end": 37.101, "tau": 3.0, "error": ["none"]},
        {"id": 23, "t_start": 41.275, "t_end": 82.191, "tau": 3.0, "error": ["Measurement Error"]},
        {"id": 84, "t_start": 92.167, "t_end": 122.574, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 12, "t_start": 122.857, "t_end": 143.807, "tau": 3.0, "error": ["none"]},
        {"id": 64, "t_start": 144.126, "t_end": 267.803, "tau": 3.0, "error": ["Measurement Error"]},
        {"id": 43, "t_start": 277.0, "t_end": 322.0, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 39, "t_start": 323.0, "t_end": 331.266, "tau": 2.067, "error": ["none"]},
        {"id": 21, "t_start": 348.162, "t_end": 383.288, "tau": 3.0, "error": ["Timing Error"]},
        {"id": 82, "t_start": 413.205, "t_end": 431.225, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 61, "t_start": 445.488, "t_end": 486.436, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 41, "t_start": 538.955, "t_end": 568.097, "tau": 3.0, "error": ["none"]},
        {"id": 63, "t_start": 569.031, "t_end": 588.98, "tau": 3.0, "error": ["none"]},
        {"id": 75, "t_start": 589.178, "t_end": 653.366, "tau": 3.0, "error": ["none"]},
        {"id": 74, "t_start": 653.863, "t_end": 724.318, "tau": 3.0, "error": ["none"]},
        {"id": 19, "t_start": 725.9, "t_end": 740.953, "tau": 3.0, "error": ["none"]},
    ],
    "L": [
        {"id": 64, "t_start": 5.402, "t_end": 76.469, "tau": 3.0, "error": ["Measurement Error"]},
        {"id": 43, "t_start": 84.256, "t_end": 128.449, "tau": 3.0, "error": ["none"]},
        {"id": 39, "t_start": 128.606, "t_end": 143.957, "tau": 3.0, "error": ["Order Error", "Technique Error"]},
        {"id": 37, "t_start": 145.395, "t_end": 159.909, "tau": 3.0, "error": ["Order Error"]},
        {"id": 82, "t_start": 162.497, "t_end": 181.406, "tau": 3.0, "error": ["none"]},
        {"id": 21, "t_start": 187.807, "t_end": 264.241, "tau": 3.0, "error": ["Timing Error"]},
        {"id": 61, "t_start": 269.971, "t_end": 327.461, "tau": 3.0, "error": ["none"]},
        {"id": 84, "t_start": 362.329, "t_end": 394.622, "tau": 3.0, "error": ["none"]},
        {"id": 41, "t_start": 396.36, "t_end": 434.713, "tau": 3.0, "error": ["Measurement Error", "Order Error"]},
        {"id": 63, "t_start": 436.623, "t_end": 457.399, "tau": 3.0, "error": ["Order Error", "Timing Error"]},
        {"id": 75, "t_start": 458.202, "t_end": 481.618, "tau": 3.0, "error": ["Order Error"]},
        {"id": 74, "t_start": 482.0, "t_end": 655.0, "tau": 3.0, "error": ["Order Error", "Timing Error"]},
        {"id": 23, "t_start": 482.481, "t_end": 500.639, "tau": 3.0, "error": ["Measurement Error"]},
        {"id": 12, "t_start": 501.08, "t_end": 624.476, "tau": 3.0, "error": ["Order Error"]},
        {"id": 72, "t_start": 558.714, "t_end": 652.789, "tau": 3.0, "error": ["Order Error", "Temperature Error"]},
        {"id": 19, "t_start": 655.001, "t_end": 672.304, "tau": 3.0, "error": ["none"]},
    ],
    "M": [
        {"id": 64, "t_start": 5.233, "t_end": 105.596, "tau": 3.0, "error": ["Measurement Error", "Technique Error"]},
        {"id": 39, "t_start": 110.522, "t_end": 154.644, "tau": 3.0, "error": ["Measurement Error", "Order Error"]},
        {"id": 37, "t_start": 192.352, "t_end": 207.884, "tau": 3.0, "error": ["Order Error", "Preparation Error"]},
        {"id": 82, "t_start": 216.236, "t_end": 326.52, "tau": 3.0, "error": ["Order Error", "Technique Error"]},
        {"id": 21, "t_start": 330.177, "t_end": 371.294, "tau": 3.0, "error": ["Technique Error", "Timing Error"]},
        {"id": 61, "t_start": 388.125, "t_end": 441.624, "tau": 3.0, "error": ["Order Error"]},
        {"id": 23, "t_start": 464.743, "t_end": 576.299, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 84, "t_start": 584.614, "t_end": 661.364, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 41, "t_start": 714.038, "t_end": 728.284, "tau": 3.0, "error": ["Order Error", "Preparation Error"]},
        {"id": 63, "t_start": 730.489, "t_end": 760.102, "tau": 3.0, "error": ["Order Error"]},
        {"id": 75, "t_start": 761.796, "t_end": 780.797, "tau": 3.0, "error": ["Order Error", "Technique Error"]},
        {"id": 74, "t_start": 781.013, "t_end": 856.777, "tau": 3.0, "error": ["Order Error"]},
        {"id": 12, "t_start": 813.251, "t_end": 936.783, "tau": 3.0, "error": ["Order Error", "Preparation Error"]},
        {"id": 72, "t_start": 938.77, "t_end": 969.456, "tau": 3.0, "error": ["Order Error", "Preparation Error", "Temperature Error"]},
        {"id": 43, "t_start": 973.311, "t_end": 982.497, "tau": 2.296, "error": ["Order Error"]},
        {"id": 19, "t_start": 989.209, "t_end": 1010.557, "tau": 3.0, "error": ["none"]},
    ],
    "N": [
        {"id": 35, "t_start": 4.54, "t_end": 20.407, "tau": 3.0, "error": ["none"]},
        {"id": 66, "t_start": 25.319, "t_end": 86.522, "tau": 3.0, "error": ["none"]},
        {"id": 6, "t_start": 92.945, "t_end": 189.662, "tau": 3.0, "error": ["Order Error"]},
        {"id": 26, "t_start": 195.706, "t_end": 334.359, "tau": 3.0, "error": ["Order Error", "Preparation Error", "Timing Error"]},
        {"id": 3, "t_start": 337.381, "t_end": 386.495, "tau": 3.0, "error": ["Order Error"]},
        {"id": 65, "t_start": 387.629, "t_end": 414.075, "tau": 3.0, "error": ["Order Error", "Preparation Error"]},
        {"id": 55, "t_start": 417.097, "t_end": 449.588, "tau": 3.0, "error": ["none"]},
        {"id": 31, "t_start": 449.966, "t_end": 471.5, "tau": 3.0, "error": ["none"]},
        {"id": 42, "t_start": 479.434, "t_end": 498.702, "tau": 3.0, "error": ["none"]},
        {"id": 53, "t_start": 504.369, "t_end": 557.639, "tau": 3.0, "error": ["Measurement Error", "Preparation Error"]},
        {"id": 46, "t_start": 559.15, "t_end": 599.953, "tau": 3.0, "error": ["none"]},
    ],
    "O": [
        {"id": 66, "t_start": 7.33, "t_end": 75.396, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 35, "t_start": 82.289, "t_end": 121.061, "tau": 3.0, "error": ["none"]},
        {"id": 65, "t_start": 125.369, "t_end": 171.464, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 26, "t_start": 177.065, "t_end": 346.368, "tau": 3.0, "error": ["Timing Error"]},
        {"id": 42, "t_start": 347.23, "t_end": 381.694, "tau": 3.0, "error": ["Order Error"]},
        {"id": 53, "t_start": 387.294, "t_end": 451.914, "tau": 3.0, "error": ["Measurement Error", "Order Error"]},
        {"id": 6, "t_start": 467.423, "t_end": 522.565, "tau": 3.0, "error": ["Measurement Error", "Order Error"]},
        {"id": 46, "t_start": 529.888, "t_end": 554.874, "tau": 3.0, "error": ["Order Error", "Technique Error"]},
        {"id": 55, "t_start": 561.767, "t_end": 602.262, "tau": 3.0, "error": ["Order Error", "Technique Error"]},
        {"id": 31, "t_start": 603.985, "t_end": 616.909, "tau": 3.0, "error": ["Order Error", "Technique Error"]},
        {"id": 3, "t_start": 626.387, "t_end": 679.806, "tau": 3.0, "error": ["Measurement Error", "Order Error"]},
    ],
    "P": [
        {"id": 66, "t_start": 7.575, "t_end": 68.105, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 65, "t_start": 72.761, "t_end": 116.412, "tau": 3.0, "error": ["none"]},
        {"id": 6, "t_start": 119.322, "t_end": 167.629, "tau": 3.0, "error": ["Measurement Error", "Order Error"]},
        {"id": 3, "t_start": 174.031, "t_end": 222.339, "tau": 3.0, "error": ["Order Error"]},
        {"id": 26, "t_start": 419.059, "t_end": 537.208, "tau": 3.0, "error": ["Order Error", "Timing Error"]},
        {"id": 55, "t_start": 651.865, "t_end": 732.183, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 35, "t_start": 737.0, "t_end": 749.0, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 42, "t_start": 750.225, "t_end": 775.252, "tau": 3.0, "error": ["none"]},
        {"id": 53, "t_start": 779.908, "t_end": 821.231, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 46, "t_start": 824.723, "t_end": 875.358, "tau": 3.0, "error": ["Technique Error"]},
    ],
    "Q": [
        {"id": 36, "t_start": 0.0, "t_end": 187.814, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 77, "t_start": 193.131, "t_end": 222.518, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 51, "t_start": 222.931, "t_end": 298.152, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 14, "t_start": 299.247, "t_end": 308.009, "tau": 2.191, "error": ["none"]},
        {"id": 78, "t_start": 312.954, "t_end": 383.913, "tau": 3.0, "error": ["none"]},
        {"id": 50, "t_start": 355.0, "t_end": 383.0, "tau": 3.0, "error": ["none"]},
        {"id": 15, "t_start": 388.136, "t_end": 413.246, "tau": 3.0, "error": ["none"]},
        {"id": 47, "t_start": 426.444, "t_end": 433.271, "tau": 1.707, "error": ["Measurement Error", "Technique Error"]},
        {"id": 62, "t_start": 527.167, "t_end": 545.832, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 49, "t_start": 551.922, "t_end": 565.478, "tau": 3.0, "error": ["none"]},
        {"id": 38, "t_start": 566.027, "t_end": 589.475, "tau": 3.0, "error": ["none"]},
        {"id": 17, "t_start": 590.0, "t_end": 593.0, "tau": 1.0, "error": ["none"]},
        {"id": 76, "t_start": 593.0, "t_end": 598.017, "tau": 1.254, "error": ["Technique Error"]},
        {"id": 80, "t_start": 604.0, "t_end": 606.0, "tau": 1.0, "error": ["Preparation Error"]},
        {"id": 80, "t_start": 612.5, "t_end": 616.0, "tau": 1.0, "error": ["Preparation Error"]},
        {"id": 80, "t_start": 616.0, "t_end": 618.0, "tau": 1.0, "error": ["Preparation Error"]},
        {"id": 80, "t_start": 618.0, "t_end": 620.0, "tau": 1.0, "error": ["Preparation Error"]},
        {"id": 40, "t_start": 650.952, "t_end": 676.239, "tau": 3.0, "error": ["none"]},
        {"id": 18, "t_start": 683.0, "t_end": 685.0, "tau": 1.0, "error": ["none"]},
    ],
    "R": [
        {"id": 77, "t_start": 2.139, "t_end": 65.181, "tau": 3.0, "error": ["Order Error"]},
        {"id": 36, "t_start": 66.26, "t_end": 94.276, "tau": 3.0, "error": ["Order Error", "Preparation Error"]},
        {"id": 51, "t_start": 95.376, "t_end": 134.29, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 78, "t_start": 141.987, "t_end": 182.569, "tau": 3.0, "error": ["Order Error", "Preparation Error", "Technique Error"]},
        {"id": 50, "t_start": 191.098, "t_end": 222.246, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 15, "t_start": 228.212, "t_end": 258.273, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 47, "t_start": 266.565, "t_end": 312.247, "tau": 3.0, "error": ["none"]},
        {"id": 62, "t_start": 323.276, "t_end": 346.218, "tau": 3.0, "error": ["Order Error", "Technique Error"]},
        {"id": 48, "t_start": 376.245, "t_end": 462.598, "tau": 3.0, "error": ["Measurement Error"]},
        {"id": 49, "t_start": 530.0, "t_end": 531.5, "tau": 1.0, "error": ["none"]},
        {"id": 38, "t_start": 531.5, "t_end": 534.0, "tau": 1.0, "error": ["none"]},
        {"id": 17, "t_start": 545.239, "t_end": 561.263, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 76, "t_start": 562.147, "t_end": 568.508, "tau": 1.59, "error": ["Order Error"]},
        {"id": 80, "t_start": 568.0, "t_end": 594.0, "tau": 3.0, "error": ["none"]},
        {"id": 80, "t_start": 605.413, "t_end": 619.861, "tau": 3.0, "error": ["none"]},
        {"id": 80, "t_start": 620.0, "t_end": 627.0, "tau": 1.75, "error": ["none"]},
        {"id": 40, "t_start": 632.908, "t_end": 665.666, "tau": 3.0, "error": ["none"]},
        {"id": 18, "t_start": 667.343, "t_end": 687.251, "tau": 3.0, "error": ["none"]},
    ],
    "S": [
        {"id": 36, "t_start": 2.459, "t_end": 57.486, "tau": 3.0, "error": ["Preparation Error"]},
        {"id": 78, "t_start": 66.459, "t_end": 165.486, "tau": 3.0, "error": ["Order Error", "Technique Error"]},
        {"id": 50, "t_start": 174.196, "t_end": 197.478, "tau": 3.0, "error": ["Order Error", "Technique Error"]},
        {"id": 77, "t_start": 214.323, "t_end": 231.014, "tau": 3.0, "error": ["Order Error", "Preparation Error"]},
        {"id": 51, "t_start": 232.906, "t_end": 252.287, "tau": 3.0, "error": ["Measurement Error", "Order Error"]},
        {"id": 14, "t_start": 260.687, "t_end": 283.578, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 47, "t_start": 294.615, "t_end": 306.47, "tau": 2.964, "error": ["Measurement Error"]},
        {"id": 48, "t_start": 322.206, "t_end": 345.161, "tau": 3.0, "error": ["Measurement Error"]},
        {"id": 15, "t_start": 360.27, "t_end": 375.797, "tau": 3.0, "error": ["none"]},
        {"id": 49, "t_start": 382.352, "t_end": 412.152, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 38, "t_start": 413.034, "t_end": 423.397, "tau": 2.591, "error": ["Order Error"]},
        {"id": 17, "t_start": 453.379, "t_end": 466.053, "tau": 3.0, "error": ["Order Error"]},
        {"id": 76, "t_start": 467.216, "t_end": 573.87, "tau": 3.0, "error": ["Order Error"]},
        {"id": 62, "t_start": 579.508, "t_end": 611.889, "tau": 3.0, "error": ["Order Error", "Preparation Error"]},
        {"id": 18, "t_start": 613.653, "t_end": 619.971, "tau": 1.579, "error": ["none"]},
        {"id": 40, "t_start": 625.835, "t_end": 635.489, "tau": 2.413, "error": ["none"]},
    ],
    "T": [
        {"id": 24, "t_start": 29.609, "t_end": 39.374, "tau": 2.441, "error": ["Measurement Error"]},
        {"id": 10, "t_start": 87.839, "t_end": 94.604, "tau": 1.691, "error": ["Technique Error"]},
        {"id": 2, "t_start": 132.253, "t_end": 139.135, "tau": 1.721, "error": ["Order Error"]},
        {"id": 27, "t_start": 220.9, "t_end": 411.344, "tau": 3.0, "error": ["Order Error", "Temperature Error", "Timing Error"]},
        {"id": 4, "t_start": 476.701, "t_end": 481.584, "tau": 1.221, "error": ["Preparation Error"]},
        {"id": 28, "t_start": 493.48, "t_end": 681.028, "tau": 3.0, "error": ["none"]},
        {"id": 5, "t_start": 694.741, "t_end": 707.61, "tau": 3.0, "error": ["none"]},
        {"id": 20, "t_start": 739.233, "t_end": 758.089, "tau": 3.0, "error": ["none"]},
        {"id": 31, "t_start": 790.554, "t_end": 809.371, "tau": 3.0, "error": ["none"]},
    ],
    "U": [
        {"id": 24, "t_start": 94.005, "t_end": 136.031, "tau": 3.0, "error": ["none"]},
        {"id": 60, "t_start": 106.984, "t_end": 222.811, "tau": 3.0, "error": ["none"]},
        {"id": 10, "t_start": 252.155, "t_end": 264.862, "tau": 3.0, "error": ["none"]},
        {"id": 27, "t_start": 276.485, "t_end": 406.304, "tau": 3.0, "error": ["none"]},
        {"id": 2, "t_start": 436.058, "t_end": 444.012, "tau": 1.989, "error": ["Technique Error"]},
        {"id": 20, "t_start": 455.647, "t_end": 495.554, "tau": 3.0, "error": ["Order Error", "Other"]},
        {"id": 71, "t_start": 455.647, "t_end": 495.652, "tau": 3.0, "error": ["Order Error", "Other"]},
        {"id": 4, "t_start": 571.772, "t_end": 605.937, "tau": 3.0, "error": ["Order Error"]},
        {"id": 83, "t_start": 613.798, "t_end": 648.068, "tau": 3.0, "error": ["Order Error"]},
        {"id": 28, "t_start": 654.717, "t_end": 841.303, "tau": 3.0, "error": ["Order Error"]},
        {"id": 5, "t_start": 852.681, "t_end": 878.164, "tau": 3.0, "error": ["none"]},
        {"id": 31, "t_start": 882.541, "t_end": 901.66, "tau": 3.0, "error": ["Technique Error"]},
    ],
    "V": [
        {"id": 24, "t_start": 87.996, "t_end": 124.489, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 60, "t_start": 126.9, "t_end": 212.624, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 10, "t_start": 232.496, "t_end": 245.758, "tau": 3.0, "error": ["Order Error"]},
        {"id": 27, "t_start": 256.579, "t_end": 389.773, "tau": 3.0, "error": ["none"]},
        {"id": 2, "t_start": 412.194, "t_end": 421.161, "tau": 2.242, "error": ["none"]},
        {"id": 4, "t_start": 478.475, "t_end": 492.59, "tau": 3.0, "error": ["none"]},
        {"id": 83, "t_start": 512.232, "t_end": 533.536, "tau": 3.0, "error": ["Technique Error"]},
        {"id": 5, "t_start": 553.914, "t_end": 561.103, "tau": 1.797, "error": ["Technique Error"]},
        {"id": 71, "t_start": 578.218, "t_end": 601.785, "tau": 3.0, "error": ["Order Error", "Preparation Error"]},
        {"id": 20, "t_start": 578.366, "t_end": 601.555, "tau": 3.0, "error": ["Order Error", "Preparation Error"]},
        {"id": 28, "t_start": 617.827, "t_end": 746.042, "tau": 3.0, "error": ["Order Error", "Timing Error"]},
    ],
}


def _norm(entry):
    """Normalize one predicted entry to {"video", "id", "t_start", "t_end"} or None."""
    if not isinstance(entry, dict):
        return None
    video = entry.get("video", entry.get("clip", entry.get("take")))
    label = entry.get("id", entry.get("label", entry.get("step_id")))
    onset = entry.get("t_start", entry.get("t", entry.get("start", entry.get("onset"))))
    offset = entry.get("t_end", entry.get("end", entry.get("offset")))
    err = entry.get("error", entry.get("error_tag", entry.get("err")))
    try:
        video = str(video).strip().upper()
        label = int(label)
        onset = float(onset)
        offset = float(offset)
    except (TypeError, ValueError):
        return None
    if video not in GROUND_TRUTH:
        return None
    return {"video": video, "id": label, "t_start": onset, "t_end": offset,
            "error": _norm_error(err)}


# The release's own taxonomy, keyed by a squashed form so that case and inner spacing do
# not decide a match. An unrecognised or absent value normalizes to None, which no ground
# truth entry carries, so the entry still counts as a prediction and still costs
# precision. Dropping it instead would let a submission that omits the field be graded as
# though it had made fewer claims.
_ERROR_CANON = {"".join(t.lower().split()): t for t in ERROR_TAGS}
_ERROR_CANON["none"] = "none"
_ERROR_CANON[""] = "none"


def _norm_error(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        value = value[0] if len(value) == 1 else None
        if value is None:
            return None
    if not isinstance(value, str):
        return None
    return _ERROR_CANON.get("".join(value.lower().split()))


def _max_monotonic(preds, gt, matcher):
    """Largest order-preserving one-to-one matching within one video (LCS-style
    DP). Predictions are consumed in the order given, so ordering errors are
    penalized; the ground truth is chronological."""
    n, m = len(preds), len(gt)
    if n == 0 or m == 0:
        return 0
    prev = [0] * (m + 1)
    for i in range(1, n + 1):
        cur = [0] * (m + 1)
        p = preds[i - 1]
        for j in range(1, m + 1):
            best = cur[j - 1] if cur[j - 1] > prev[j] else prev[j]
            if matcher(p, gt[j - 1]):
                cand = prev[j - 1] + 1
                if cand > best:
                    best = cand
            cur[j] = best
        prev = cur
    return prev[m]


def _error_ok(p, g):
    """The reported error must be one the release annotates for this step.

    Any one of them, not all of them: 59 of the key's instances carry more than one tag,
    and requiring the full set would ask the agent to reproduce an annotator's list rather
    than to notice what went wrong. Naming one the annotator also named is the claim being
    scored. A step with no annotated error requires "none".
    """
    return p["error"] is not None and p["error"] in g["error"]


def _match(p, g):
    return (
        p["id"] == g["id"]
        and abs(p["t_start"] - g["t_start"]) <= g["tau"]
        and abs(p["t_end"] - g["t_end"]) <= g["tau"]
        and _error_ok(p, g)
    )


def _match_without_error(p, g):
    # diagnostic: label, order and both boundaries right, error tag ignored. The gap
    # between this and the reward is what the error field costs a given submission.
    return (
        p["id"] == g["id"]
        and abs(p["t_start"] - g["t_start"]) <= g["tau"]
        and abs(p["t_end"] - g["t_end"]) <= g["tau"]
    )


def _match_onset_only(p, g):
    # diagnostic: right label, onset pinned, offset ignored
    return p["id"] == g["id"] and abs(p["t_start"] - g["t_start"]) <= g["tau"]


def _match_label_only(p, g):
    # diagnostic: right label in the right place in the sequence, timing ignored
    return p["id"] == g["id"]


def grade(entries):
    """Score a list of predicted entries. Returns the details dict."""
    truncated = len(entries) > MAX_ENTRIES
    preds = [_norm(e) for e in entries[:MAX_ENTRIES]]
    unusable = sum(1 for p in preds if p is None)

    by_video = {letter: [] for letter in GROUND_TRUTH}
    for p in preds:
        if p is not None:
            by_video[p["video"]].append(p)

    # Canonical order within each video: by onset, ties broken by label id. The alignment
    # below is order-preserving, so without this the key's own arbitrary order among steps
    # that start at the same second becomes a hidden requirement: video U has two steps
    # that both start at 455.647, and submitting them the other way round dropped a
    # perfect oracle to 0.9968. The prompt states this same rule, so an agent can produce
    # the canonical order itself, and applying it here means it does not have to. For a
    # submission that already follows the prompt's "order by the moment the step begins",
    # this is a no-op.
    for letter in by_video:
        by_video[letter].sort(key=lambda e: (e["t_start"], e["id"]))

    per_video = {}
    tp = tp_onset = tp_label = 0
    for letter, gt in GROUND_TRUTH.items():
        got = by_video[letter]
        hits = _max_monotonic(got, gt, _match)
        tp += hits
        tp_onset += _max_monotonic(got, gt, _match_onset_only)
        tp_label += _max_monotonic(got, gt, _match_label_only)
        per_video[letter] = {
            "n_ground_truth": len(gt),
            "n_predicted": len(got),
            "true_positives": hits,
        }

    n_pred = len(preds)
    n_gt = sum(len(v) for v in GROUND_TRUTH.values())
    precision = tp / n_pred if n_pred else 0.0
    recall = tp / n_gt if n_gt else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "n_ground_truth": n_gt,
        "n_predicted": n_pred,
        "true_positives": tp,
        "onset_only_matches": tp_onset,
        "label_and_order_only_matches": tp_label,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "per_video": per_video,
        "unusable_entries": unusable,
        "truncated_to_max_entries": truncated,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", required=True, type=Path)
    ap.add_argument("--reward-json", required=True, type=Path)
    ap.add_argument("--reward-txt", required=True, type=Path)
    args = ap.parse_args()

    reason = "ok"
    raw = []
    try:
        sol = json.loads(args.solution.read_text())
        raw = sol.get("sequence", sol.get("instances", sol.get("keysteps", [])))
        if not isinstance(raw, list):
            raise ValueError("sequence is not a list")
    except Exception as exc:  # noqa: BLE001 - a malformed submission scores 0
        reason, raw = f"unreadable solution.json: {exc}", []

    details = grade(raw)
    details["reason"] = reason
    reward = details["f1"]

    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps({"reward": reward, "details": details}, indent=2) + "\n")
    args.reward_txt.parent.mkdir(parents=True, exist_ok=True)
    args.reward_txt.write_text(f"{reward}\n")


if __name__ == "__main__":
    main()
