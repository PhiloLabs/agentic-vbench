#!/usr/bin/env python3
"""Task 3 scorer: interacted-object 3D reconstruction across three clips.
Deterministic, numpy+scipy+trimesh (no VLM/LLM).

For each clip the agent submits a reconstructed triangle mesh of that clip's target
object (clip_01.{obj,ply,glb,stl}, ...). The scorer samples points from the submission
and from the reference mesh, aligns the submission to the reference with a scale-aware
registration invariant to the submission's arbitrary pose/scale (PCA-frame + 24
octahedral rotations, refined with similarity-ICP, ranked by a symmetric trimmed-chamfer
residual; the best fit is kept), then scores shape agreement with an F-score at a fixed
fraction of the reference diameter.

per-clip score = surface-F-score^2 * volumetric-IoU after best-fit similarity alignment.

The bare F-score is not shortcut-resistant: a convex hull of the reference points (which
fills every concavity) or an extruded silhouette slab still put a lot of surface near the
reference, so both score far too high. Two orthogonal agreement terms are therefore
multiplied:

  * Surface F-score  F = 2PR/(P+R), P = frac(pred within TAU of ref), R = frac(ref within
    TAU of pred). TAU = TAU_SPACING_MULT * (median nearest-neighbour spacing of the
    reference samples). Tying TAU to the sample spacing (rather than a fixed fraction of
    the diameter) makes it self-calibrating: dense/large-area detailed meshes get a
    proportionally larger tolerance, so the true shape survives even where sampling noise
    would trip a fixed threshold, while a wrong shape / slab still fails. F enters squared
    (i.e. precision and recall each count once) so low-overlap fakes are punished hard.

  * Volumetric IoU of flood-filled solid occupancy on a shared voxel grid. The exterior is
    flood-filled from the grid border through empty voxels; everything unreachable (the
    surface shell plus any sealed cavity) is 'solid'. The true shape and its reference
    agree; a convex hull turns open cavities into solid (IoU drops), and a slab occupies a
    completely different volume. This is the term that collapses a convex hull on genuinely
    concave objects and any silhouette slab.

The product is 1.0 for the identical mesh under any pose/scale (registration is scale-free)
and near 0 for a wrong/empty/hollow-filled/flattened shape. No per-object constants are used.
"""
import argparse
import itertools
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

FSCORE_FRAC = 0.02      # legacy fixed-diameter tolerance (kept for API/back-compat & reporting)
N_SAMPLE = 20000
_SAMPLE_SEED = 0        # fixed sampling seed -> score_one is fully deterministic
TAU_SPACING_MULT = 2.5  # surface tolerance = this many median inter-sample spacings
OCC_RES = 48            # occupancy grid: ~this many voxels across the reference diameter
OCC_SHELL_FRAC = 0.03   # surface-shell half-thickness as a fraction of the diameter


def _load_gt():
    d = json.loads((Path(__file__).with_name("ground_truth.json")).read_text())
    clips = {}
    for c in d["clips"]:
        clips[c["clip"]] = (np.asarray(c["gt_points"], float), float(c["gt_diag_m"]),
                            c["object"], float(c.get("oracle_iou", 1.0)),
                            float(c.get("oracle_f", 1.0)))
    return clips


def _sample_submission(path, n=N_SAMPLE):
    import trimesh
    m = trimesh.load(path, force="mesh")
    if m.vertices is None or len(m.vertices) == 0 or len(getattr(m, "faces", [])) == 0:
        raise ValueError("submission has no faces/vertices")
    # Seed the surface sampler so a given submission always scores identically. Newer
    # trimesh takes seed=; fall back to seeding numpy's global RNG for older versions.
    try:
        pts, _ = trimesh.sample.sample_surface(m, n, seed=_SAMPLE_SEED)
    except TypeError:
        np.random.seed(_SAMPLE_SEED)
        pts, _ = trimesh.sample.sample_surface(m, n)
    return np.asarray(pts, float)


def _octahedral_rotations():
    """The 24 proper (det=+1) signed permutation matrices, the rotational
    symmetries of the cube/octahedron."""
    ms = []
    for perm in itertools.permutations(range(3)):
        for sg in itertools.product([1, -1], repeat=3):
            M = np.zeros((3, 3))
            for i, p in enumerate(perm):
                M[i, p] = sg[i]
            if abs(np.linalg.det(M) - 1) < 1e-6:
                ms.append(M)
    return ms


def _pca_frame(pts):
    """Return (centroid, principal-axis matrix V, eigenvalues w) with columns of V
    the principal axes sorted by descending variance and det(V) = +1 (right-handed)."""
    c = pts.mean(0)
    X = pts - c
    cov = (X.T @ X) / len(X)
    w, V = np.linalg.eigh(cov)            # ascending eigenvalues, orthonormal V
    order = np.argsort(w)[::-1]
    w = w[order]
    V = V[:, order]
    if np.linalg.det(V) < 0:              # force a proper rotation
        V[:, 2] = -V[:, 2]
    return c, V, w


def _trimmed_residual(dists, trim=0.9):
    """Robust NN residual: mean of the smallest `trim` fraction of distances so a
    handful of bad correspondences don't dominate branch selection."""
    d = np.sort(dists)
    k = max(1, int(len(d) * trim))
    return float(d[:k].mean())


def _sim_icp(src, dst, tree=None, iters=25):
    """Iterated similarity (scale+rotation+translation) ICP via Umeyama on NN pairs.
    Returns the aligned copy of `src`."""
    if tree is None:
        tree = cKDTree(dst)
    S = src.copy()
    for _ in range(iters):
        _, idx = tree.query(S)
        X, Y = S, dst[idx]
        mx, my = X.mean(0), Y.mean(0)
        Xc, Yc = X - mx, Y - my
        C = Xc.T @ Yc / len(X)
        U, D, Vt = np.linalg.svd(C)
        dsign = np.sign(np.linalg.det(Vt.T @ U.T))
        Dm = np.diag([1.0, 1.0, dsign])
        R = Vt.T @ Dm @ U.T
        s = np.trace(np.diag(D) @ Dm) / ((Xc ** 2).sum() / len(X) + 1e-12)
        t = my - s * R @ mx
        S = (s * (R @ S.T).T) + t
    return S


def _bidir_residual(S, dst, tree_dst, trim=0.9):
    """Symmetric (both-directions) trimmed NN residual between aligned source `S`
    and target `dst`. The dst->src term is essential: it penalises degenerate fits
    that collapse the source to a blob (small src->dst error but huge dst->src)."""
    d_sd, _ = tree_dst.query(S)
    d_ds, _ = cKDTree(S).query(dst)
    return _trimmed_residual(d_sd, trim) + _trimmed_residual(d_ds, trim)


def _robust_align(src, dst):
    """Scale-aware global registration robust to arbitrary source pose/scale.

    Align the source's PCA frame onto the target's PCA frame, then enumerate the 24
    proper signed-permutation elements of the octahedral group *within* that shared
    frame. This resolves the axis-order / sign ambiguity of PCA (including near-
    degenerate cases) while starting every branch close to the true orientation.
    Each branch is refined with a short similarity-ICP and ranked by a *symmetric*
    trimmed chamfer residual (so scale-collapsing branches are rejected) on a fixed
    coarse subsample; the top few are refined on the full set and the global best
    (again by symmetric residual) is kept.
    """
    c_s, V_s, w_s = _pca_frame(src)
    c_d, V_d, w_d = _pca_frame(dst)
    s0 = np.sqrt(w_d.sum() / (w_s.sum() + 1e-12))   # RMS-radius scale estimate
    src0 = src - c_s

    # Deterministic coarse subsamples for cheap branch ranking.
    rng = np.random.default_rng(0)
    cs = min(len(src), 2000)
    cd = min(len(dst), 3000)
    idx_s = rng.choice(len(src), cs, replace=False) if len(src) > cs else np.arange(len(src))
    idx_d = rng.choice(len(dst), cd, replace=False) if len(dst) > cd else np.arange(len(dst))
    src_cs = src0[idx_s]
    dst_cs = dst[idx_d]
    tree_cs = cKDTree(dst_cs)

    cands = []
    for G in _octahedral_rotations():
        R0 = V_d @ G @ V_s.T
        init = (s0 * (R0 @ src_cs.T).T) + c_d
        S = _sim_icp(init, dst_cs, tree=tree_cs, iters=20)
        err = _bidir_residual(S, dst_cs, tree_cs)
        cands.append((err, R0))
    cands.sort(key=lambda x: x[0])

    tree_full = cKDTree(dst)
    best = None
    for _, R0 in cands[:4]:
        init = (s0 * (R0 @ src0.T).T) + c_d
        S = _sim_icp(init, dst, tree=tree_full, iters=40)
        err = _bidir_residual(S, dst, tree_full)
        if best is None or err < best[1]:
            best = (S, err)
    return best[0]


def _fscore(P, Q, tau):
    dpq, _ = cKDTree(Q).query(P)
    dqp, _ = cKDTree(P).query(Q)
    prec = float((dpq < tau).mean())
    rec = float((dqp < tau).mean())
    f = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    chamfer = float(dpq.mean() + dqp.mean())
    return f, prec, rec, chamfer


def _solid_occupancy(points, origin, res, vox):
    """Rasterise a surface point cloud into a filled solid on a (res,res,res) grid.

    A voxel is 'surface' if it holds a sample point; the shell is closed with one voxel
    of binary dilation so an independently-sampled copy of the same surface produces a
    watertight-enough shell (this makes the true shape's self-IoU ~1 rather than losing
    ~13% to shell-voxel misalignment). The exterior is then found by labelling the empty
    region and taking the components that touch the grid border; every other voxel (the
    shell, the interior, and any enclosed cavity) is 'solid'. A convex hull that fills a
    real concavity therefore reads as extra solid there, and a flat slab occupies a
    different volume, while the true shape matches."""
    from scipy import ndimage
    idx = np.floor((points - origin) / vox).astype(int)
    idx = np.clip(idx, 0, res - 1)
    surf = np.zeros((res, res, res), dtype=bool)
    surf[idx[:, 0], idx[:, 1], idx[:, 2]] = True
    surf = ndimage.binary_dilation(surf, iterations=1)   # close sampling gaps in the shell

    free = ~surf
    lbl, n = ndimage.label(free)                          # 6-connected empty components
    if n == 0:
        return surf
    border = np.unique(np.concatenate([
        lbl[0].ravel(), lbl[-1].ravel(), lbl[:, 0].ravel(),
        lbl[:, -1].ravel(), lbl[:, :, 0].ravel(), lbl[:, :, -1].ravel()]))
    border = border[border != 0]
    exterior = np.isin(lbl, border)
    return ~exterior                                      # solid = shell + interior + sealed cavities


def _voxel_iou(Pa, Q, res=OCC_RES):
    """Volumetric IoU of the filled solids of the aligned prediction Pa and the reference
    Q, on a shared grid spanning their common bounding box (with a small border pad)."""
    lo = np.minimum(Pa.min(0), Q.min(0))
    hi = np.maximum(Pa.max(0), Q.max(0))
    pad = 0.05 * (hi - lo).max()
    lo = lo - pad
    hi = hi + pad
    vox = (hi - lo).max() / res
    if vox <= 0:
        return 0.0
    solid_p = _solid_occupancy(Pa, lo, res, vox)
    solid_q = _solid_occupancy(Q, lo, res, vox)
    inter = np.logical_and(solid_p, solid_q).sum()
    union = np.logical_or(solid_p, solid_q).sum()
    return float(inter / union) if union else 0.0


def score_one(submission_path, gt_points, gt_diag, oracle_iou=1.0, oracle_f=1.0):
    """Shape agreement = (surface-F / oracle_f)^2 * (volumetric-IoU / oracle_iou) after
    best-fit similarity alignment, clipped to [0,1].

    Two orthogonal terms: the squared surface F-score punishes imprecise / partial
    surfaces (a coarse blob has low F even when its bulk volume roughly matches), and the
    flood-filled volumetric IoU collapses concavity-filling convex hulls and flat
    silhouette slabs. Both are normalised by the per-object oracle ceilings (the F and IoU
    the true reference mesh itself reaches under independent surface sampling +
    voxelisation, baked at authoring), so the true shape scores 1.0 while sampling /
    quantisation loss is factored out. The product is 1 for the true shape at any
    pose/scale and near 0 for a shortcut or a loose reconstruction."""
    P = _sample_submission(submission_path)
    Pa = _robust_align(P, gt_points)
    # self-calibrating surface tolerance: a few median NN spacings of the reference
    dref, _ = cKDTree(gt_points).query(gt_points, k=2)
    spacing = float(np.median(dref[:, 1]))
    tau = TAU_SPACING_MULT * spacing
    f, prec, rec, chamfer = _fscore(Pa, gt_points, tau)
    iou = _voxel_iou(Pa, gt_points)
    f_norm = min(f / oracle_f, 1.0) if oracle_f > 0 else f
    iou_norm = min(iou / oracle_iou, 1.0) if oracle_iou > 0 else iou
    reward = (f_norm ** 2) * iou_norm
    return reward, {"surface_f": round(f, 4), "f_norm": round(f_norm, 4),
                    "voxel_iou": round(iou, 4), "iou_norm": round(iou_norm, 4),
                    "oracle_f": round(oracle_f, 4), "oracle_iou": round(oracle_iou, 4),
                    "precision": round(prec, 4), "recall": round(rec, 4),
                    "chamfer_m": round(chamfer, 5), "tau_m": round(tau, 5)}


def _find_clip_mesh(out_dir, clip_id):
    out = Path(out_dir)
    for ext in ("obj", "ply", "glb", "stl", "off"):
        p = out / f"{clip_id}.{ext}"
        if p.is_file():
            return p
    return None


def score(out_dir, clips):
    """clips: {clip_id: (gt_points, gt_diag, object_name)}. Mean F-score over clips."""
    per_clip = {}
    total = 0.0
    for cid, (gt_points, gt_diag, obj, oracle_iou, oracle_f) in clips.items():
        mesh = _find_clip_mesh(out_dir, cid)
        entry = {"object": obj}
        if mesh is None:
            entry.update({"score": 0.0, "reason": f"no mesh file {cid}.[obj|ply|glb|stl]"})
        else:
            try:
                r, d = score_one(str(mesh), gt_points, gt_diag, oracle_iou, oracle_f)
                entry.update({"score": round(r, 4), "file": mesh.name, **d})
                total += r
            except Exception as exc:  # noqa: BLE001
                entry.update({"score": 0.0, "reason": f"scoring failed: {exc}"})
        per_clip[cid] = entry
    reward = total / len(clips) if clips else 0.0
    return reward, per_clip


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-dir", required=True, type=Path,
                    help="dir the agent writes its per-clip meshes into")
    ap.add_argument("--reward-json", required=True, type=Path)
    ap.add_argument("--reward-txt", required=True, type=Path)
    args = ap.parse_args()

    clips = _load_gt()
    reward, per_clip = score(args.output_dir, clips)
    details = {"reason": "ok", "n_clips": len(clips),
               "fscore_frac": FSCORE_FRAC, "per_clip": per_clip}

    args.reward_json.parent.mkdir(parents=True, exist_ok=True)
    args.reward_json.write_text(json.dumps({"reward": round(float(reward), 4), "details": details}, indent=2))
    args.reward_txt.write_text(f"{round(float(reward), 4)}\n")


if __name__ == "__main__":
    main()
