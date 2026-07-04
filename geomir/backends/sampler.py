"""Sampler backend — point-membership classification in pure numpy.

A third "kernel" with yet another math: solids are characteristic functions
f(x,y,z) -> {in, out} (implicit membership, F-rep-lite). Booleans are logical
ops on membership — they cannot fail, but there is no topology and volume is
estimated by sampling. Its role here:

  1. test oracle: lets the full pipeline (IR -> evaluate -> bake -> match_cast
     -> fallback) run and be verified with zero compiled dependencies;
  2. a live illustration that "different underlying math" is not just
     B-rep vs mesh — implicit membership is a third paradigm (cf. nTop).

No fillet (raises UnsupportedOp, same as the mesh kernel) and no mesh output
(returns None: baked artifacts made from this backend carry volume/bbox only).
"""

from __future__ import annotations

import numpy as np

from ..eval import UnsupportedOp


class _Solid:
    __slots__ = ("fn", "box")

    def __init__(self, fn, box):
        self.fn = fn          # (N,3) float array -> (N,) bool
        self.box = box        # (xmin, ymin, zmin, xmax, ymax, zmax)


def _combine_bbox(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), min(a[2], b[2]),
            max(a[3], b[3]), max(a[4], b[4]), max(a[5], b[5]))


class SamplerBackend:
    name = "sampler"

    def __init__(self, budget: int = 2_000_000):
        self.budget = budget  # total sample points for volume estimation

    # -- constructors --------------------------------------------------------
    def box(self, w, d, h):
        def fn(p):
            return ((p[:, 0] >= 0) & (p[:, 0] <= w) &
                    (p[:, 1] >= 0) & (p[:, 1] <= d) &
                    (p[:, 2] >= 0) & (p[:, 2] <= h))
        return _Solid(fn, (0.0, 0.0, 0.0, w, d, h))

    def cylinder(self, r, h):
        def fn(p):
            return ((p[:, 0] ** 2 + p[:, 1] ** 2 <= r * r) &
                    (p[:, 2] >= 0) & (p[:, 2] <= h))
        return _Solid(fn, (-r, -r, 0.0, r, r, h))

    # -- combinators ----------------------------------------------------------
    def translate(self, s, x, y, z):
        t = np.array([x, y, z])

        def fn(p):
            return s.fn(p - t)
        b = s.box
        return _Solid(fn, (b[0] + x, b[1] + y, b[2] + z,
                           b[3] + x, b[4] + y, b[5] + z))

    def union(self, a, b):
        def fn(p):
            return a.fn(p) | b.fn(p)
        return _Solid(fn, _combine_bbox(a.box, b.box))

    def difference(self, a, b):
        def fn(p):
            return a.fn(p) & ~b.fn(p)
        return _Solid(fn, a.box)  # conservative

    def fillet(self, s, r):
        raise UnsupportedOp(self.name, "geom.fillet")

    # -- queries ---------------------------------------------------------------
    def volume(self, s) -> float:
        b = s.box
        ex, ey, ez = b[3] - b[0], b[4] - b[1], b[5] - b[2]
        bbox_vol = ex * ey * ez
        if bbox_vol <= 0:
            return 0.0
        # cubic cells sized to the sample budget, cell-center classification
        cell = (bbox_vol / self.budget) ** (1.0 / 3.0)
        nx = max(2, int(np.ceil(ex / cell)))
        ny = max(2, int(np.ceil(ey / cell)))
        nz = max(2, int(np.ceil(ez / cell)))
        xs = b[0] + (np.arange(nx) + 0.5) * (ex / nx)
        ys = b[1] + (np.arange(ny) + 0.5) * (ey / ny)
        zs = b[2] + (np.arange(nz) + 0.5) * (ez / nz)
        gx, gy, gz = np.meshgrid(xs, ys, zs, indexing="ij")
        pts = np.column_stack([gx.ravel(), gy.ravel(), gz.ravel()])
        frac = float(np.count_nonzero(s.fn(pts))) / pts.shape[0]
        return frac * bbox_vol

    def bbox(self, s):
        return tuple(float(v) for v in s.box)

    def mesh(self, s):
        return None  # membership functions have no boundary representation
