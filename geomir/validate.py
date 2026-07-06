"""geomir.validate — validation v2: mesh area + sampled Hausdorff distance.

Volume + bbox (validation v1, in artifact.py) can miss shape errors that
preserve volume (a feature moved from one side to another). The deep check
compares actual surfaces: sample points on both meshes (area-weighted) and
compute the symmetric sampled Hausdorff distance. Approximate by
construction — the sample count bounds resolution — but it is
backend-agnostic, pure numpy, and catches what volumes can't.

Used by artifact.import_artifact(..., deep=True) when both the baked oracle
mesh and the receiving kernel's mesh exist.
"""

from __future__ import annotations

import numpy as np


def mesh_area(vertices, faces) -> float:
    v = np.asarray(vertices, dtype=np.float64)
    f = np.asarray(faces, dtype=np.int64)
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return float(np.linalg.norm(np.cross(b - a, c - a), axis=1).sum() / 2.0)


def sample_surface(vertices, faces, n: int = 400,
                   seed: int = 0) -> np.ndarray:
    """Area-weighted random points on a triangle mesh, (n, 3)."""
    rng = np.random.default_rng(seed)
    v = np.asarray(vertices, dtype=np.float64)
    f = np.asarray(faces, dtype=np.int64)
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    areas = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2.0
    total = areas.sum()
    if total <= 0:
        return np.zeros((0, 3))
    idx = rng.choice(len(f), size=n, p=areas / total)
    r1, r2 = rng.random(n), rng.random(n)
    su = np.sqrt(r1)
    w0, w1, w2 = 1.0 - su, su * (1.0 - r2), su * r2
    return (a[idx] * w0[:, None] + b[idx] * w1[:, None] + c[idx] * w2[:, None])


def hausdorff(mesh_a, mesh_b, n: int = 400) -> float:
    """Symmetric sampled Hausdorff distance (mm) between two meshes given as
    (vertices, faces) or {"vertices":..., "faces":...} dicts."""
    def _unpack(m):
        if isinstance(m, dict):
            return m["vertices"], m["faces"]
        return m
    va, fa = _unpack(mesh_a)
    vb, fb = _unpack(mesh_b)
    pa = sample_surface(va, fa, n, seed=1)
    pb = sample_surface(vb, fb, n, seed=2)
    if len(pa) == 0 or len(pb) == 0:
        return float("inf")
    # brute-force pairwise distances (n<=~1000 keeps this trivial)
    d = np.linalg.norm(pa[:, None, :] - pb[None, :, :], axis=2)
    return float(max(d.min(axis=1).max(), d.min(axis=0).max()))
