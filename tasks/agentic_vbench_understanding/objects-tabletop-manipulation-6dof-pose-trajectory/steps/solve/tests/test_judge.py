#!/usr/bin/env python3
"""Regression tests for judge.py input handling. Run: python3 test_judge.py"""
import numpy as np

import judge


def _mini_gt():
    # unit-ish object: 4 mesh points, identity pose at both queries
    return {"clips": [{
        "clip": "clip_01", "object": "widget", "symmetric": False,
        "mesh_points_obj": [[0.0, 0.0, 0.0], [0.1, 0.0, 0.0], [0.0, 0.1, 0.0], [0.0, 0.0, 0.1]],
        "mesh_diag_m": 0.17,
        "queries": [
            {"frame": 10, "t_xyz_m": [0.0, 0.0, 0.5], "q_wxyz": [1.0, 0.0, 0.0, 0.0]},
            {"frame": 20, "t_xyz_m": [0.0, 0.0, 0.6], "q_wxyz": [1.0, 0.0, 0.0, 0.0]},
        ],
    }]}


def test_malformed_frame_ids_get_zero_not_crash():
    gt = _mini_gt()
    pred = {"clips": {"clip_01": [
        {"frame": "bad", "t_xyz_m": [0, 0, 0.5], "q_wxyz": [1, 0, 0, 0]},
        {"frame": None, "t_xyz_m": [0, 0, 0.5], "q_wxyz": [1, 0, 0, 0]},
        {"frame": [10], "t_xyz_m": [0, 0, 0.5], "q_wxyz": [1, 0, 0, 0]},
        {"frame": 20, "t_xyz_m": [0.0, 0.0, 0.6], "q_wxyz": [1.0, 0.0, 0.0, 0.0]},
    ]}}
    reward, per_clip, _ = judge.score(pred, gt)
    # frame 10 has no valid entry -> 0; frame 20 is exact -> 1; mean = 0.5
    assert abs(reward - 0.5) < 1e-9, reward
    assert per_clip["clip_01"]["scores"] == [0.0, 1.0], per_clip


def test_malformed_pose_payloads_get_zero_not_crash():
    gt = _mini_gt()
    pred = {"clips": {"clip_01": [
        {"frame": 10, "t_xyz_m": "not a vector", "q_wxyz": [1, 0, 0, 0]},
        {"frame": 20, "t_xyz_m": [0, 0, float("nan")], "q_wxyz": [1, 0, 0, 0]},
    ]}}
    reward, per_clip, _ = judge.score(pred, gt)
    assert reward == 0.0, reward


def test_non_dict_shapes_do_not_crash():
    gt = _mini_gt()
    for pred in [None, [], "x", {"clips": None}, {"clips": {"clip_01": "x"}},
                 {"clips": {"clip_01": [None, 42, "y"]}}]:
        reward, _, _ = judge.score(pred, gt)
        assert reward == 0.0, (pred, reward)


def test_exact_solution_scores_one():
    gt = _mini_gt()
    pred = {"clips": {"clip_01": [
        {"frame": 10, "t_xyz_m": [0.0, 0.0, 0.5], "q_wxyz": [1.0, 0.0, 0.0, 0.0]},
        {"frame": 20, "t_xyz_m": [0.0, 0.0, 0.6], "q_wxyz": [1.0, 0.0, 0.0, 0.0]},
    ]}}
    reward, _, _ = judge.score(pred, gt)
    assert abs(reward - 1.0) < 1e-9, reward


if __name__ == "__main__":
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as exc:
                fails += 1
                print(f"FAIL {name}: {exc}")
    raise SystemExit(1 if fails else 0)
