#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import math
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_ground_truth.py")
SPEC = importlib.util.spec_from_file_location("dota_ground_truth", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {MODULE_PATH}")
GROUND_TRUTH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GROUND_TRUTH)


class GridBoundaryTests(unittest.TestCase):
    def test_internal_boundaries_belong_to_east_or_north_cell(self) -> None:
        for index, boundary in enumerate(GROUND_TRUTH.GRID_BOUNDARIES, start=1):
            with self.subTest(index=index):
                self.assertEqual(
                    GROUND_TRUTH.grid_axis(math.nextafter(boundary, -math.inf)),
                    index - 1,
                )
                self.assertEqual(GROUND_TRUTH.grid_axis(boundary), index)
                self.assertEqual(
                    GROUND_TRUTH.grid_axis(math.nextafter(boundary, math.inf)),
                    index,
                )

    def test_outer_edges_remain_inside_grid(self) -> None:
        self.assertEqual(GROUND_TRUTH.grid_axis(GROUND_TRUTH.RAW_MAP_MIN), 0)
        self.assertEqual(
            GROUND_TRUTH.grid_axis(
                GROUND_TRUTH.RAW_MAP_MIN + GROUND_TRUTH.RAW_MAP_SPAN
            ),
            GROUND_TRUTH.GRID_SIZE - 1,
        )

    def test_outside_map_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            GROUND_TRUTH.grid_axis(
                math.nextafter(GROUND_TRUTH.RAW_MAP_MIN, -math.inf)
            )
        with self.assertRaises(RuntimeError):
            GROUND_TRUTH.grid_axis(
                math.nextafter(
                    GROUND_TRUTH.RAW_MAP_MIN + GROUND_TRUTH.RAW_MAP_SPAN,
                    math.inf,
                )
            )


if __name__ == "__main__":
    unittest.main()
