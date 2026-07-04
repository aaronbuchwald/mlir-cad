"""Manifold backend — polyhedral mesh kernel (OpenSCAD's boolean engine).

This is OpenSCAD's math since its Manifold backend landed: solids are
triangle meshes with exact, guaranteed-robust mesh booleans. A cylinder is a
prism with `circular_segments` flat faces — its volume is *systematically*
smaller than pi*r^2*h by a factor of (N/2pi)*sin(2pi/N). That factor is the
demo's measurable "different underlying math": at N=64 the colonnade is
-0.16% vs OCCT (passes a 0.5% match_cast contract), at N=12 it is -4.5%
(fails it, and the importer falls back to baked geometry).

`circular_segments` is deliberately a *backend* parameter, not a recipe
parameter: faceting policy is a lowering decision, like -O flags or
-ffast-math — the same source, compiled differently.

Volume/bbox are computed from the output mesh via the divergence theorem
(version-proof and makes the math explicit).
"""

from __future__ import annotations

import numpy as np

from ..eval import UnsupportedOp


class ManifoldBackend:
    name = "manifold"

    def __init__(self, circular_segments: int = 64):
        from manifold3d import Manifold  # lazy import
        self._M = Manifold
        self.circular_segments = int(circular_segments)

    # -- constructors --------------------------------------------------------
    def box(self, w, d, h):
        return self._M.cube([w, d, h])  # corner at origin (center=False default)

    def cylinder(self, r, h):
        # (height, radius_low, radius_high, circular_segments); base at z=0,
        # axis +z, centered in xy — matches geom.cylinder semantics
        return self._M.cylinder(h, r, r, self.circular_segments)

    # -- combinators ----------------------------------------------------------
    def translate(self, s, x, y, z):
        return s.translate([x, y, z])

    def union(self, a, b):
        return a + b

    def difference(self, a, b):
        return a - b

    def fillet(self, s, r):
        # Edge fillets need B-rep topology (edges as first-class entities);
        # a mesh kernel has only triangles. This is the honest gap that
        # exercises per-element fallback.
        raise UnsupportedOp(self.name, "geom.fillet")

    # -- queries ---------------------------------------------------------------
    def _mesh_arrays(self, s):
        m = s.to_mesh() if hasattr(s, "to_mesh") else s.get_mesh()
        verts = np.asarray(m.vert_properties, dtype=np.float64)[:, :3]
        faces = np.asarray(m.tri_verts, dtype=np.int64).reshape(-1, 3)
        return verts, faces

    def volume(self, s) -> float:
        verts, faces = self._mesh_arrays(s)
        v0, v1, v2 = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
        # divergence theorem: sum of signed tetrahedron volumes
        return float(np.sum(np.einsum("ij,ij->i", v0, np.cross(v1, v2))) / 6.0)

    def bbox(self, s):
        verts, _ = self._mesh_arrays(s)
        mn, mx = verts.min(axis=0), verts.max(axis=0)
        return (float(mn[0]), float(mn[1]), float(mn[2]),
                float(mx[0]), float(mx[1]), float(mx[2]))

    def mesh(self, s):
        verts, faces = self._mesh_arrays(s)
        return verts.tolist(), faces.tolist()

    # -- export ----------------------------------------------------------------
    def export_stl(self, s, path: str):
        import trimesh
        verts, faces = self._mesh_arrays(s)
        trimesh.Trimesh(vertices=verts, faces=faces, process=False).export(path)
